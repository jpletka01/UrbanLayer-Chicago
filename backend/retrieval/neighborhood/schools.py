"""The lot's assigned Chicago Public Schools and the state's report card for each (decision Item 102).

Owner's call (2026-11-09): the attendance-boundary elementary and high school, each with ISBE's own summative
designation, % meeting state standards in reading (ELA) and math, enrollment, and the high school's 4-year
graduation rate. Official CPS and ISBE data only, never a private rating.

- Which schools: CPS's attendance boundaries on the City's portal (``settings.dataset_cps_boundaries_es`` /
  ``_hs``), one point-in-polygon query each. A point inside no boundary is a checked "none" for that level
  (citywide and selective-enrollment schools have no boundary); a failed query raises (Item 65).
- Their figures: the committed artifact ``ingestion/data/cps_schools.json`` (built offline by
  ``ingestion.build_cps_schools_artifact`` from ISBE's report-card workbook), keyed by the CPS ``school_id``
  the boundary layers carry. A school the artifact lacks is still named, with ``report_card: None``.

Only the new UI's Profile parts read this (``main.NEXT_UI_TASK_KEYS``); chat and the report don't.
"""

from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

ARTIFACT = Path(__file__).resolve().parents[3] / "ingestion" / "data" / "cps_schools.json"
BOUNDARY_YEAR = "2025-26"  # the boundary layers' school year (CPS's SY2526 datasets)
_cache = TTLCache(ttl_seconds=86_400, maxsize=512, name="schools")


class SchoolsArtifactError(RuntimeError):
    """The committed report-card artifact is missing or unreadable: the schools are 'not checked'."""


@lru_cache(maxsize=1)
def _artifact(path: str = str(ARTIFACT)) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SchoolsArtifactError(f"CPS schools artifact unreadable: {exc}") from exc
    if not isinstance(data.get("schools"), dict):
        raise SchoolsArtifactError("CPS schools artifact has no schools table")
    return data


_REPORT_FIELDS = ("designation", "enrollment", "ela_pct", "math_pct", "graduation_4yr_pct", "ela_source", "math_source")


def _school(row: dict[str, Any], level: str) -> dict[str, Any]:
    art = _artifact()
    sid = str(row.get("school_id") or "")
    rec = art["schools"].get(sid)
    name = (rec or {}).get("name") or (row.get("short_name") or row.get("school_nam") or "").title() or None
    out: dict[str, Any] = {
        "school_id": sid,
        "level": level,
        "name": name,
        "grades": (rec or {}).get("grades") or row.get("boundarygr"),
        "address": (row.get("school_add") or "").title() or None,
        "cps_url": (rec or {}).get("cps_url") or (f"https://www.cps.edu/schools/schoolprofiles/{sid}" if sid else None),
        "report_card_url": (
            f"https://www.illinoisreportcard.com/school.aspx?source=profile&Schoolid={rec['rcdts']}" if rec and rec.get("rcdts") else None
        ),
        "report_card": None,
    }
    if rec:
        out["report_card"] = {k: rec.get(k) for k in _REPORT_FIELDS if rec.get(k) is not None}
        out["report_card"]["year"] = art.get("report_year")
    return out


async def _boundary(dataset: str, lat: float, lon: float) -> list[dict[str, Any]]:
    return await socrata_get(dataset, {
        "$select": "school_id,school_add,boundarygr,grade_cat",
        "$where": f"intersects(the_geom, 'POINT ({lon} {lat})')",
        "$limit": 5,
    })


async def assigned_schools(lat: float, lon: float) -> dict[str, Any]:
    """{elementary: school | None, high: school | None, boundary_year, report_year, source}. Raises when a
    boundary query fails or the artifact is unreadable (never a false "no assigned school")."""
    key = f"schools:{round(lat, 5)}:{round(lon, 5)}"
    cached = _cache.get(key)
    if cached is not None:
        return cached
    s = get_settings()
    art = _artifact()
    es_rows, hs_rows = await asyncio.gather(
        _boundary(s.dataset_cps_boundaries_es, lat, lon), _boundary(s.dataset_cps_boundaries_hs, lat, lon),
    )
    result = {
        "elementary": _school(es_rows[0], "elementary") if es_rows else None,
        "high": _school(hs_rows[0], "high") if hs_rows else None,
        "boundary_year": BOUNDARY_YEAR,
        "report_year": art.get("report_year"),
        "source": art.get("source"),
    }
    _cache.set(key, result)
    return result
