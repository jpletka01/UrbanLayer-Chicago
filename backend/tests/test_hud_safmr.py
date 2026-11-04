"""HUD Small Area Fair Market Rents by ZIP (WS4 PR5, decision Item 69): the artifact builder, the lookup, the
ZIP plumbing, the Profile attachment, provenance and the artifact age check."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from backend.data_health import artifacts
from backend.models import NeighborhoodSummary, PropertySummary, RentEvidence
from backend.retrieval.neighborhood import rent
from backend.retrieval.property import _zip5
from ingestion import build_hud_safmr_artifact as builder


@pytest.fixture(autouse=True)
def _reset():
    rent.reset_artifact()
    yield
    rent.reset_artifact()


def _tsv(rows: int = 300) -> str:
    lines = ["# copied from HUD", "zip\tbr0\tbr1\tbr2\tbr3\tbr4"]
    lines += [f"{60000 + i:05d}\t1000\t1100\t1300\t1700\t1900" for i in range(rows)]
    return "\n".join(lines) + "\n"


def test_builder_reads_the_copied_table():
    zips = builder.parse_tsv(_tsv() + "60622\t2340\t2490\t2810\t3610\t4130\n")
    assert zips["60622"] == [2340, 2490, 2810, 3610, 4130]
    assert len(zips) == 301


@pytest.mark.parametrize("bad", [
    "60622\t2340\t2490\t2810\t3610\n",          # a column short
    "6062\t2340\t2490\t2810\t3610\t4130\n",     # not a ZIP
    "60622\t2490\t2340\t2810\t3610\t4130\n",    # falls with bedrooms: a misaligned paste
    "60000\t1000\t1100\t1300\t1700\t1900\n",    # listed twice
])
def test_builder_refuses_a_malformed_row(bad):
    with pytest.raises(ValueError):
        builder.parse_tsv(_tsv() + bad)


def test_builder_refuses_a_partial_table():
    with pytest.raises(ValueError, match="incomplete"):
        builder.parse_tsv(_tsv(rows=50))


def test_committed_artifact_has_chicago():
    art = json.loads((builder.OUTPUT_PATH).read_text())
    assert art["fy"] == 2027 and art["bedrooms"] == ["0", "1", "2", "3", "4"]
    assert art["zips"]["60622"] == [2340, 2490, 2810, 3610, 4130]
    assert sum(z.startswith("606") for z in art["zips"]) >= 60


def test_lookup_listed_and_unlisted():
    fmr = rent.safmr_for_zip("60647")
    assert fmr.listed and fmr.fy == 2027 and fmr.by_bedroom == {"0": 2140, "1": 2270, "2": 2570, "3": 3300, "4": 3770}
    miss = rent.safmr_for_zip("99999")
    assert not miss.listed and miss.by_bedroom == {}


def test_unreadable_artifact_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(rent, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    with pytest.raises(rent.RentArtifactError):
        rent.safmr_for_zip("60622")


@pytest.mark.parametrize("raw,want", [
    ("60622", "60622"), ("60622-1234", "60622"), (60622, "60622"), (60622.0, "60622"), (2134, "02134"),
    (None, None), ("", None), ("ZIP", None), ("0", None),
])
def test_zip5(raw, want):
    assert _zip5(raw) == want


def _results(zip_code="60622", unchecked=None):
    ev = RentEvidence(unchecked=list(unchecked or []))
    return {"neighborhood": NeighborhoodSummary(rent=ev), "property": PropertySummary(pin14="1", zip_code=zip_code)}


def test_scorecard_attaches_on_a_copy():
    from backend.main import _attach_safmr

    results = _results()
    cached = results["neighborhood"]
    _attach_safmr(results)
    assert results["neighborhood"].rent.safmr.by_bedroom["2"] == 2810
    assert cached.rent.safmr is None  # the cached retrieval result is untouched


def test_scorecard_without_a_zip_attaches_nothing():
    from backend.main import _attach_safmr

    results = _results(zip_code=None)
    _attach_safmr(results)
    assert results["neighborhood"].rent.safmr is None and results["neighborhood"].rent.unchecked == []


def test_scorecard_names_an_unreadable_table(monkeypatch):
    from backend.main import _attach_safmr

    def boom(_zip):
        raise rent.RentArtifactError("gone")

    monkeypatch.setattr(rent, "safmr_for_zip", boom)
    results = _results()
    _attach_safmr(results)
    assert results["neighborhood"].rent.unchecked == ["hud_safmr"]
    assert results["neighborhood"].rent.safmr is None


def test_provenance_entry_per_bedroom():
    from backend.provenance_figures import expected_fact_ids, figure_entries

    ev = RentEvidence(safmr=rent.safmr_for_zip("60622"))
    ctx = SimpleNamespace(neighborhood=NeighborhoodSummary(rent=ev))
    entries = figure_entries(ctx, comparables=None, qd="2026-11-04", existing={})
    e = entries["area.rent.hud_safmr.2"]
    assert e["value"] == 2810 and e["scope"] == "zip" and e["geography"] == "ZIP 60622" and e["period"] == "FY 2027"
    assert e["as_of"] == "2026-10-01" and e["as_of_basis"] == "vintage" and e["method_key"] == "government_model"
    payload = {"context": {"neighborhood": {"rent": ev.model_dump()}}}
    assert {f"area.rent.hud_safmr.{b}" for b in "01234"} <= expected_fact_ids(payload)


def test_unlisted_zip_has_no_entries():
    from backend.provenance_figures import expected_fact_ids, figure_entries

    ev = RentEvidence(safmr=rent.safmr_for_zip("99999"))
    ctx = SimpleNamespace(neighborhood=NeighborhoodSummary(rent=ev))
    assert not [k for k in figure_entries(ctx, comparables=None, qd="2026-11-04", existing={}) if "hud_safmr" in k]
    assert not [k for k in expected_fact_ids({"context": {"neighborhood": {"rent": ev.model_dump()}}}) if "hud_safmr" in k]


@pytest.mark.parametrize("today,state", [
    (date(2026, 11, 4), "ok"), (date(2027, 9, 30), "ok"), (date(2027, 10, 1), "warn"), (date(2028, 4, 1), "alarm"),
])
def test_age_check_follows_hud_fiscal_year(tmp_path, today, state):
    (tmp_path / "ingestion/data").mkdir(parents=True)
    (tmp_path / "ingestion/data/hud_safmr.meta.json").write_text(json.dumps({"fy": 2027, "zips": 370, "retrieved": "2026-11-04"}))
    assert artifacts.check_hud_safmr(today, tmp_path).state == state


def test_age_check_without_sidecar_warns(tmp_path):
    assert artifacts.check_hud_safmr(date(2026, 11, 4), tmp_path).state == "warn"
