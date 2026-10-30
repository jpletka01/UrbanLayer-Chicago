"""WS1 M5: the rezoning-title parser, pinned to the 352 titles recorded from the Clerk on 2026-10-21.

The rule under test is "never guess": a title the parser can't fully account for is partial and
gets no parcel flag. Gate (plan §6.4): at least 95% parse clean; the rest are listed here by name.
"""

import json
from pathlib import Path

import pytest

from backend.legislation.address_titles import name_candidates, parse_title, side_of

FIXTURE = Path(__file__).parent / "fixtures" / "clerk" / "rezonings_2025-10-21.json"
TITLES = [m for m in json.loads(FIXTURE.read_text())["matters"]]

# The titles that cannot be read, and why. Anything new here is a decision, not a drift.
NOT_CLEAN = {
    "SO2025-0020963": "unknown street type",           # "W Fulton Market" has no type word
    "O2025-0021692": "reversed range",                 # "1236-1230 W 105th"
    "O2026-0025379": "fused number",                   # "36333701"
    "O2026-0025380": "fused number",                   # "34013551"
    "SO2025-0018864": "reversed range",                # "7600-7400 S Kostner"
    "O2026-0026168": "suspect street name",            # "124-130 E 75t St"
}


def _segs(title):
    p = parse_title(title)
    return p, [(s.dir, s.name, s.type, s.lo, s.hi, s.side) for s in p.segments]


def test_at_least_95_percent_of_recorded_titles_parse_clean():
    results = {m["record"]: parse_title(m["title"]) for m in TITLES}
    clean = sum(1 for p in results.values() if p.status == "clean")
    assert len(results) == 352
    assert clean / len(results) >= 0.95, f"{clean}/{len(results)} clean"
    assert {r for r, p in results.items() if p.status != "clean"} == set(NOT_CLEAN)


@pytest.mark.parametrize("record,why", sorted(NOT_CLEAN.items()))
def test_each_unreadable_title_says_why_and_never_guesses(record, why):
    title = next(m["title"] for m in TITLES if m["record"] == record)
    p = parse_title(title)
    assert p.status in ("partial", "unparsed")
    assert why in " ".join(p.notes)
    # nothing the parser could not read became a segment: a fused number is not split, "75t" is not repaired
    assert all(s.hi - s.lo < 2500 for s in p.segments)
    assert not any(s.name in ("75T", "75TH") for s in p.segments)


def test_every_clean_title_yields_a_segment_with_a_valid_range_and_type():
    for m in TITLES:
        p = parse_title(m["title"])
        if p.status != "clean":
            continue
        assert p.segments, m["record"]
        for s in p.segments:
            assert 0 < s.lo <= s.hi, (m["record"], s)
            assert s.dir in "NSEW" and s.type and s.name, (m["record"], s)


def test_a_simple_title():
    p, segs = _segs("Zoning Reclassification Map No. 7-H at 2328-2334 W Montana St. - App No. 23167T1")
    assert p.status == "clean" and p.maps == "7-H" and p.app_no == "23167T1"
    assert segs == [("W", "MONTANA", "ST", 2328, 2334, "even")]


def test_two_ranges_share_the_street_that_follows():
    _, segs = _segs("Zoning Reclassification Map No. 5-G at 1300-1422 and 1301-1511 W Cortland St - App No. A-1")
    assert segs == [("W", "CORTLAND", "ST", 1300, 1422, "even"), ("W", "CORTLAND", "ST", 1301, 1511, "odd")]


def test_a_list_across_streets_with_commas_slashes_and_and():
    p, segs = _segs("Zoning Reclassification Map No. 3-G at 1415 N Dayton St, 811 W Evergreen Ave, 821 W Eastman St and "
                    "1415 N Kingsbury St/1300 N Halsted St - App No. 22987")
    assert p.status == "clean"
    assert [(s[0], s[1], s[3]) for s in segs] == [
        ("N", "DAYTON", 1415), ("W", "EVERGREEN", 811), ("W", "EASTMAN", 821), ("N", "KINGSBURY", 1415), ("N", "HALSTED", 1300)]


