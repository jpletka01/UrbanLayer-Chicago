"""Tests for the parcel-kit scorer (eval/parcel_kit.py).

No network and no models. The recorded 2026-10-01 runs in eval/kit/baseline are
the fixtures: the replay tests pin the totals published in the research notes,
so a change to a scorer or to the key that moves a published number fails here
instead of silently rewriting the benchmark.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest

from eval import parcel_kit as k

BASELINE = Path(k.KIT_DIR) / "baseline" / "2026-10-01"
KEY = k.load_key()
BY_ID = {p["id"]: p for p in KEY["parcels"]}


# --- the key -----------------------------------------------------------------

def test_key_shape():
    assert [p["id"] for p in KEY["parcels"]] == [f"P{i}" for i in range(1, 8)]
    for p in KEY["parcels"]:
        assert p["scored"] == (["A", "B", "C", "D", "E", "F"] if p["id"] in ("P3", "P5") else ["A", "B", "C", "D", "F"])
        for fld in p["scored"]:
            assert fld in p, (p["id"], fld)


def test_every_pattern_compiles():
    for p in KEY["parcels"]:
        for fld in ("B", "E", "F"):
            for surface in k.SURFACES:
                rub = (p.get(fld) or {}).get(surface) or {}
                pats = [x for g in rub.get("groups", []) + rub.get("partial", []) for x in g]
                pats += rub.get("wrong", []) + rub.get("forbid", [])
                for pat in pats:
                    re.compile(pat)
    for pat in k.CHAT_OVERLAY_PATTERNS.values():
        re.compile(pat)


def test_prompt_is_the_standard_prompt():
    msg = k.build_prompt(KEY, BY_ID["P2"])
    assert "1256 N Artesian Ave" in msg and "could I build 6 units" in msg
    assert msg.count("(6)") == 1 and msg.endswith("what you could not determine.")


# --- text helpers --------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,want",
    [("RS-3", "RS3"), ("rm 4.5", "RM4.5"), ("PD 835", "PD835"), ("Planned Development No. 835", "PD835"), ("B1-2", "B12")],
)
def test_norm_district(raw, want):
    assert k.norm_district(raw) == want


def test_first_district_takes_the_claim_not_a_neighbour():
    assert k.first_district("This parcel is zoned **RM-4.5**, next to RS-3.") == "RM4.5"
    assert k.first_district("no district here") is None
    assert k.first_district("rezoned from M1-2 to RT-4") == "M12"


def test_split_sections_needs_sequential_headings():
    text = "intro\n## 1. Zoning\na\n## 2. Use\nb\n### 3. Bulk\nc\n1. a list item\n## 6. Task\nz"
    secs = k.split_sections(text)
    assert secs[1].startswith("## 1.") and "b" in secs[2] and "a list item" in secs[3]
    assert 4 not in secs and 5 not in secs  # a stray "1." list item never opens a section


def test_field_text_falls_back_to_whole_answer_without_structure():
    assert k.field_text({}, "plain answer", "C") == "plain answer"
    secs = {1: "one", 2: "two", 3: "three"}
    assert k.field_text(secs, "x", "C") == "three"
    assert k.field_text(secs, "x", "F") == ""  # item 6 never written -> NP, not a guess


def test_chat_numbers_reads_the_district_standard_not_the_parcel_or_coach_house():
    text = (
        "- **FAR:** 1.7 per 17-2-0304\n"
        "- **Maximum building height:** 45 ft\n"
        "- **Minimum lot area per dwelling unit:** 700 sq ft. The parcel's land area is **3,075 sq ft**.\n"
        "- **Coach house height:** Max 22 ft building height\n"
    )
    got = k.chat_numbers(text)
    assert got["far"] == [1.7]
    assert got["height_ft"] == [45.0]
    assert got["mla"] == [700.0]


def test_chat_numbers_does_not_invent_a_far_from_a_section_number():
    assert k.chat_numbers("Specific FAR limits are in § 17-2-0300 and were not retrieved.")["far"] == []


def test_chat_numbers_skips_reference_lines_and_marks_hedged_guesses():
    text = (
        "- **Minimum lot area per unit (RS-3 reference):** a floor of 1,500 sq ft per unit\n"
        "- **FAR:** the base FAR is typically **3.0**, but I cannot confirm it\n"
        "- Implied FAR (actual, for reference only): approximately **26.6x**\n"
    )
    got = k.chat_numbers(text)
    assert got["mla"] == [] and got["far"] == [3.0] and got["far_hedged"] == [3.0]
    # a hedged wrong number is a 0, not a confident-wrong
    assert k.score_numbers([{"name": "far", "accept": [2.2], "tol": 0.05}], got)[:2] == (0, False)
    unhedged = {"far": [3.0], "far_hedged": []}
    assert k.score_numbers([{"name": "far", "accept": [2.2], "tol": 0.05}], unhedged)[:2] == (0, True)


# --- overlays ------------------------------------------------------------------

def test_chat_overlays_table_rows_and_prose():
    text = (
        "| **Planned Development** | ❌ No | — |\n"
        "| **Affordable Requirements Ordinance (ARO) Zone** | ✅ **YES** | applies |\n"
        "| **Transit-Oriented Development (TOD) Area** | ❌ No | No TOD bonus |\n"
        "- **No Special Service Area (SSA):** not within an SSA.\n"
        "- **Landmark:** this is an individual Chicago Landmark.\n"
        "TOD eligibility does not apply here.\n"
    )
    asserted, denied = k.chat_overlays(text)
    assert asserted == {"aro", "landmark_building"}
    assert {"pd", "tod", "ssa"} <= denied


def test_chat_overlays_negation_covers_a_list_and_process_mentions_are_not_overlays():
    text = (
        "- **No Planned Development, Landmark, Historic District, Lakefront Protection, or PMD overlays apply.**\n"
        "A zoning entitlement (map amendment, planned development, or ARO-triggering approval) triggers set-asides.\n"
        "Transit-served sites must meet pedestrian-street design standards.\n"
        "- **TOD eligibility** requires proximity within a threshold; this parcel does not meet it.\n"
    )
    asserted, denied = k.chat_overlays(text)
    assert not ({"pd", "landmark_building", "historic_district", "lakefront", "pmd", "pedestrian_street"} & asserted)
    assert {"pd", "lakefront", "pmd", "tod"} <= denied


def test_chat_overlays_denial_reasons_and_parenthetical_examples():
    text = (
        "- **No Transit-Oriented Development (TOD) designation**: not in a TOD area. These distances exceed the TOD threshold.\n"
        "ARO applies to projects needing an entitlement (map amendment, special use, or planned development).\n"
    )
    asserted, denied = k.chat_overlays(text)
    assert "tod" not in asserted and "tod" in denied
    assert "pd" not in asserted


def test_chat_overlays_none_after_a_parenthetical_and_setbacks_are_not_heights():
    asserted, denied = k.chat_overlays("- **Special Service Area (SSA):** None.\n")
    assert "ssa" not in asserted and "ssa" in denied
    text = "- Maximum building height: set by the PD ordinance.\n- Rear setbacks of 30 feet apply to floors with dwelling units.\n"
    assert k.chat_numbers(text)["height_ft"] == []


def test_score_overlays_rules():
    assert k.score_overlays(["tod", "aro"], {"tod", "aro", "adu"}, set())[:2] == (2, False)  # ADU is never "false"
    score, cw, detail = k.score_overlays(["tod", "aro", "ssa"], {"tod", "aro"}, {"ssa"})
    assert (score, cw) == (1, True) and "denied ssa" in detail
    assert k.score_overlays(["landmark_building"], {"pedestrian_street"}, set())[:2] == (0, True)


# --- numbers -------------------------------------------------------------------

NUMS = [
    {"name": "far", "accept": [1.7], "tol": 0.05},
    {"name": "height_ft", "accept": [45, 47], "tol": 2},
    {"name": "mla", "accept": [700], "tol": 10},
]


def test_score_numbers():
    assert k.score_numbers(NUMS, {"far": [1.7], "height_ft": [45.0, 47.0], "mla": [700.0]})[:2] == (2, False)
    assert k.score_numbers(NUMS, {"far": [1.7], "height_ft": [], "mla": []})[:2] == (1, False)  # partial
    assert k.score_numbers(NUMS, {"far": [], "height_ft": [], "mla": []})[:2] == (None, False)  # NP
    assert k.score_numbers(NUMS, {"far": [1.7], "mla": [2500.0, 1500.0]})[:2] == (0, True)  # a wrong MLA wins


def test_profile_numbers_reads_ranges_and_never_mistakes_min_lot_for_mla():
    spec = [{"name": "mla", "profile_fields": ["min_lot_area_per_unit"]}]
    resp = {"zone_definition": {"far": 1.7, "max_height": "45–47 ft (varies by lot frontage)", "min_lot_sqft": 1650}}
    assert k.profile_numbers(resp, spec) == {"far": [1.7], "height_ft": [45.0, 47.0], "mla": []}
    resp["zone_definition"]["min_lot_area_per_unit"] = 700
    assert k.profile_numbers(resp, spec)["mla"] == [700.0]


# --- phrase rubrics --------------------------------------------------------------

def test_score_phrases_semantics():
    rub = {"groups": [["above"], ["special use"]], "none": "NP"}
    assert k.score_phrases(rub, "residential above, ground floor is a special use")[:2] == (2, False)
    assert k.score_phrases(rub, "residential above only")[:2] == (1, False)
    assert k.score_phrases(rub, "nothing relevant")[:2] == (None, False)
    assert k.score_phrases({**rub, "none": "0"}, "nothing relevant")[:2] == (0, False)
    assert k.score_phrases({**rub, "wrong": ["nothing"]}, "nothing relevant")[:2] == (0, True)
    forbid = {"groups": [["parking"]], "forbid": [r"(?<!no )density bonus"]}
    assert k.score_phrases(forbid, "reduced parking and a density bonus")[:2] == (1, True)
    assert k.score_phrases(forbid, "parking relief, no density bonus")[:2] == (2, False)
    assert k.score_phrases(None, "x")[0] is None


def test_hand_score_parsing():
    assert k.parse_hand_score("2") == (2, False)
    assert k.parse_hand_score("0CW") == (0, True)
    assert k.parse_hand_score("1 CW") == (1, True)
    assert k.parse_hand_score("NP") == (None, False)


# --- aggregation -----------------------------------------------------------------

def _fr(score, cw=False):
    return k.FieldResult(score, cw)


def test_aggregate_and_screening_grade():
    per = {"P1": {"A": _fr(2), "B": _fr(1), "C": _fr(None)}, "P2": {"A": _fr(0, True), "B": _fr(2)}}
    agg = k.aggregate(per, n_scored=6)
    assert (agg["answered"], agg["points"], agg["possible"]) == (4, 5, 8)
    assert agg["critical_misses"] == ["P2"] and agg["cw"] == 1 and agg["a_correct"] == 1
    assert agg["coverage"] == pytest.approx(4 / 6)
    assert not k.screening_grade(agg, per)
    clean = {"P1": {"A": _fr(2), "B": _fr(2)}}
    assert k.screening_grade(k.aggregate(clean, 2), clean)


# --- replay of the recorded 2026-10-01 runs -----------------------------------------

@pytest.fixture(scope="module")
def baseline():
    manual = json.loads((BASELINE / "manual_scores.json").read_text())
    return k.score_run_dir(BASELINE, KEY, k.SURFACES, None, manual, "BEF")


def test_baseline_profile_totals_reproduce(baseline):
    a = baseline["surfaces"]["profile"]["aggregate"]
    assert (a["answered"], a["scored_fields"]) == (32, 37)  # coverage 86%
    assert (a["points"], a["possible"]) == (51, 64)  # accuracy 80%
    assert a["cw"] == 2 and a["critical_misses"] == [] and a["a_correct"] == 7
    assert a["screening_grade"] is False  # misses by a hair, as published


def test_baseline_chat_totals_reproduce(baseline):
    a = baseline["surfaces"]["chat"]["aggregate"]
    assert (a["answered"], a["scored_fields"]) == (28, 37)  # coverage 76%
    assert (a["points"], a["possible"]) == (38, 56)  # accuracy 68%
    assert a["cw"] == 7 and a["critical_misses"] == ["P2", "P5"] and a["a_correct"] == 5


def test_automatic_scores_vs_hand_scores(baseline):
    """A, C and D are never hand-overridden (bar the one forced cell), so these
    agreement counts are the scorer's own. Rubrics were written with the
    baseline in view, so this is in-sample evidence, not a held-out accuracy."""
    prof, chat = (baseline["surfaces"][s]["agreement"] for s in ("profile", "chat"))
    assert (prof["agree"], prof["total"]) == (37, 37)
    assert (chat["agree"], chat["total"]) == (35, 37)
    assert chat["by_field"]["A"] == chat["by_field"]["C"] == "7/7"
    assert sorted(chat["disagreements"]) == [
        "P2.D: auto 2 / hand 1",  # hand score predates the "ADU hit isn't a false overlay" rule
        "P7.F: auto 1 / hand NP",
    ]
    assert baseline["forced_cells"]["chat"].keys() == {"P2.D"}


def test_baseline_without_hand_scores_is_all_automatic():
    rep = k.score_run_dir(BASELINE, KEY, k.SURFACES, None, None)
    assert all(b["manual_cells"] == 0 for b in rep["surfaces"].values())
    assert rep["surfaces"]["profile"]["aggregate"]["points"] == 51
    assert rep["surfaces"]["chat"]["aggregate"]["critical_misses"] == ["P2", "P5"]


def test_baseline_resolution_and_truncation_findings(baseline):
    res = baseline["resolution"]
    assert res["P3"]["chat_pin_matches"] is True and res["P6"]["chat_pin_matches"] is True
    for pid in ("P1", "P2", "P5", "P7"):
        assert res[pid]["chat_pin_matches"] is False  # chat cited a neighbouring PIN (M1)
    assert all(r["point_gap_ft"] > 50 for r in res.values())
    trunc = baseline["truncation"]
    assert [pid for pid, t in trunc.items() if not t["item6_present"]] == ["P3", "P5"]  # M5


def test_truncation_check_tells_a_silent_cut_off_from_a_flagged_one():
    head = "".join(f"## {i}. Item\nfull.\n" for i in range(1, 6))
    done = head + "## 6. F\nThe answer ends here."
    assert k.truncation_check({"text": done})["silently_cut_off"] is False
    cut = head + "## 6. F\nThe answer stops mid"
    assert k.truncation_check({"text": cut})["silently_cut_off"] is True
    flagged = cut + "\n\n---\n*This answer was cut off before it finished. Reply \"continue\".*"
    t = k.truncation_check({"text": flagged, "truncated": True})
    assert t["notice_shown"] and not t["ends_cleanly"] and t["silently_cut_off"] is False
    assert t["truncated_flag"] is True and t["item6_present"] is True


def test_markdown_report_renders(baseline):
    md = k.render_markdown(baseline, KEY, {"date": "2026-10-01", "git_sha": "abc1234", "source": "test"})
    assert "| profile | 32/37 = 86% | 51/64 = 80% | 2 |" in md
    assert "| chat | 28/37 = 76% | 38/56 = 68% | 7 | P2, P5 |" in md


# --- fetching ------------------------------------------------------------------------

def test_fetch_chat_collects_the_sse_stream():
    sse = "\n".join(
        [
            'data: {"type":"plan","plan":{"location":{"resolved_lat":41.9,"resolved_lon":-87.7},"sources":["vector_search"]}}',
            'data: {"type":"context","context":{"parcel_zoning":{"zone_class":"RM-4.5"}}}',
            'data: {"type":"token","text":"## 1. Zoning\\n"}',
            'data: {"type":"token","text":"RM-4.5"}',
            'data: {"type":"done","truncated":true,"citation_warnings":[]}',
        ]
    ) + "\n"

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {"message": "hi", "history": []} and request.url.path == "/chat"
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await k._fetch_chat(http, "http://kit.test", "hi")

    out = asyncio.run(run())
    assert out["text"] == "## 1. Zoning\nRM-4.5"
    assert out["plan_location"]["resolved_lat"] == 41.9 and out["context_zone"]["zone_class"] == "RM-4.5"
    assert out["truncated"] is True and out["error"] is None


# --- verdict helper (needs node >= 22.6; skipped where absent) ---------------------------

@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_verdict_helper_runs_the_real_frontend_module_on_a_recorded_payload():
    """The committed P3.verdict.json is the 2026-10-01 BASELINE text. The live
    module moves on (F2 rewrote the transit sentence), so compare shape, and pin
    the F2 behavior on the recorded payload: no density-bonus claim."""
    f = BASELINE / "P3.profile.json"
    try:
        got = k.load_verdicts([f])
    except (OSError, subprocess.SubprocessError):
        got = {}
    if not got:
        pytest.skip("this node cannot strip TypeScript types")
    live = next(iter(got.values()))
    recorded = json.loads((BASELINE / "P3.verdict.json").read_text())
    assert set(live) == set(recorded) and live["category"] == recorded["category"]
    assert any("density bonus" in r for r in recorded["reasons"])  # the baseline defect, kept on record
    assert not any("density bonus" in r.lower() and "no density bonus" not in r.lower() for r in live["reasons"])
