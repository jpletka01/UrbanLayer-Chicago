"""Guard the deterministic zoning reference data against the ingested ordinance.

The 2026-07-06 audit found hand-typed values in ``zoning_definitions.py`` that
the ordinance text (already parsed under ``ingestion/data/sections/``)
disproves — fabricated RM/M-district heights, an invented R-district
lot-coverage standard, and per-unit lot-area mis-rows — which the cache build
then stamped "high" confidence into the committed artifact. These tests parse
the bulk tables straight from the section JSONs and diff every number the
reference table (and the served cache) claims, so a hand-typed value can never
again outrank the machine-readable source sitting in the same repo.

If Title 17 is re-ingested with a real ordinance change, the failing assertion
points at exactly the drifted value to update.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from backend.retrieval.zoning_definitions import (
    ZONE_CLASS_DATA,
    min_lot_area_per_unit,
)
from backend.zoning_extract import standards_from_definitions

SECTIONS_DIR = Path(__file__).resolve().parents[2] / "ingestion" / "data" / "sections"

# Which dash-number FAR/height/per-unit rows apply to which zone prefixes.
BC_PREFIXES = ("B1", "B2", "B3", "C1", "C2", "C3")
BC_RESIDENTIAL_PREFIXES = ("B1", "B2", "B3", "C1", "C2")  # C3: no dwelling units
M_PREFIXES = ("M1", "M2", "M3")
D_PREFIXES = ("DX", "DC", "DR", "DS")
D_RESIDENTIAL_PREFIXES = ("DX", "DC", "DR")  # DS: no dwelling units


def _section(section_id: str) -> dict:
    path = SECTIONS_DIR / f"{section_id}.json"
    if not path.exists():
        pytest.skip(f"ordinance corpus not present: {path}")
    return json.loads(path.read_text())


def _tables(section: dict, header_substring: str) -> list[dict]:
    return [
        t
        for t in section.get("tables", [])
        if any(header_substring in (h or "") for h in t.get("headers", []))
    ]


def _first_number(text: str) -> float | None:
    m = re.search(r"[\d,]+(?:\.\d+)?", text or "")
    return float(m.group(0).replace(",", "")) if m else None


def _dwelling_units_number(text: str) -> int | None:
    """Per-unit cells read 'Dwelling units: 1,000 Efficiency units: …' or '1,250'."""
    m = re.search(r"Dwelling units:\s*([\d,]+)", text or "")
    if m:
        return int(m.group(1).replace(",", ""))
    n = _first_number(text)
    return int(n) if n is not None else None


def _r_zone_key(raw: str) -> str | None:
    """'RM4.5' → 'RM-4.5'; None for non-zone rows."""
    m = re.match(r"^(R[SMT])([\d.]+)$", (raw or "").strip())
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _dash_key(raw: str) -> str | None:
    """'Dash 1.5' / '-3' → '1.5' / '3'; None for separator/blank rows."""
    m = re.match(r"^(?:Dash\s+|-)([\d.]+)", (raw or "").strip())
    return m.group(1) if m else None


def _zones_with_dash(prefixes: tuple[str, ...], dash: str) -> list[str]:
    return [
        z
        for z in ZONE_CLASS_DATA
        if any(z == f"{p}-{dash}" for p in prefixes)
    ]


# ---------------------------------------------------------------------------
# FAR — every district family
# ---------------------------------------------------------------------------

def test_residential_far_matches_ordinance():
    sec = _section("17-2-0300")
    (table,) = _tables(sec, "Maximum Floor Area Ratio")
    checked = 0
    for raw_zone, raw_far in table["data_rows"]:
        zone = _r_zone_key(raw_zone)
        if not zone:
            continue
        assert zone in ZONE_CLASS_DATA, f"{zone} missing from ZONE_CLASS_DATA"
        expected = _first_number(raw_far)
        assert ZONE_CLASS_DATA[zone].far == pytest.approx(expected), (
            f"{zone}: table FAR {ZONE_CLASS_DATA[zone].far} != ordinance {expected}"
        )
        checked += 1
    assert checked >= 10  # all RS/RT/RM rows


def test_bc_and_m_far_matches_ordinance():
    for section_id, prefixes in (("17-3-0400", BC_PREFIXES), ("17-5-0400", M_PREFIXES)):
        sec = _section(section_id)
        # The plain dash table (the ARO variant has an extra column).
        table = next(
            t for t in _tables(sec, "Maximum Floor Area Ratio") if len(t["headers"]) == 2
        )
        for raw_dash, raw_far in table["data_rows"]:
            dash = _dash_key(raw_dash)
            if not dash:
                continue
            expected = _first_number(raw_far)
            for zone in _zones_with_dash(prefixes, dash):
                assert ZONE_CLASS_DATA[zone].far == pytest.approx(expected), (
                    f"{zone}: table FAR {ZONE_CLASS_DATA[zone].far} != ordinance {expected}"
                )


def test_downtown_far_matches_ordinance():
    sec = _section("17-4-0400")
    table = next(
        t for t in _tables(sec, "Maximum Base Floor Area Ratio")
    )
    checked = 0
    for row in table["data_rows"]:
        dash = _dash_key(row[0])
        if not dash:
            continue
        expected = _first_number(row[1])
        for zone in _zones_with_dash(D_PREFIXES, dash):
            assert ZONE_CLASS_DATA[zone].far == pytest.approx(expected), (
                f"{zone}: table FAR {ZONE_CLASS_DATA[zone].far} != ordinance {expected}"
            )
            checked += 1
    assert checked >= 10  # DX-3..16, DC-12/16, DR-3..10, DS-3/5


# ---------------------------------------------------------------------------
# Minimum lot area (lot size — an R-district-only standard)
# ---------------------------------------------------------------------------

def test_residential_min_lot_area_matches_ordinance():
    sec = _section("17-2-0300")
    table = next(
        t
        for t in _tables(sec, "Minimum Lot Area")
        if not any("per Unit" in h for h in t["headers"])
    )
    expectations: dict[str, int] = {}
    for raw_zone, raw_val in table["data_rows"]:
        val = _first_number(raw_val)
        if val is None:
            continue
        if "to" in raw_zone:  # "RT4 to RM6.5" — a range row
            expectations.update({
                z: int(val)
                for z in ZONE_CLASS_DATA
                if z == "RT-4" or z.startswith("RM-")
            })
        else:
            zone = _r_zone_key(raw_zone)
            if zone:
                expectations[zone] = int(val)
    assert len(expectations) >= 10
    for zone, expected in expectations.items():
        assert ZONE_CLASS_DATA[zone].min_lot_sqft == expected, (
            f"{zone}: min_lot_sqft {ZONE_CLASS_DATA[zone].min_lot_sqft} != ordinance {expected}"
        )


def test_non_r_districts_have_no_min_lot_size():
    for zone, d in ZONE_CLASS_DATA.items():
        if not zone.startswith(("RS-", "RT-", "RM-")):
            assert d.min_lot_sqft is None, (
                f"{zone}: min_lot_sqft={d.min_lot_sqft} but Title 17 sets no "
                "minimum lot size outside R districts"
            )


# ---------------------------------------------------------------------------
# Minimum lot area PER DWELLING UNIT (the density control)
# ---------------------------------------------------------------------------

def test_residential_per_unit_matches_ordinance():
    sec = _section("17-2-0300")
    table = next(t for t in _tables(sec, "Minimum Lot Area per Unit"))
    checked = 0
    for raw_zone, raw_val in table["data_rows"]:
        zone = _r_zone_key(raw_zone)
        if not zone:
            continue
        expected = _dwelling_units_number(raw_val)
        assert min_lot_area_per_unit(zone) == expected, (
            f"{zone}: per-unit {min_lot_area_per_unit(zone)} != ordinance {expected}"
        )
        checked += 1
    assert checked >= 10


def test_bc_per_unit_matches_ordinance():
    sec = _section("17-3-0400")
    table = next(
        t
        for t in _tables(sec, "Per Dwelling Unit")
        if not any("ARO" in h for h in t["headers"])
    )
    dash_expected = {}
    for row in table["data_rows"]:
        dash = _dash_key(row[0])
        if dash:
            dash_expected[dash] = _dwelling_units_number(row[1])
    assert dash_expected  # sanity
    for prefix in BC_RESIDENTIAL_PREFIXES:
        for dash, expected in dash_expected.items():
            zone = f"{prefix}-{dash}"
            if zone in ZONE_CLASS_DATA:
                assert min_lot_area_per_unit(zone) == expected, (
                    f"{zone}: per-unit {min_lot_area_per_unit(zone)} != ordinance {expected}"
                )
    # Districts that permit no dwelling units must yield None, never a number.
    for zone in ("C3-1", "C3-5", "M1-1", "M2-2", "M3-3", "DS-3", "DS-5"):
        assert min_lot_area_per_unit(zone) is None, f"{zone} permits no dwelling units"


def test_downtown_per_unit_matches_ordinance():
    sec = _section("17-4-0400")
    table = next(
        t
        for t in _tables(sec, "Minimum Lot Area per Unit")
        if not any("ARO" in h for h in t["headers"])
    )
    for row in table["data_rows"]:
        dash = _dash_key(row[0])
        if not dash:
            continue
        expected = _dwelling_units_number(row[1])
        for prefix in D_RESIDENTIAL_PREFIXES:
            zone = f"{prefix}-{dash}"
            if zone in ZONE_CLASS_DATA:
                assert min_lot_area_per_unit(zone) == expected, (
                    f"{zone}: per-unit {min_lot_area_per_unit(zone)} != ordinance {expected}"
                )


# ---------------------------------------------------------------------------
# Maximum building height
# ---------------------------------------------------------------------------

def _numeric_floor_for(zone: str) -> int | None:
    std = standards_from_definitions(zone)
    assert std is not None, f"{zone} should synthesize standards"
    return std.max_height_ft


def test_residential_heights_match_ordinance():
    """Our numeric height must be the LOWEST ordinance tier (true everywhere in
    the district); districts the ordinance leaves uncapped must parse to None."""
    sec = _section("17-2-0300")
    table = next(t for t in _tables(sec, "Maximum Building Height"))
    checked = 0
    for raw_zone, cell in table["data_rows"]:
        zone = _r_zone_key(raw_zone)
        if not zone:
            continue
        residential_part = cell.split("Principal nonresidential")[0]
        tiers = [int(x) for x in re.findall(r":\s*(\d+)", residential_part)]
        expected = min(tiers) if tiers else None
        actual = _numeric_floor_for(zone)
        assert actual == expected, (
            f"{zone}: height floor {actual} != ordinance {expected} (tiers {tiers})"
        )
        checked += 1
    assert checked >= 10


def test_bc_heights_match_ordinance():
    sec = _section("17-3-0400")
    height_tables = _tables(sec, "Maximum Building Height")
    assert height_tables
    dash_min: dict[str, int] = {}
    for table in height_tables:
        for row in table["data_rows"]:
            dash = _dash_key(row[0])
            if not dash:
                continue
            values = []
            for cell in row[1:]:
                m = re.match(r"\s*(\d+)", cell or "")
                if m:
                    values.append(int(m.group(1)))
            if values:
                dash_min[dash] = min(dash_min.get(dash, 10**9), *values)
    assert dash_min
    for prefix in BC_PREFIXES:
        for dash, expected in dash_min.items():
            zone = f"{prefix}-{dash}"
            if zone in ZONE_CLASS_DATA:
                actual = _numeric_floor_for(zone)
                assert actual == expected, (
                    f"{zone}: height floor {actual} != ordinance minimum tier {expected}"
                )


def test_m_districts_have_no_height_standard():
    sec = _section("17-5-0400")
    assert not _tables(sec, "Height"), "17-5-0400 grew a height table — update the reference data"
    body = "\n".join(sec.get("body_paragraphs", []))
    assert "height" not in body.lower()
    for zone in ZONE_CLASS_DATA:
        if zone.startswith(M_PREFIXES):
            assert _numeric_floor_for(zone) is None, (
                f"{zone}: carries a numeric height but Title 17 sets none for M districts"
            )


def test_downtown_heights_are_uncapped():
    for zone in ZONE_CLASS_DATA:
        if zone.startswith(D_PREFIXES):
            assert _numeric_floor_for(zone) is None, (
                f"{zone}: D-district height is governed by FAR/bonuses, not a fixed cap"
            )


# ---------------------------------------------------------------------------
# Lot coverage — NOT a Title 17 base-district standard
# ---------------------------------------------------------------------------

def test_no_base_district_lot_coverage_standard():
    for section_id in ("17-2-0300", "17-3-0400", "17-4-0400", "17-5-0400"):
        sec = _section(section_id)
        text = json.dumps(sec).lower()
        assert "lot coverage" not in text, (
            f"{section_id} now mentions lot coverage — revisit the force-null in "
            "apply_table_authority"
        )
    for zone, d in ZONE_CLASS_DATA.items():
        assert d.lot_coverage is None, f"{zone}: lot_coverage must not be populated"
        std = standards_from_definitions(zone)
        if std is not None:
            assert std.lot_coverage_pct is None, f"{zone}: lot_coverage_pct must be None"


# ---------------------------------------------------------------------------
# The SERVED cache must agree with the table (authority applied on read)
# ---------------------------------------------------------------------------

def test_served_cache_matches_table_authority():
    from backend import zoning_cache

    zoning_cache.reset_cache()
    try:
        raw = json.loads((SECTIONS_DIR.parent / "zoning_cache.json").read_text())
    except FileNotFoundError:
        pytest.skip("committed zoning cache not present")

    zones = list(raw.get("entries", {}))
    assert zones
    compared = 0
    for zone in zones:
        served = zoning_cache.get_cached_zoning_standards(zone)
        if served is None:
            # config_version drift makes the whole artifact unservable; the
            # table fallback takes over at runtime, so nothing stale can leak.
            pytest.skip("cache config_version stale — serve path uses table fallback")
        table = standards_from_definitions(zone)
        assert table is not None
        for field in (
            "far",
            "max_height_ft",
            "lot_coverage_pct",
            "min_lot_area_sqft",
            "min_lot_area_per_unit_sqft",
        ):
            assert getattr(served, field) == getattr(table, field), (
                f"{zone}.{field}: served {getattr(served, field)!r} != "
                f"table-authoritative {getattr(table, field)!r}"
            )
        compared += 1
    assert compared == len(zones)
    zoning_cache.reset_cache()