def test_several_map_numbers_and_the_map_no_with_dash_at():
    p = parse_title("Zoning Reclassification Map Nos. 18-B and 20-B at 2900-3032 E 79th St - App No. A-9122")
    assert p.maps == "18-B and 20-B" and p.status == "clean"
    p = parse_title("Zoning Reclassification Map No. 16-C-at 1834-2126 E 71st St, 7109-7129 S Bennet Ave - App No. A-9141")
    assert p.maps == "16-C" and [s.name for s in p.segments] == ["71ST", "BENNET"]


def test_app_number_variants():
    for tail, app in [("St- App No. 23009T1", "23009T1"), ("St App No. A-8925", "A-8925"), ("St - A-9059", "A-9059"),
                      ("St - App No. 22636", "22636")]:
        p = parse_title(f"Zoning Reclassification Map No. 1-A at 10 N Foo {tail}")
        assert p.status == "clean" and p.app_no == app, tail


def test_street_names_with_a_comma_or_a_full_type_word():
    p, segs = _segs("Zoning Reclassification Map No. 9-A at 4100 S Dr. Martin Luther King, Jr. Dr - App No. 1")
    assert segs == [("S", "DR MARTIN LUTHER KING JR", "DR", 4100, 4100, "both")]
    assert "DOCTOR MARTIN LUTHER KING JR" in name_candidates(segs[0][1])
    _, segs = _segs("Zoning Reclassification Map No. 22-F at 634-724 W 95th Street - App No. A-9071")
    assert segs[0][1:3] == ("95TH", "ST")


def test_a_aka_adds_the_second_address_of_the_same_land():
    _, segs = _segs("Zoning Reclassification Map No. 1-A at 10 N Foo St a.k.a. 12 N Foo St - App No. 1")
    assert [s[3] for s in segs] == [10, 12]


def test_fused_numbers_and_typos_are_flagged_never_repaired():
    p = parse_title("Zoning Reclassification Map No. 4-J at 3600-3732 and 36333701 W 16th St - App No. A-9108")
    assert p.status == "partial" and [s.lo for s in p.segments] == [3600] and "fused number" in p.notes[0]
    p = parse_title("Zoning Reclassification Map No. 18-E at 124-130 E 75t St - App No. 23105T1")
    assert p.segments == [] and "suspect street name" in p.notes[0]


def test_text_the_parser_cannot_account_for_makes_it_partial():
    p = parse_title("Zoning Reclassification Map No. 1-A at 10 N Foo St and the vacated alley - App No. 1")
    assert p.status == "partial" and any("unparsed text" in n for n in p.notes)


def test_a_title_that_is_not_a_reclassification_is_unparsed():
    assert parse_title("Amendment of Municipal Code Section 17-2-0304").status == "unparsed"
    assert parse_title("").status == "unparsed"


@pytest.mark.parametrize("lo,hi,side", [
    (2328, 2334, "even"), (2329, 2335, "odd"), (2328, 2335, "both"), (2330, 2330, "both"), (1, 3, "odd"),
])
def test_parity_rule(lo, hi, side):
    assert side_of(lo, hi) == side


def test_ordinal_words_and_digits_are_both_tried():
    assert name_candidates("FIFTH") == ["FIFTH", "5TH"]
    assert name_candidates("5TH") == ["5TH", "FIFTH"]
    assert name_candidates("ST LAWRENCE") == ["ST LAWRENCE", "SAINT LAWRENCE"]
    assert name_candidates("95TH") == ["95TH"]


def test_the_two_acceptance_parcels_titles():
    """6711 S Western Ave is covered by O2026-0028350 (Oct 14, off the map on 2026-10-21); 1218 W George
    St by O2026-0025358 (June, on the map). The titles parse the way the Profile's matching needs."""
    by = {m["record"]: m for m in TITLES}
    western = parse_title(by["O2026-0028350"]["title"])
    assert [(s.dir, s.name, s.type, s.lo, s.hi, s.side) for s in western.segments] == [("S", "WESTERN", "AVE", 6701, 6731, "odd")]
    assert by["O2026-0028350"]["on_map_2026_10_21"] is False
    george = parse_title(by["O2026-0025358"]["title"])
    assert george.status == "clean" and by["O2026-0025358"]["on_map_2026_10_21"] is True
    assert any(s.name == "GEORGE" and s.lo <= 1218 <= s.hi for s in george.segments)
