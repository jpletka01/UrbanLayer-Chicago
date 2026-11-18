"""The chat audit's scorer: a scorer bug would silently change every number in the audit."""

import json
from pathlib import Path

from eval import chat_audit as ca

QUESTIONS = json.loads((Path(__file__).resolve().parents[1] / "chat_audit_questions.json").read_text())["queries"]


def _q(qid):
    return next(q for q in QUESTIONS if q["id"] == qid)


def _turn(answer, sources=(), chunks=(), intent="legal_question"):
    return {"answer": answer, "plan": {"sources": list(sources), "intent": intent, "location": {"pin": "1"}},
            "context": {"code_chunks": [{"section": s} for s in chunks]}}


def test_question_set_shape():
    assert len(QUESTIONS) >= 60
    assert QUESTIONS[0]["id"] == "restaurant_rm6_wrightwood"
    names = set(ca.AREA_FEEDS) | {"vector_search", "regulatory_domain", "property_domain", "incentives_domain",
                                  "neighborhood_domain"}
    for q in QUESTIONS:
        assert q["gold"]["conclusion"] in {"yes", "no", "special_use", "conditional", "info", "cant_tell", "decline", "clarify"}
        assert set(q["sources"]["need"]) <= names and set(q["sources"]["not_needed"]) <= names, q["id"]
        assert not set(q["sources"]["need"]) & set(q["sources"]["not_needed"]), q["id"]


def test_first_sentence_skips_heading():
    assert ca.first_sentence("## Opening a Bar at 2200 W Chicago Ave\n\n**No.** A tavern is not allowed.") == "No."


def test_trigger_answer_scores_as_wrong_and_padded():
    q = _q("restaurant_rm6_wrightwood")
    ans = ("**Yes, a restaurant is likely allowable at 443 W Wrightwood Ave — but you'll need a special use approval "
           "for some configurations.**\n\nThis parcel is zoned **RM-6** [1]. Lincoln Park has 5 ARO projects. "
           "Lincoln Park has seen 1,010 permits issued recently [data:permits]. Since `in_landmark_district` is false.\n\n"
           "A restaurant is **not permitted by right** in the RM-6 base district.\n\n---\n**Sources for the parcel data used**\n- x")
    s = ca.score_answer(q, q["gold"], q["relevant_topics"], q["sources"],
                        _turn(ans, ["vector_search", "regulatory_domain", "business_api", "permits_api"], ["17-3-0200"]))
    assert s["conclusion_ok"] is False and s["wrong_hits"]
    assert s["mixed_conclusion"] is True
    assert s["over_fetch"] == ["business_api", "permits_api"]
    assert s["under_fetch"] == ["property_domain"]
    assert {"aro", "permits"} <= set(s["filler_topics"])
    assert s["leaked_fields"] == ["in_landmark_district"]
    assert s["cited_off_gold"] == ["17-3-0200"]


def test_correct_no_answer_passes():
    q = _q("bar_b23_chicago")
    ans = "**No.** A tavern is not allowed in B2 (it is '-' in the use table); a limited restaurant is permitted."
    s = ca.score_answer(q, q["gold"], q["relevant_topics"], q["sources"], _turn(ans, ["vector_search", "regulatory_domain"]))
    assert s["first_sentence_agrees"] and s["conclusion_ok"] and not s["over_fetch"] and not s["filler_topics"]


def test_special_use_claim_for_b2_tavern_is_wrong():
    q = _q("bar_b23_chicago")
    ans = "**A tavern is not permitted by right in B2 — it requires a Special Use approval.**"
    assert ca.score_answer(q, q["gold"], [], q["sources"], _turn(ans))["conclusion_ok"] is False


def test_cant_tell_and_clarify():
    q = _q("crime_wicker_park")
    fq = q["followup"]
    ans = "The city's public crime database doesn't allow filtering by intersection in the data I have."
    assert ca.score_answer(q, fq["gold"], [], fq["sources"], _turn(ans, ["crime_api"]))["conclusion_ok"]
    v = _q("vague_my_lot")
    assert ca.first_sentence_agrees("clarify", "What is the address?", {"intent": "clarification_needed"})
    assert ca.score_answer(v, v["gold"], [], v["sources"], _turn("What is the address?", intent="clarification_needed"))["conclusion_ok"]


def test_named_districts():
    assert ca._named_districts("B3 use table allowed uses") == {"B3"}
    assert ca._named_districts("RM-4.5 bulk and density") == {"RM4.5"}
    assert ca._named_districts("use table allowed uses restaurant") == set()
