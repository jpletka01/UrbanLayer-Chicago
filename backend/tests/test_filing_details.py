import copy

from backend.legislation.filing_details import current_details, load_details, validate_artifact

SHA = "a" * 64
ENTRY = {
    "reviewed_record": "O2026-1", "matter_id": "m1", "method": "hand_reviewed",
    "reviewed_on": "2026-11-06", "reviewed_by": "reviewer",
    "attachments": {
        "ordinance": {"url": "https://clerk.test/o.pdf", "file_name": "O2026-1 Ordinance.pdf", "type": "Legislation", "sha256": SHA},
        "narrative": {"url": "https://clerk.test/n.pdf", "file_name": "O2026-1 Narrative and Plans.pdf", "type": "Exhibits", "sha256": SHA},
    },
    "fields": [
        {"id": "to_district", "value": "B2-3", "unit": None, "page": 1, "source": "ordinance"},
        {"id": "height", "value": "45", "unit": "ft", "page": 2, "source": "narrative"},
    ],
}
ARTIFACT = {"schema_version": 2, "details": {"O2026-1": ENTRY}}
LIVE = [{"url": a["url"], "file_name": a["file_name"], "type": a["type"]} for a in ENTRY["attachments"].values()]


def test_empty_committed_artifact_is_valid_but_exposes_no_details():
    assert validate_artifact({"schema_version": 2, "details": {}}) == []
    assert load_details() == {}


def test_a_complete_hand_reviewed_entry_validates():
    assert validate_artifact(ARTIFACT) == []


def test_detail_requires_review_identity_and_page_citation():
    problems = validate_artifact({"schema_version": 2, "details": {"O1": {"fields": [{"id": "height", "value": "45"}]}}})
    assert any("missing reviewed_record" in p for p in problems)
    assert any("method must be hand_reviewed" in p for p in problems)


def test_units_sources_and_attachment_roles_are_enforced():
    bad = copy.deepcopy(ARTIFACT)
    bad["details"]["O2026-1"]["fields"][1]["unit"] = None
    bad["details"]["O2026-1"]["fields"][0]["source"] = "narrative"
    bad["details"]["O2026-1"]["attachments"]["narrative"]["file_name"] = "O2026-1 Application.pdf"
    problems = validate_artifact(bad)
    assert any("wrong unit for height" in p for p in problems)
    assert any("to_district must cite the ordinance" in p for p in problems)
    assert any("invalid narrative attachment identity" in p for p in problems)


def test_join_requires_current_record_and_identical_attachment_metadata():
    details = ARTIFACT["details"]
    assert current_details("O2026-1", "O2026-1", LIVE, details=details) == ENTRY
    assert current_details("O2026-1", "SO2026-1", LIVE, details=details) is None
    replaced = [dict(LIVE[0]), {**LIVE[1], "url": "https://clerk.test/n2.pdf"}]
    assert current_details("O2026-1", "O2026-1", replaced, details=details) is None
    assert current_details("O2026-2", "O2026-2", LIVE, details=details) is None
