"""F5a: the City's zoning layer already says WHEN and BY WHAT ORDINANCE a district
last changed. The product used to drop both, present an *application* number as
"the ordinance" (kit P7: 23082T1, which the chat model read as a year), and say
nothing about how current the Municipal Code text is."""

import datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.code_vintage import get_code_vintage
from backend.models import ContextObject, RECENT_REZONING_DAYS, ZoningSummary
from backend.retrieval.zoning import _epoch_ms_to_date, _zoning_result, lookup_zoning

# Real layer-1 attributes for P7 (1218 W George St), queried 2026-10-02.
P7_ATTRS = {
    "ZONE_CLASS": "RT-4", "ZONE_TYPE": 4, "ORDINANCE_NUM": "23082T1",
    "ORDINANCE_DATE": 1781568000000, "UPDATE_TIMESTAMP": 1787320889000,
    "CLERK_DOCNO": "O2026-0025358",
    "CLERK_URL": "https://chicityclerkelms.chicago.gov/Matter/?matterId=39EAE819-E452-F111-BEC6-001DD80B0E39",
}
# P2 (older, legacy ordinance id, no clerk number)
P2_ATTRS = {"ZONE_CLASS": "RM-4.5", "ZONE_TYPE": 4, "ORDINANCE_NUM": "A7210",
            "ORDINANCE_DATE": 1189000000000, "UPDATE_TIMESTAMP": 1635300000000, "CLERK_DOCNO": None, "CLERK_URL": None}


# --- reading the layer ----------------------------------------------------------------

def test_epoch_ms_dates():
    assert _epoch_ms_to_date(1781568000000) == "2026-06-16"
    assert _epoch_ms_to_date(1787320889000) == "2026-08-21"
    assert _epoch_ms_to_date(None) is None and _epoch_ms_to_date("") is None and _epoch_ms_to_date("x") is None


def test_application_number_is_not_presented_as_the_ordinance():
    r = _zoning_result(P7_ATTRS)
    assert r["application_num"] == "23082T1"
    assert r["ordinance_num"] == "O2026-0025358"  # the clerk's ordinance number
    assert (r["ordinance_date"], r["map_updated"]) == ("2026-06-16", "2026-08-21")
    assert r["clerk_url"].startswith("https://chicityclerkelms.chicago.gov/")


def test_legacy_ordinance_ids_pass_through_unchanged():
    r = _zoning_result(P2_ATTRS)
    assert r["ordinance_num"] == "A7210" and r["application_num"] is None
    assert r["clerk_url"] is None and r["ordinance_date"] == "2007-09-05"
    pd = _zoning_result({"ZONE_CLASS": "PD 835", "ORDINANCE_NUM": "13559"})
    assert pd["ordinance_num"] == "13559" and pd["application_num"] is None and pd["ordinance_date"] is None


def test_application_number_with_no_clerk_doc_leaves_no_ordinance():
    r = _zoning_result({"ZONE_CLASS": "RT-4", "ORDINANCE_NUM": "23082T1"})
    assert r["ordinance_num"] is None and r["application_num"] == "23082T1"


@pytest.mark.asyncio
async def test_lookup_zoning_asks_the_layer_for_the_date_fields_and_returns_them():
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"features": [{"attributes": P7_ATTRS}]})
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    out = await lookup_zoning(41.93458012, -87.65966119, client=client)
    asked = client.get.await_args.kwargs["params"]["outFields"]
    for f in ("ORDINANCE_DATE", "UPDATE_TIMESTAMP", "CLERK_DOCNO", "CLERK_URL"):
        assert f in asked
    assert out["ordinance_date"] == "2026-06-16" and out["application_num"] == "23082T1"


# --- recently rezoned --------------------------------------------------------------------

def _zs(days_ago: int | None) -> ZoningSummary:
    d = None if days_ago is None else (datetime.date.today() - datetime.timedelta(days=days_ago)).isoformat()
    return ZoningSummary(zone_class="RT-4", ordinance_date=d)


def test_recently_rezoned_window():
    assert _zs(0).recently_rezoned and _zs(65).recently_rezoned and _zs(RECENT_REZONING_DAYS).recently_rezoned
    assert not _zs(RECENT_REZONING_DAYS + 1).recently_rezoned
    assert not _zs(None).recently_rezoned
    assert not ZoningSummary(zone_class="RT-4", ordinance_date="garbage").recently_rezoned
    future = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
    assert not ZoningSummary(zone_class="RT-4", ordinance_date=future).recently_rezoned  # not a past event


def test_recently_rezoned_is_in_the_serialized_payload():
    assert _zs(30).model_dump(exclude_none=True)["recently_rezoned"] is True
    assert json.loads(_zs(2000).model_dump_json())["recently_rezoned"] is False


# --- code vintage -----------------------------------------------------------------------------

def test_code_vintage_is_shipped_and_parses():
    v = get_code_vintage()
    assert v["current_through"] == "2026-03-18" and v["label"] == "Council Journal of March 18, 2026"


def test_code_vintage_matches_the_export_header_when_the_export_is_present():
    from ingestion.code_vintage import SOURCE_FILE, extract_code_vintage

    if not SOURCE_FILE.exists():
        pytest.skip("export not present")
    head = SOURCE_FILE.open(encoding="utf-8").read(20_000)
    assert extract_code_vintage(head)["current_through"] == get_code_vintage()["current_through"]


def test_extract_code_vintage():
    from ingestion.code_vintage import extract_code_vintage

    got = extract_code_vintage('<div>Published by Order, 1990<br>Current through Council Journal of March 18, 2026</div>')
    assert got["current_through"] == "2026-03-18" and got["label"] == "Council Journal of March 18, 2026"
    assert extract_code_vintage("<div>no header here</div>") is None
    assert extract_code_vintage("Current through Council Journal of Smarch 99, 2026") is None


def test_missing_vintage_file_omits_the_stamp_instead_of_faking_one(tmp_path):
    import backend.code_vintage as cv

    cv.get_code_vintage.cache_clear()
    try:
        with patch.object(cv, "VINTAGE_FILE", tmp_path / "nope.json"):
            assert cv.get_code_vintage() is None
    finally:
        cv.get_code_vintage.cache_clear()


def test_context_carries_the_vintage_only_for_a_parcel_with_zoning():
    z = ZoningSummary(zone_class="B1-2", ordinance_date="2007-09-05")
    assert ContextObject(parcel_zoning=z).model_dump(exclude_none=True)["code_vintage"]["current_through"] == "2026-03-18"
    assert ContextObject().code_vintage is None


def test_prompt_rule_keeps_the_application_number_out_of_the_answer():
    from backend.prompts import SYNTHESIZER_SYSTEM

    i = SYNTHESIZER_SYSTEM.index("34. HOW CURRENT THE ZONING IS")
    rule = SYNTHESIZER_SYSTEM[i : i + 2500]
    assert "APPLICATION number" in rule and "never a year" in rule and "recently_rezoned" in rule
