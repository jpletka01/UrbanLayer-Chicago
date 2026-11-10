"""Build ``cps_schools.json``: the Illinois Report Card's figures for every Chicago Public Schools school.

Front-end rewrite Phase 6, Neighborhood tab (decision Item 102).  The owner's call: the lot's assigned schools
(CPS attendance boundaries, queried live) with the state's own report card, never a private rating.  The report
card is ISBE's annual public data set, one 40 MB workbook for the whole state; this script keeps only CPS
(District 299) schools and only the measures the tab shows:

- ISBE's summative designation (Exemplary, Commendable, Targeted, Comprehensive, Intensive) and its year,
- # student enrollment,
- % of students meeting state standards in ELA and in math, from ``ELAMathScience`` (all tested grades); where
  ISBE suppressed or left that blank for a school serving high-school grades, the ``ACT`` sheet's high school
  assessment rate (``HS Assessment ... Proficiency Rate - Total``), marked ``*_source: "hs_assessment"``,
- the high school 4-year graduation rate,
- and, from CPS's progress report, its 5Essentials culture-and-climate rating (CPS's own attainment and growth
  ratings are "no data" for most schools in SY2425, so they are left out).

The workbook has no CPS school id, so the join goes through CPS's School Progress Reports on the City's portal
(``twrw-chuq``, SY2425): each row links its Illinois Report Card page with the school's RCDTS code in the URL
(``schoolid=150162990252510`` = ISBE's ``15-016-2990-25-2510`` without dashes).  The artifact is keyed by the
CPS ``school_id`` that the attendance-boundary layers carry.

Usage:  PYTHONPATH=. python -m ingestion.build_cps_schools_artifact --workbook <rc2025.xlsx> --year 2025 \
            --retrieved 2026-11-09
The workbook comes from https://www.isbe.net/pages/illinois-state-report-card-data.aspx ("Report Card Public
Data Set"); keep the raw copy outside the repo.  Needs ``openpyxl`` (not a project dependency: run it from a
throwaway venv with ``httpx`` too).  Production never runs this; it reads the committed artifact.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "ingestion" / "data" / "cps_schools.json"
META_PATH = OUTPUT_PATH.with_name("cps_schools.meta.json")
SOURCE_URL = "https://www.isbe.net/pages/illinois-state-report-card-data.aspx"
PROGRESS_REPORTS = "https://data.cityofchicago.org/resource/twrw-chuq.json"
CPS_DISTRICT = "15-016-2990-25"
DESIGNATIONS = {"Exemplary", "Commendable", "Targeted", "Comprehensive", "Intensive"}


def rcdts_key(code: str) -> str:
    """ISBE's RCDTS with the dashes removed, upper-cased: the form CPS's report-card links carry."""
    return re.sub(r"[^0-9A-Za-z]", "", code).upper()


def _pct(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None  # ISBE writes "*" for a suppressed small group
    if not 0 <= f <= 100:
        raise ValueError(f"percentage out of range: {v!r}")
    return round(f, 1)


def _int(v) -> int | None:
    try:
        return int(float(v)) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def read_workbook(path: Path) -> dict[str, dict]:
    """RCDTS key → the school's figures, CPS schools only."""
    import openpyxl  # throwaway-venv dependency, see the module docstring

    wb = openpyxl.load_workbook(path, read_only=True)

    def sheet(name: str, cols: list[str]):
        it = wb[name].iter_rows(values_only=True)
        hdr = next(it)
        missing = [c for c in ["RCDTS", "Level", *cols] if c not in hdr]
        if missing:
            raise ValueError(f"sheet {name!r} lacks {missing}: ISBE changed the layout")
        ix = {c: hdr.index(c) for c in ["RCDTS", "Level", *cols]}
        for r in it:
            code = str(r[ix["RCDTS"]] or "")
            if r[ix["Level"]] == "School" and code.startswith(CPS_DISTRICT):
                yield rcdts_key(code), {c: r[ix[c]] for c in cols}

    out: dict[str, dict] = {}
    for key, r in sheet("General", ["School Name", "School Type", "Grades Served", "Summative Designation",
                                     "# Student Enrollment", "High School 4-Year Graduation Rate - Total"]):
        designation = r["Summative Designation"] if r["Summative Designation"] in DESIGNATIONS else None
        out[key] = {
            "isbe_name": r["School Name"],
            "type": r["School Type"],
            "grades": r["Grades Served"],
            "designation": designation,
            "enrollment": _int(r["# Student Enrollment"]),
            "graduation_4yr_pct": _pct(r["High School 4-Year Graduation Rate - Total"]),
        }
    for key, r in sheet("ELAMathScience", ["% ELA Proficiency", "% Math Proficiency"]):
        if key in out:
            out[key]["ela_pct"] = _pct(r["% ELA Proficiency"])
            out[key]["math_pct"] = _pct(r["% Math Proficiency"])
    for key, r in sheet("ACT", ["HS Assessment ELA Proficiency Rate - Total", "HS Assessment Math Proficiency Rate - Total"]):
        rec = out.get(key)
        if rec is None:
            continue
        for field, col in (("ela_pct", "HS Assessment ELA Proficiency Rate - Total"), ("math_pct", "HS Assessment Math Proficiency Rate - Total")):
            v = _pct(r[col])
            if rec.get(field) is None and v is not None:
                rec[field] = v
                rec[f"{field.split('_')[0]}_source"] = "hs_assessment"
    if len(out) < 400:
        raise ValueError(f"only {len(out)} CPS schools in the workbook: wrong file or layout")
    return out


