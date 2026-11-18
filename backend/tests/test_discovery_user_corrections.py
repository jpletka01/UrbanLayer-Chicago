"""Reviewed user reports applied to a lot's building area (decision Item 129, PR 5): only over the footprint estimate
or a lot with no figure, never over the Assessor, public land or the City's land inventory; the committed file's
validation; the row the card reads; the data-health probe. No network."""

from __future__ import annotations

import asyncio
import json

import numpy as np
import shapely
from shapely.geometry import box
from shapely.strtree import STRtree

from backend.data_health import probes
from backend.data_health.registry import BY_ID
from backend.discovery import user_corrections as uc
from backend.discovery.lot_facts import LotSources, fill_building_area
from backend.discovery.lot_sources import area_sqft

FT_LAT = 1 / 364_600
FT_LON = 1 / 271_700
LOT = box(-87.70, 41.84, -87.70 + 25 * FT_LON, 41.84 + 125 * FT_LAT)
HOUSE = box(-87.70 + 3 * FT_LON, 41.84 + 10 * FT_LAT, -87.70 + 22 * FT_LON, 41.84 + 70 * FT_LAT)  # 19 x 60 ft
PIN10 = "1433103011"


def _sources(footprints=(), city_land=frozenset()):
    geoms = np.array([g for g, _ in footprints], dtype=object)
    reps = shapely.point_on_surface(geoms) if len(geoms) else np.array([], dtype=object)
    return LotSources(
        fp_tree=STRtree(reps), fp_geoms=geoms, fp_points=reps,
        fp_stories=[s for _, s in footprints], fp_area=[area_sqft(g) for g, _ in footprints],
        pt_tree={}, area_tree=None, meta={}, city_land=frozenset(city_land),
    )


def _report(**over):
    return {PIN10: {"stories": 3, "empty": False, "reviewed": "2026-11-18", "report_ids": [4], "what": "3 stories", **over}}


def _fill(attrs, src, reports, **kw):
    fill_building_area(attrs, lot=LOT, src=src, pin10=PIN10, user_corrections=reports, **kw)
    return attrs


class TestPrecedence:
    def test_reviewed_stories_replace_the_footprint_estimate(self):
        src = _sources([(HOUSE, 2)])
        est = _fill({"land_sqft": 3_125.0}, src, {})
        assert est["bldg_sqft_source"] == "footprint" and abs(est["bldg_sqft"] - 19 * 60 * 2) < 30
        got = _fill({"land_sqft": 3_125.0}, src, _report(stories=3))
        assert got["bldg_sqft_source"] == "user_report_reviewed"
        assert abs(got["bldg_sqft"] - 19 * 60 * 3) < 40
        assert got["user_report"] == {"stories": 3, "reviewed": "2026-11-18"}

    def test_a_footprint_with_no_stories_on_record_gets_its_area_from_the_report(self):
        src = _sources([(HOUSE, None)])
        assert "bldg_sqft" not in _fill({"land_sqft": 3_125.0}, src, {})  # the estimate is withheld
        got = _fill({"land_sqft": 3_125.0}, src, _report(stories=4))
        assert got["bldg_sqft_source"] == "user_report_reviewed" and abs(got["bldg_sqft"] - 19 * 60 * 4) < 50

    def test_no_building_now_gives_zero_over_the_estimate(self):
        got = _fill({"land_sqft": 3_125.0}, _sources([(HOUSE, 2)]), _report(stories=None, empty=True))
        assert got["bldg_sqft"] == 0.0 and got["bldg_sqft_source"] == "user_report_reviewed"
        assert got["user_report"] == {"empty": True, "reviewed": "2026-11-18"}

    def test_the_assessor_commercial_records_and_public_land_always_win(self):
        from backend.retrieval.property.commercial_artifact import UnitArea

        src = _sources([(HOUSE, 2)])
        a = _fill({"bldg_sqft": 2_400.0}, src, _report(stories=9))
        assert a == {"bldg_sqft": 2_400.0, "bldg_sqft_source": "assessor"}
        a = _fill({}, src, _report(stories=9), commercial=UnitArea(9_000.0, ("x",), "2024"))
        assert a == {"bldg_sqft": 9_000.0, "bldg_sqft_source": "commercial_valuation"}
        a = _fill({"public_land": True}, src, _report(stories=9))
        assert a["bldg_sqft_source"] == "public_land" and a["bldg_sqft"] == 0.0
        a = _fill({"is_vacant": True}, src, _report(stories=9))  # the Assessor's vacant class: no building to report
        assert "bldg_sqft" not in a and "user_report" not in a

    def test_the_citys_land_inventory_wins_over_no_building_now(self):
        got = _fill({}, _sources([], city_land={PIN10}), _report(stories=None, empty=True))
        assert got["bldg_sqft_source"] == "city_land_inventory" and "user_report" not in got

    def test_stories_with_no_footprint_to_measure_change_nothing_and_say_why(self):
        got = _fill({}, _sources([]), _report(stories=3))
        assert "bldg_sqft" not in got and got["user_report_unapplied"] == "no_footprint"
        big = LOT.buffer(20 * FT_LON)
        got = _fill({"land_sqft": area_sqft(LOT)}, _sources([(big, 4)]), _report(stories=3))
        assert "bldg_sqft" not in got and got["user_report_unapplied"] == "spans_lots"

    def test_another_lots_report_is_ignored(self):
        got = _fill({"land_sqft": 3_125.0}, _sources([(HOUSE, 2)]), {"9999999999": _report()[PIN10]})
        assert got["bldg_sqft_source"] == "footprint"


