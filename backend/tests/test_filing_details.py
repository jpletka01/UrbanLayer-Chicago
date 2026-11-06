from backend.legislation.filing_details import load_details, validate_artifact


def test_empty_draft_artifact_is_valid_but_exposes_no_details():
    assert validate_artifact({"schema_version": 1, "details": {}}) == []
    assert load_details() == {}


def test_detail_requires_review_identity_hash_and_page_citation():
    data = {"schema_version": 1, "details": {"O1": {"fields": [{"id": "height", "value": "45"}]}}}
    problems = validate_artifact(data)
    assert any("missing reviewed_record" in problem for problem in problems)
    assert any("invalid cited field" in problem for problem in problems)
