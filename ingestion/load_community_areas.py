"""One-shot script: download community-area polygons from Socrata, cache to disk as GeoJSON.

Run with: python -m ingestion.load_community_areas
"""

import asyncio
import json
from pathlib import Path

import httpx

from backend.config import get_settings


OUTPUT = Path(__file__).resolve().parent / "data" / "community_areas.geojson"


async def main() -> None:
    settings = get_settings()
    url = f"{settings.socrata_base}/{settings.dataset_community_areas}.json"
    headers = {"X-App-Token": settings.socrata_app_token} if settings.socrata_app_token else {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        resp = await client.get(url, params={"$limit": 100}, headers=headers)
        resp.raise_for_status()
        rows = resp.json()

    features = []
    for row in rows:
        name = row.get("community", "").strip()
        area_num = int(row.get("area_numbe") or row.get("area_num_1") or 0)
        geom = row.get("the_geom")
        if not geom or not area_num:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {"community_area": area_num, "name": name.title()},
                "geometry": geom,
            }
        )

    fc = {"type": "FeatureCollection", "features": features}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(fc))
    print(f"Wrote {len(features)} community areas to {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
