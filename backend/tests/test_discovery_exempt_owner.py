"""Who owns an exempt lot, and empty public land (decision Item 128, the owner's review of 2026-11-16)."""

from __future__ import annotations

import dataclasses
import sqlite3

import httpx
import pytest

from backend.discovery import lot_sources
from backend.discovery.lot_facts import (
    EXEMPT_OWNERS, derive_capacity, fill_building_area, land_in_use, mark_land_use, measure_bands,
)
from backend.tests.test_discovery_lot_facts import _sources

PIN10 = "1705100001"
EMPTY = {"land_kind": "exempt", "empty_land": True, "structure": "empty", "density_band": 2.2, "land_sqft": 10_000.0}


def _src(owner=None, cmap=None):
    return dataclasses.replace(_sources([], []), cmap_on_lot=cmap or {}, exempt_owner={PIN10: owner} if owner else {})


def test_a_known_owner_is_spelled_out():
    attrs = {"land_kind": "exempt", "structure": "built"}
    mark_land_use(attrs, PIN10, _src(("5", "CHICAGO HSING AUTHORTI")))
    assert attrs["exempt_owner"] == "Chicago Housing Authority"
    assert "exempt_owner_assessor" not in attrs and "public_land" not in attrs  # built: in use


def test_an_unlisted_owner_keeps_the_assessors_own_text():
    # 1301 N Mohawk: the Lincoln Park congregation of Jehovah's Witnesses, a Kingdom Hall
    attrs = {"land_kind": "exempt", "structure": "disagree"}
    mark_land_use(attrs, PIN10, _src(("4999", "LINCOLN PK CONG JEH WT")))
    assert attrs["exempt_owner"] == "LINCOLN PK CONG JEH WT" and attrs["exempt_owner_assessor"] is True


def test_a_renumbered_owner_never_borrows_another_name():
    attrs = {"land_kind": "exempt"}
    mark_land_use(attrs, PIN10, _src(("5", "SOME OTHER OWNER")))
    assert attrs["exempt_owner"] == "SOME OTHER OWNER" and attrs["exempt_owner_assessor"] is True


@pytest.mark.parametrize("num", ["229", "6875", "2336", "14"])  # ALLEY, STREET, EXPRESSWAY, EXEMPT STATUS PENDING
def test_rows_that_name_the_land_not_the_owner_show_no_owner(num):
    attrs = {"land_kind": "exempt"}
    mark_land_use(attrs, PIN10, _src((num, "ALLEY")))
    assert "exempt_owner" not in attrs


def test_empty_cha_land_is_empty_public_land_with_room_not_an_institution():
    # The Cabrini-Green land on N Clybourn: nothing stands on it
    attrs = dict(EMPTY)
    mark_land_use(attrs, PIN10, _src(("5", "CHICAGO HSING AUTHORTI"), {PIN10: ("4110", 0.9)}))
    assert attrs["public_land"] is True and "institution" not in attrs
    fill_building_area(attrs, lot=None, src=None)  # no outline: the rule still holds
    assert attrs["bldg_sqft"] == 0.0 and attrs["bldg_sqft_source"] == "public_land"
    derive_capacity(attrs)
    assert attrs["room_sqft"] == 22_000.0
    assert land_in_use(attrs) == "empty" and measure_bands(attrs)["r"] == "4"


@pytest.mark.parametrize("code, share, public", [("1350", 0.9, False), ("1321", 0.5, False), ("1350", 0.49, True)])
def test_city_land_cmap_calls_institutional_stays_an_institution(code, share, public):
    # The owner's blind check: 0 of 10 such City lots were sites (a police station's lot, a school's yard)
    attrs = dict(EMPTY)
    mark_land_use(attrs, PIN10, _src(("1", "CHICAGO CITY OF"), {PIN10: (code, share)}))
    assert attrs.get("public_land", False) is public
    assert attrs.get("institution", False) is (not public)


def test_an_empty_school_yard_stays_an_institution():
    # The Board of Education is not a public landholder here: its empty lots are mostly playgrounds and parking
    attrs = dict(EMPTY)
    mark_land_use(attrs, PIN10, _src(("7", "CHICAGO BOARD OF ED"), {PIN10: ("1321", 0.9)}))
    assert attrs["institution"] is True and "public_land" not in attrs


def test_public_landholders_are_the_city_cha_and_the_land_bank():
    assert sorted(v["name"] for v in EXEMPT_OWNERS.values() if v.get("public_land")) == [
        "Chicago Housing Authority", "City of Chicago", "Cook County Land Bank Authority"]


def test_a_rerun_clears_the_owner():
    attrs = {"land_kind": "exempt", "exempt_owner": "x", "exempt_owner_assessor": True, "public_land": True}
    mark_land_use(attrs, PIN10, _src())
    assert not {"exempt_owner", "exempt_owner_assessor", "public_land"} & attrs.keys()


def test_a_copy_without_the_table_names_no_owner(tmp_path):
    attrs = dict(EMPTY)
    mark_land_use(attrs, PIN10, dataclasses.replace(_sources([], []), exempt_owner=None))
    assert "exempt_owner" not in attrs


# --- the fetch ---------------------------------------------------------------------------------------------------

def test_fetch_keeps_the_base_pin_and_refuses_a_short_read(tmp_path, monkeypatch):
    out = tmp_path / "src.db"
    db = sqlite3.connect(out)
    db.execute("CREATE TABLE meta (name TEXT PRIMARY KEY, value TEXT)")
    db.commit()
    db.close()
    rows = [{"pin": "17051000011001", "owner_num": "4999", "owner_name": "UNIT OWNER"},
            {"pin": "17051000010000", "owner_num": "5", "owner_name": "CHICAGO HSING AUTHORTI"},
            {"pin": "17051000021001", "owner_num": "7", "owner_name": "CHICAGO BOARD OF ED"},
            {"pin": "bad", "owner_num": "1", "owner_name": "X"}]

    def handler(req: httpx.Request) -> httpx.Response:
        if "max" in req.url.params.get("$select", ""):
            return httpx.Response(200, json=[{"y": "2026.0"}])
        return httpx.Response(200, json=rows if req.url.params.get("$offset") == "0" else [])

    real = httpx.Client
    monkeypatch.setattr(lot_sources.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler)))
    with pytest.raises(RuntimeError, match="only 2 lots"):
        lot_sources.fetch_exempt(out)
    monkeypatch.setattr(lot_sources, "MIN_EXEMPT_LOTS", 2)
    assert lot_sources.fetch_exempt(out) == {"exempt_lots": 2, "exempt_year": "2026"}
    got = dict((r[0], (r[1], r[2])) for r in sqlite3.connect(out).execute("SELECT pin10, owner_num, owner_name FROM exempt_owner"))
    assert got == {"1705100001": ("5", "CHICAGO HSING AUTHORTI"), "1705100002": ("7", "CHICAGO BOARD OF ED")}
