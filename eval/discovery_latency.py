"""Discovery search latency ladder — read-only, no model, LOCAL backend only.

Runs the five-query ladder from the Discovery redesign plan (Section 3.2) against
`/api/discovery/search` and `/api/discovery/search/pins` and records, per query and
endpoint, every run's wall time (first / median / p95 / min), the response size and the
backend process RSS before and after. It also checks that the list's ordered PINs are a
prefix of the map's ordered PINs, with equal totals and dataVersion (the Item 30 parity).

The ladder (sort `lot_size desc` throughout):
  recipe (4 filters) -> 3 filters (no lot size) -> 1 filter (zoning: residential)
  -> no filters -> recipe again (the repeat/undo case)

Never point this at production: it refuses any non-loopback host. Numbers from a local
idle machine are not production numbers (production is a busy 4 vCPU box).

Usage:
  python -m eval.discovery_latency --base http://localhost:8003 --label baseline
  python -m eval.discovery_latency --base http://localhost:8003 --label after-cache --runs 7
Results land in eval/results/2026-10-29-discovery/<label>.{json,md}.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

RESULTS_DIR = Path(__file__).resolve().parent / "results" / "2026-10-29-discovery"

SORT = {"key": "lot_size", "dir": "desc"}
_VACANCY = {"kind": "flag", "value": True}
_RESIDENTIAL = {"kind": "enum", "values": ["residential"]}
_TRANSIT = {"kind": "range", "max": 0.5}
_LOT = {"kind": "range", "min": 3000}

LADDER: list[tuple[str, dict]] = [
    ("recipe (4 filters)", {"vacancy": _VACANCY, "zoning_group": _RESIDENTIAL, "transit_proximity": _TRANSIT, "lot_size": _LOT}),
    ("3 filters (no lot size)", {"vacancy": _VACANCY, "zoning_group": _RESIDENTIAL, "transit_proximity": _TRANSIT}),
    ("1 filter (zoning: residential)", {"zoning_group": _RESIDENTIAL}),
    ("no filters", {}),
    ("recipe again (repeat)", {"vacancy": _VACANCY, "zoning_group": _RESIDENTIAL, "transit_proximity": _TRANSIT, "lot_size": _LOT}),
]

ENDPOINTS = {"search": "/api/discovery/search", "pins": "/api/discovery/search/pins"}


def _envelope(filters: dict, **extra) -> dict:
    return {"userFilters": filters, "sort": SORT, **extra}


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


def _summ(values: list[float]) -> dict:
    return {
        "runs": [round(v, 1) for v in values],
        "first_ms": round(values[0], 1),
        "median_ms": round(statistics.median(values), 1),
        "p95_ms": round(_p95(values), 1),
        "min_ms": round(min(values), 1),
    }


def _backend_pid(port: int) -> int | None:
    try:
        out = subprocess.run(
            ["lsof", "-nP", "-tiTCP:%d" % port, "-sTCP:LISTEN"], capture_output=True, text=True, timeout=10
        ).stdout.split()
        return int(out[0]) if out else None
    except Exception:
        return None


def _rss_mb(pid: int | None) -> float | None:
    if pid is None:
        return None
    try:
        kb = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, timeout=10).stdout.strip()
        return round(int(kb) / 1024, 1)
    except Exception:
        return None


def _post(client: httpx.Client, base: str, path: str, body: dict) -> tuple[float, httpx.Response]:
    t0 = time.perf_counter()
    resp = client.post(base + path, json=body)
    ms = (time.perf_counter() - t0) * 1000
    resp.raise_for_status()
    return ms, resp


def parity(client: httpx.Client, base: str, filters: dict) -> dict:
    """Pin-sequence parity between the list window and the map (not timed)."""
    _, s = _post(client, base, ENDPOINTS["search"], _envelope(filters, limit=200))
    _, p = _post(client, base, ENDPOINTS["pins"], _envelope(filters))
    sj, pj = s.json(), p.json()
    list_pins = [r["pin"] for r in sj["result"]["rows"]]
    map_pins = [pt["pin"] for pt in pj["points"]]
    n = min(len(list_pins), len(map_pins))
    return {
        "rows_compared": n,
        "prefix_equal": list_pins[:n] == map_pins[:n],
        "total_equal": sj["result"]["total"] == pj["total"],
        "data_version_equal": sj["dataVersion"] == pj["dataVersion"],
        "gated": sj["result"]["gated"],
    }


def run(base: str, runs: int, label: str) -> dict:
    host = urlparse(base).hostname
    if host not in ("localhost", "127.0.0.1", "::1"):
        sys.exit(f"refusing non-loopback host {host!r}: this script measures a LOCAL backend only")
    port = urlparse(base).port or 80
    pid = _backend_pid(port)
    out: dict = {
        "label": label,
        "base": base,
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": {"platform": platform.platform(), "machine": platform.machine(), "note": "LOCAL idle machine, not production"},
        "runs_per_cell": runs,
        "rss_mb_before": _rss_mb(pid),
        "ladder": [],
    }
    with httpx.Client(timeout=300) as client:
        client.get(base + "/health").raise_for_status()
        for name, filters in LADDER:
            row: dict = {"query": name, "filters": sorted(filters)}
            for key, path in ENDPOINTS.items():
                times, size, total = [], 0, None
                for _ in range(runs):
                    ms, resp = _post(client, base, path, _envelope(filters))
                    times.append(ms)
                    size = len(resp.content)
                    body = resp.json()
                    total = body["result"]["total"] if key == "search" else body["total"]
                row[key] = {**_summ(times), "bytes": size, "total": total}
            row["parity"] = parity(client, base, filters)
            out["ladder"].append(row)
            print(f"{name:34s} search {row['search']['median_ms']:8.0f} ms  pins {row['pins']['median_ms']:8.0f} ms  total {row['search']['total']}", flush=True)
    out["rss_mb_after"] = _rss_mb(pid)
    return out


def markdown(res: dict) -> str:
    lines = [
        f"# Discovery latency: {res['label']}",
        "",
        f"Measured {res['measured_at']} against {res['base']} ({res['environment']['platform']}). "
        f"**Local idle machine, not production.** {res['runs_per_cell']} runs per cell; sort `lot_size desc`.",
        "",
        f"Backend RSS: {res['rss_mb_before']} MB before, {res['rss_mb_after']} MB after.",
        "",
        "| Query | Matches | /search first | /search median | /search p95 | /pins first | /pins median | /pins p95 | List=map parity |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in res["ladder"]:
        s, p, par = r["search"], r["pins"], r["parity"]
        ok = par["prefix_equal"] and par["total_equal"] and par["data_version_equal"]
        lines.append(
            f"| {r['query']} | {s['total']:,} | {s['first_ms']:.0f} | {s['median_ms']:.0f} | {s['p95_ms']:.0f} "
            f"| {p['first_ms']:.0f} | {p['median_ms']:.0f} | {p['p95_ms']:.0f} | {'ok' if ok else 'MISMATCH'} ({par['rows_compared']} rows) |"
        )
    lines += ["", "Times in milliseconds. 'first' is the first run of the cell, 'median'/'p95' are over all runs of the cell.", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8001", help="LOCAL backend base URL")
    ap.add_argument("--label", required=True, help="result name, e.g. baseline or after-cache")
    ap.add_argument("--runs", type=int, default=5)
    args = ap.parse_args()

    res = run(args.base.rstrip("/"), args.runs, args.label)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / f"{args.label}.json").write_text(json.dumps(res, indent=2) + "\n")
    (RESULTS_DIR / f"{args.label}.md").write_text(markdown(res))
    print(f"wrote {RESULTS_DIR / (args.label + '.json')} and .md")


if __name__ == "__main__":
    main()