class TestTheFile:
    def test_validation(self):
        ok = _report()[PIN10]
        assert uc.validate_user_correction(PIN10, ok) is None
        assert uc.validate_user_correction(PIN10, {**ok, "stories": None, "empty": True}) is None
        bad = [
            ("123", ok), (PIN10, "x"), (PIN10, {**ok, "stories": 0}), (PIN10, {**ok, "stories": 151}),
            (PIN10, {**ok, "stories": True}), (PIN10, {**ok, "empty": True}), (PIN10, {**ok, "stories": None}),
            (PIN10, {**ok, "reviewed": "Nov 18"}), (PIN10, {**ok, "report_ids": []}), (PIN10, {**ok, "report_ids": ["4"]}),
        ]
        for pin10, entry in bad:
            assert uc.validate_user_correction(pin10, entry), (pin10, entry)

    def test_load_skips_unsound_entries_and_notes(self, tmp_path):
        p = tmp_path / "user_corrections.json"
        assert uc.load_user_corrections(p) == {}  # no file yet
        p.write_text(json.dumps({"_note": "header", PIN10: _report()[PIN10], "1700000000": {"stories": 0}}))
        assert list(uc.load_user_corrections(p)) == [PIN10]

    def test_the_export_writes_what_the_loader_reads(self):
        # The queue's export (backend/corrections.py) writes {stories, empty, reviewed, report_ids, what}.
        exported = {"stories": None, "empty": True, "reviewed": "2026-11-18", "report_ids": [7, 9], "what": "no building"}
        assert uc.validate_user_correction(PIN10, exported) is None


class TestRowAndProbe:
    def test_the_row_carries_the_report_only_when_it_set_the_area(self):
        from backend.discovery import api as discovery_api
        from backend.discovery.parcel import DictParcel

        sort_field = discovery_api.load_registry().sort_field("lot_size")
        row = discovery_api._row_from_parcel(DictParcel(PIN10 + "0000", {
            "bldg_sqft": 3_420.0, "bldg_sqft_source": "user_report_reviewed", "user_report": {"stories": 3, "reviewed": "2026-11-18"},
        }), sort_field)
        assert row.user_report == {"stories": 3, "reviewed": "2026-11-18"}
        row = discovery_api._row_from_parcel(DictParcel(PIN10 + "0000", {
            "bldg_sqft": 2_400.0, "bldg_sqft_source": "assessor", "user_report": {"stories": 3, "reviewed": "2026-11-18"},
        }), sort_field)
        assert row.user_report is None

    def _probe(self, monkeypatch, tmp_path, content):
        p = tmp_path / "user_corrections.json"
        if content is not None:
            p.write_text(json.dumps(content))
        monkeypatch.setattr(uc, "USER_CORRECTIONS_FILE", p)
        monkeypatch.setattr(uc.read_raw, "__defaults__", (p,))
        ctx = type("Ctx", (), {"today": None})()
        return asyncio.run(probes.probe_user_corrections(BY_ID["internal.user_corrections"], ctx))

    def test_probe_no_file_yet_is_quiet(self, monkeypatch, tmp_path):
        res = self._probe(monkeypatch, tmp_path, None)
        assert res.findings == [] and res.info == "no reviewed user reports yet"

    def test_probe_counts_and_alarms_on_an_entry_it_cant_apply(self, monkeypatch, tmp_path):
        good = _report()[PIN10]
        res = self._probe(monkeypatch, tmp_path, {
            PIN10: good, "1700000000": {**good, "stories": None, "empty": True, "reviewed": "2026-11-17"},
            "1800000000": {**good, "stories": 0},
        })
        assert res.info == "2 lots (1 with stories, 1 with no building), newest reviewed 2026-11-18"
        assert [f.level for f in res.findings] == ["alarm"] and "1800000000" in res.findings[0].text

    def test_probe_warns_past_the_size_bound(self, monkeypatch, tmp_path):
        monkeypatch.setattr(uc, "MAX_ENTRIES", 1)
        good = _report()[PIN10]
        res = self._probe(monkeypatch, tmp_path, {PIN10: good, "1700000000": good})
        assert [f.level for f in res.findings] == ["warn"]
