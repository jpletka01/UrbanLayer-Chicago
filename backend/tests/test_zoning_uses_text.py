"""The use sentences for the downtown and manufacturing districts, pinned to the ingested code.

Kit P8/P10 (2026-10-02): the Profile said only "residential" for DC-16 and "No residential"
for M2-3. The use table decides more than that: downtown ground-floor dwellings are a special
use, and the M tables simply have no household-living row (§17-5-0204: unlisted = prohibited).
"""

import json
from pathlib import Path

import pytest

from backend.retrieval import zoning_definitions as zd

SECTIONS = Path(__file__).resolve().parents[2] / "ingestion" / "data" / "sections"


def _rows(article: str) -> list[list[str]]:
    path = SECTIONS / f"{article}.json"
    if not path.exists():
        pytest.skip(f"ordinance corpus not present: {path}")
    return [list(map(str, r)) for t in json.loads(path.read_text())["tables"] for r in t["data_rows"]]


def test_downtown_dwelling_rows_match_the_sentences():
    rows = _rows("17-4-0200")
    above = next(r for r in rows if "Dwelling Units located above the ground floor" in r[1])
    assert above[2:6] == ["P", "P", "P", "-"]  # DC DX DR DS: not allowed in DS
    ground = {r[1]: r[2:6] for r in rows if r[1] in ("Detached House", "Multi-unit (3+ units) residential", "Townhouse", "Two-Flat")}
    assert ground["Multi-unit (3+ units) residential"] == ["S", "S", "P", "-"]
    assert ground["Detached House"][0] == ground["Townhouse"][0] == ground["Two-Flat"][0] == "-"  # DC: not allowed
    assert set(ground["Detached House"][1:2] + ground["Townhouse"][1:2] + ground["Two-Flat"][1:2]) == {"S"}  # DX: special use
    assert "above the ground floor are permitted" in zd._DC_USES and "special use" in zd._DC_USES
    assert "above the ground floor are permitted" in zd._DX_USES and "special use" in zd._DX_USES
    assert "every floor" in zd._DR_USES
    assert "No dwelling units" in zd._DS_USES


def test_manufacturing_has_no_household_living_row():
    rows = _rows("17-5-0200")
    assert not [r for r in rows if "Household Living" in r[0] and len(r) > 2 and r[2] in ("P", "S")]
    assert not [r for r in rows if "Dwelling" in r[1] or "Multi-unit" in r[1]]
    assert "unlisted uses are prohibited" in zd._M2_USES and "§17-5-0204" in zd._M2_USES


def test_business_commercial_dwelling_rows_match_the_sentences():
    """§17-3-0207 columns: B1 B2 B3 C1 C2 C3. Above the ground floor: P everywhere but C3; on the
    ground floor: special use in B1/B3/C1/C2, permitted in B2, nothing in C3."""
    rows = _rows("17-3-0200")
    row = lambda name: next(r for r in rows if r[1] == name)[2:8]  # noqa: E731
    assert row("Dwelling Units located above the ground floor") == ["P", "P", "P", "P", "P", "-"]
    for dwelling in ("Detached House", "Multi-Unit (3+ units) Residential", "Townhouse", "Two-Flat"):
        assert row(dwelling) == ["S", "P", "S", "S", "S", "-"]
    for sentence in (zd._B1_USES, zd._B3_USES, zd._C1_USES, zd._C2_USES):
        assert "special use" in sentence and "above the ground floor" in sentence
    assert "on or above the ground floor" in zd._B2_USES and "special use" not in zd._B2_USES
    assert "No dwelling units" in zd._C3_USES