def fetch_progress_reports() -> list[dict]:
    import httpx

    r = httpx.get(PROGRESS_REPORTS, params={
        "$select": "school_id,long_name,short_name,primary_category,state_school_report_card,cps_school_profile,culture_climate_rating",
        "$limit": 5000,
    }, timeout=60)
    r.raise_for_status()
    return r.json()


def build(workbook: Path, year: int, retrieved: str, progress: list[dict] | None = None) -> dict:
    isbe = read_workbook(workbook)
    progress = progress if progress is not None else fetch_progress_reports()
    schools: dict[str, dict] = {}
    unmatched = 0
    for row in progress:
        url = (row.get("state_school_report_card") or {}).get("url") or ""
        m = re.search(r"schoolid=([0-9A-Za-z]+)", url)
        rec = isbe.get(m.group(1).upper()) if m else None
        if rec is None:
            unmatched += 1
            continue
        culture = (row.get("culture_climate_rating") or "").strip()
        schools[str(row["school_id"])] = {
            "name": row.get("long_name") or rec["isbe_name"],
            # CPS's 5Essentials culture-and-climate rating (its own survey; "Not Enough Data" is no rating)
            "culture": culture.capitalize() if culture and culture.lower() != "not enough data" else None,
            "category": row.get("primary_category"),
            "cps_url": (row.get("cps_school_profile") or {}).get("url"),
            "rcdts": m.group(1).upper(),
            **rec,
        }
    if len(schools) < 400:
        raise ValueError(f"only {len(schools)} schools joined: the progress-report links changed")
    return {
        "report_year": year,
        "source": "Illinois State Board of Education, Illinois Report Card public data set",
        "source_url": SOURCE_URL,
        "join": "CPS School Progress Reports SY2425 (twrw-chuq): report-card link -> RCDTS",
        "retrieved": retrieved,
        "unmatched_progress_rows": unmatched,
        "schools": dict(sorted(schools.items())),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workbook", type=Path, required=True)
    ap.add_argument("--year", type=int, required=True, help="the report card's year, e.g. 2025")
    ap.add_argument("--retrieved", default=date.today().isoformat())
    a = ap.parse_args()
    art = build(a.workbook, a.year, a.retrieved)
    OUTPUT_PATH.write_text(json.dumps(art, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    META_PATH.write_text(json.dumps({
        "builder": "ingestion/build_cps_schools_artifact.py",
        "built_at": date.today().isoformat(),
        "report_year": a.year,
        "retrieved": a.retrieved,
        "schools": len(art["schools"]),
    }, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(art['schools'])} schools ({art['unmatched_progress_rows']} progress rows unmatched)")


if __name__ == "__main__":
    main()
