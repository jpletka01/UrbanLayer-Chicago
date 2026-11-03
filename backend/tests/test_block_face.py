"""The RS-3 "60% of the block face" test (§17-2-0303-B.1; decision Item 67).

Recorded: the City's street centerlines (``pr57-gg9e``) for the whole of N Avers Ave, 2026-11-03. Its 2500 block is
two segments joined at a node that meets no street (2543/2545), which is the case the face walk must chain.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.models import BlockFaceTest
from backend.retrieval.property import block_face as bf
from backend.retrieval.zoning_definitions import max_units_by_lot_area

AVERS = json.loads((Path(__file__).parent / "fixtures" / "centerlines_n_avers_ave_2026-11-03.json").read_text())


@pytest.mark.parametrize("number, expected", [
    (2307, (2301, 2359, "W BELDEN AVE", "W FULLERTON AVE")),
    (2308, (2300, 2358, "W BELDEN AVE", "W FULLERTON AVE")),          # the other side of the same face
    (2541, (2501, 2559, "W ALTGELD ST", "W WRIGHTWOOD AVE")),        # two segments, chained through a street-less node
    (2548, (2500, 2558, "W ALTGELD ST", "W WRIGHTWOOD AVE")),
])
def test_the_face_runs_between_the_two_nearest_intersecting_streets(number, expected):
    assert bf.face_range(AVERS, number) == expected


def test_a_number_on_no_segment_has_no_face():
    assert bf.face_range(AVERS, 99999) is None


def test_the_walk_does_not_depend_on_which_way_a_segment_was_drawn():
    flipped = []
    for s in AVERS:  # reverse every segment: from/to nodes and cross streets swap, address ranges stay
        r = dict(s)
        r["fnode_id"], r["tnode_id"] = s["tnode_id"], s["fnode_id"]
        r["f_cross"], r["t_cross"] = s["t_cross"], s["f_cross"]
        r["f_cross_st"], r["t_cross_st"] = s["t_cross_st"], s["f_cross_st"]
        flipped.append(r)
    lo, hi, a, b = bf.face_range(flipped, 2541)
    assert (lo, hi) == (2501, 2559) and {a, b} == {"W ALTGELD ST", "W WRIGHTWOOD AVE"}


@pytest.mark.parametrize("address, expected", [
    ("2307 N AVERS AVE", (2307, "N", "AVERS", "AVE")),
    ("2307 N Avers Ave, Chicago, IL 60647", (2307, "N", "AVERS", "AVE")),
    ("2400 N KEDZIE BLVD", (2400, "N", "KEDZIE", "BLVD")),
    ("1600 N LA SALLE DR", (1600, "N", "LA SALLE", "DR")),
    ("~2301 N AVERS AVE", None),       # an approximate stand-in address is never a lot's own
    ("Avers and Fullerton", None),
])
def test_addresses_split_into_number_direction_name_and_type(address, expected):
    assert bf.split_address(address) == expected


@pytest.mark.parametrize("cls, chars, condo, units", [
    ("2-11", {"char_apts": "Two", "pin_num_cards": "1"}, False, 2),
    ("2-03", {"char_apts": "None", "pin_num_cards": "1"}, False, 1),
    ("2-03", {"char_apts": "None", "pin_num_cards": "2"}, False, None),   # a second building the field doesn't count
    ("2-03", {"char_apts": ""}, False, None),
    ("2-99", None, False, 2),                                            # condominium building
    ("2-03", None, True, 2),                                             # unit PINs on the PIN10
    ("3-15", None, False, 2),
    ("1-00", None, False, 0),
    ("2-05", None, False, None),
])
def test_units_from_the_assessors_record(cls, chars, condo, units):
    assert bf.units_from_record(cls, chars, condo=condo) == units


@pytest.mark.parametrize("units, state", [
    ([2, 2, 1], "not_computable"),                              # under four lots
    ([2] * 8 + [None, None], "not_computable"),                 # 80% with a count, under the 90% gate
    ([2] * 6 + [1] * 4, "met"),                                 # exactly 60%
    ([2] * 5 + [1] * 5, "not_met"),
    ([2] * 11 + [1] * 7 + [None], "not_met"),                  # 11 of 19: an unknown lot counts as not two-plus
])
def test_the_gate_and_the_60_percent_rule(units, state):
    assert bf.judge(units)[0] == state


def _face(state: str, **kw) -> BlockFaceTest:
    base = dict(lots=14, counted=14, two_plus=11, street="N AVERS AVE", side="even",
                from_number=2400, to_number=2458, from_street="W FULLERTON AVE", to_street="W ALTGELD ST")
    base.update(kw)
    return BlockFaceTest(state=state, **base)


def test_a_met_face_opens_the_two_unit_path_on_a_3000_sq_ft_lot():
    uy = max_units_by_lot_area("RS-3", 3125, in_606=False, block_face=_face("met"))
    assert uy["base_units"] == 1 and uy["units"] == 2 and uy["rule_block_face"] == "met"
    assert "11 of 14 lots" in uy["arithmetic"] and "W FULLERTON AVE to W ALTGELD ST" in uy["arithmetic"]
    assert "lawfully improved is not on record" in uy["arithmetic"]


def test_a_met_face_never_gives_a_single_unit_or_lowers_a_bigger_lot():
    assert max_units_by_lot_area("RS-3", 2800, in_606=False, block_face=_face("met"))["units"] == 1
    assert max_units_by_lot_area("RS-3", 7500, in_606=False, block_face=_face("met"))["units"] == 3


def test_a_face_that_is_not_met_or_not_computable_keeps_the_base_number_and_says_why():
    nm = max_units_by_lot_area("RS-3", 3125, in_606=False, block_face=_face("not_met", two_plus=5))
    assert nm["units"] == 1 and "5 of 14 lots" in nm["arithmetic"] and "under the 60%" in nm["arithmetic"]
    nc = max_units_by_lot_area("RS-3", 3125, in_606=False, block_face=_face("not_computable", counted=9))
    assert nc["units"] == 1 and "too few lots with a unit count" in nc["arithmetic"]


def test_an_unchecked_face_says_so_in_the_caveat():
    uy = max_units_by_lot_area("RS-3", 3125, in_606=False, block_face=BlockFaceTest(state="unchecked"))
    assert uy["units"] == 1 and uy["rule_block_face"] == "unchecked" and "could not check the block-face rule" in uy["caveat"]


def test_only_rs3_reads_the_block_face():
    uy = max_units_by_lot_area("RT-4", 3125, block_face=_face("met"))
    assert uy["rule_block_face"] is None and "block face" not in uy["arithmetic"]


@pytest.mark.asyncio
async def test_a_failed_source_raises_and_caches_nothing():
    with patch("backend.retrieval.property.block_face.socrata_get", AsyncMock(side_effect=RuntimeError("down"))) as soc:
        for _ in range(2):
            with pytest.raises(bf.BlockFaceError, match="centerlines"):
                await bf.block_face_test("2307 N AVERS AVE")
    assert soc.call_count == 2


@pytest.mark.asyncio
async def test_an_empty_discovery_index_is_not_checked_never_no_lots():
    from backend.discovery import parcel_source

    with patch("backend.retrieval.property.block_face.socrata_get", AsyncMock(return_value=AVERS)), \
            patch.object(parcel_source, "current_version", return_value=parcel_source.EMPTY_VERSION), \
            pytest.raises(bf.BlockFaceError, match="empty"):
        await bf.block_face_test("2307 N AVERS AVE")


@pytest.mark.asyncio
async def test_the_lots_come_from_every_district_on_the_face_and_units_from_the_index_first():
    from backend.discovery import parcel_source

    rows = [
        (2301, "13-26-300-001-0000", {"class": "2-11", "units": 2, "zone_class": "RS-3"}),
        (2305, "13-26-300-002-0000", {"class": "2-11", "units": 3, "zone_class": "RS-3"}),
        (2309, "13-26-300-003-0000", {"class": "2-11", "units": 2, "zone_class": "B3-1"}),  # another district counts
        (2313, "13-26-300-004-0000", {"class": "2-03", "zone_class": "RS-3"}),             # no units: ask the Assessor
        (2317, "13-26-300-005-0000", {"class": "2-11", "units": 2, "zone_class": "RS-3"}),
        (2306, "13-26-300-006-0000", {"class": "2-11", "units": 2, "zone_class": "RS-3"}),  # the other side: out
        (2401, "13-26-300-007-0000", {"class": "2-11", "units": 2, "zone_class": "RS-3"}),  # the next face: out
    ]
    chars = [{"pin": "13263000040000", "year": "2025", "char_apts": "None", "pin_num_cards": "1"}]
    calls = []

    async def fake(dataset, params, **kw):
        calls.append(dataset)
        return AVERS if dataset == bf.DATASET_CENTERLINES else chars

    with patch("backend.retrieval.property.block_face.socrata_get", fake), \
            patch.object(parcel_source, "current_version", return_value="v-test"), \
            patch.object(bf, "street_index", return_value={("N", "AVERS", "AVE"): rows}):
        result = await bf.block_face_test("2307 N AVERS AVE")
    assert (result.lots, result.counted, result.two_plus, result.state) == (5, 5, 4, "met")
    assert (result.from_number, result.to_number, result.side) == (2301, 2359, "odd")
    assert calls.count("x54s-btds") == 1  # one Assessor query, only for the lot the index couldn't count


def test_the_report_names_the_trigger_that_raised_the_number():
    from backend.models import ContextObject, PropertySummary, ReportData, ZoningSummary
    from backend.report_builder import _compute_unit_yield

    ctx = ContextObject(parcel_zoning=ZoningSummary(zone_class="RS-3"), property=PropertySummary(land_sqft=3125),
                        block_face=_face("met"))
    uy = _compute_unit_yield(ReportData(address="2446 N Avers Ave", context=ctx))
    assert uy["units"] == 2 and uy["raised_by_block_face"] is True and uy["raised_by_606"] is False
