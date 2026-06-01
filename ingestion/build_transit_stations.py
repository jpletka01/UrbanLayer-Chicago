"""Build transit_stations.json from CTA and Metra GTFS feeds.

Downloads GTFS zip files, parses stops/routes/trips/stop_times,
and writes a JSON array of station objects to backend/data/.

Usage:
    python -m ingestion.build_transit_stations
"""

import csv
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "ingestion" / "data" / "transit_stations.json"

CTA_GTFS_URL = "https://www.transitchicago.com/downloads/sch_data/google_transit.zip"
METRA_GTFS_URL = "https://schedules.metrarail.com/gtfs/schedule.zip"


def _read_csv(zf: zipfile.ZipFile, name: str) -> list[dict]:
    with zf.open(name) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        rows = []
        for row in reader:
            rows.append({k.strip(): v.strip() for k, v in row.items()})
        return rows


def _build_cta_stations(zf: zipfile.ZipFile) -> list[dict]:
    stops = _read_csv(zf, "stops.txt")
    routes = {r["route_id"]: r for r in _read_csv(zf, "routes.txt")}
    trips = _read_csv(zf, "trips.txt")
    stop_times = _read_csv(zf, "stop_times.txt")

    # Map route_id -> human-readable line name
    route_names: dict[str, str] = {}
    for r in routes.values():
        name = r.get("route_long_name") or r.get("route_short_name") or r["route_id"]
        route_names[r["route_id"]] = name

    # Map trip_id -> route_id
    trip_to_route = {t["trip_id"]: t["route_id"] for t in trips}

    # Collect which routes serve each stop
    stop_routes: dict[str, set[str]] = defaultdict(set)
    for st in stop_times:
        route_id = trip_to_route.get(st["trip_id"])
        if route_id:
            stop_routes[st["stop_id"]].add(route_id)

    # Parent stations (location_type=1) represent the actual station
    parent_stops = {
        s["stop_id"]: s for s in stops
        if s.get("location_type") == "1"
    }

    # Collect routes for parent stations from their child stops
    parent_routes: dict[str, set[str]] = defaultdict(set)
    for s in stops:
        parent = s.get("parent_station", "")
        if parent and parent in parent_stops:
            parent_routes[parent].update(stop_routes.get(s["stop_id"], set()))

    stations = []
    for stop_id, stop in parent_stops.items():
        lat = float(stop["stop_lat"])
        lon = float(stop["stop_lon"])
        name = stop.get("stop_name", stop_id)
        route_ids = parent_routes.get(stop_id, set())
        lines = sorted({route_names.get(r, r) for r in route_ids})
        stations.append({
            "name": name,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "type": "cta_rail",
            "lines": lines,
        })

    return stations


def _build_metra_stations(zf: zipfile.ZipFile) -> list[dict]:
    stops = _read_csv(zf, "stops.txt")
    routes = {r["route_id"]: r for r in _read_csv(zf, "routes.txt")}
    trips = _read_csv(zf, "trips.txt")
    stop_times = _read_csv(zf, "stop_times.txt")

    route_names: dict[str, str] = {}
    for r in routes.values():
        name = r.get("route_long_name") or r.get("route_short_name") or r["route_id"]
        route_names[r["route_id"]] = name

    trip_to_route = {t["trip_id"]: t["route_id"] for t in trips}

    stop_routes: dict[str, set[str]] = defaultdict(set)
    for st in stop_times:
        route_id = trip_to_route.get(st["trip_id"])
        if route_id:
            stop_routes[st["stop_id"]].add(route_id)

    stations = []
    for s in stops:
        loc_type = s.get("location_type", "0")
        if loc_type == "1":
            continue
        lat = float(s["stop_lat"])
        lon = float(s["stop_lon"])
        name = s.get("stop_name", s["stop_id"])
        route_ids = stop_routes.get(s["stop_id"], set())
        lines = sorted({route_names.get(r, r) for r in route_ids})
        line = lines[0] if lines else None
        stations.append({
            "name": name,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "type": "metra",
            "line": line,
        })

    return stations


def main():
    headers = {"User-Agent": "UrbanLayer/1.0 (transit station data)"}

    print("Downloading CTA GTFS...")
    req = Request(CTA_GTFS_URL, headers=headers)
    with urlopen(req) as resp:
        cta_data = resp.read()
    cta_zf = zipfile.ZipFile(io.BytesIO(cta_data))
    cta_stations = _build_cta_stations(cta_zf)
    print(f"  {len(cta_stations)} CTA rail stations")

    print("Downloading Metra GTFS...")
    req = Request(METRA_GTFS_URL, headers=headers)
    with urlopen(req) as resp:
        metra_data = resp.read()
    metra_zf = zipfile.ZipFile(io.BytesIO(metra_data))
    metra_stations = _build_metra_stations(metra_zf)
    print(f"  {len(metra_stations)} Metra stations")

    all_stations = cta_stations + metra_stations
    all_stations.sort(key=lambda s: (s["type"], s["name"]))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(all_stations, indent=2) + "\n")
    print(f"Wrote {len(all_stations)} stations to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
