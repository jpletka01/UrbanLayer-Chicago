"""WS2 PR4b: reviewed applicant-proposal details are premium-only, private, and dark by default."""
import json
import sqlite3
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.auth import get_current_user
from backend.config import get_settings
from backend.legislation import upcoming
from backend.models import ContextObject, UpcomingZoningFiling, UpcomingZoningProvenance, UpcomingZoningSummary

SHA = "b" * 64
ORD = {"url": "https://clerk.test/o.pdf", "file_name": "O2026-1 Ordinance.pdf", "type": "Legislation"}
NAR = {"url": "https://clerk.test/n.pdf", "file_name": "O2026-1 Narrative and Plans.pdf", "type": "Exhibits"}
REVIEWED = {
    "O2026-1": {
        "reviewed_record": "O2026-1", "matter_id": "m1", "method": "hand_reviewed",
        "reviewed_on": "2026-11-06", "reviewed_by": "reviewer",
        "attachments": {"ordinance": {**ORD, "sha256": SHA}, "narrative": {**NAR, "sha256": SHA}},
        "fields": [
            {"id": "to_district", "value": "B2-3", "unit": None, "page": 1, "source": "ordinance"},
            {"id": "height", "value": "45", "unit": "ft", "page": 2, "source": "narrative"},
        ],
    }
}


def _store(path, attachments=(ORD, NAR), record="O2026-1"):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE matters (matter_id TEXT, lifecycle_id TEXT, record_number TEXT)")
    con.execute("CREATE TABLE attachments (matter_id TEXT, file_name TEXT, url TEXT, attachment_type TEXT)")
    con.execute("INSERT INTO matters VALUES ('m1', 'O2026-1', ?)", (record,))
    for a in attachments:
        con.execute("INSERT INTO attachments VALUES ('m1', ?, ?, ?)", (a["file_name"], a["url"], a["type"]))
    con.commit()
    con.close()
    return path


def _summary(record="O2026-1"):
    prov = UpcomingZoningProvenance(source_id="chi.clerk.legislation", method="m", confidence="standard")
    return UpcomingZoningSummary(
        status="ready", placement_status="complete", record_provenance=prov, placement_provenance=prov,
        subject_filings=[UpcomingZoningFiling(
            record_number=record, title="Zoning Reclassification Map No. 1-A at 1 W Main St - App No. 1T1",
            status="4-In Committee", sub_status="Referred", url="https://clerk.test/matter", match_kind="subject_pin",
        )],
    )


def test_premium_gets_cited_values_and_free_gets_only_that_they_exist(tmp_path):
    db = _store(tmp_path / "p.db")
    premium = _summary()
    assert upcoming.attach_proposal_details(db, premium, premium=True, details=REVIEWED) == 1
    details = premium.subject_filings[0].proposal_details
    assert [(f.id, f.value, f.unit, f.page, f.document_url) for f in details.fields] == [
        ("to_district", "B2-3", None, 1, ORD["url"]), ("height", "45", "ft", 2, NAR["url"]),
    ]
    free = _summary()
    assert upcoming.attach_proposal_details(db, free, premium=False, details=REVIEWED) == 0
    payload = json.dumps(free.model_dump(exclude_none=True))
    assert free.subject_filings[0].proposal_details_status == "premium"
    assert "B2-3" not in payload and ".pdf" not in payload and "proposal_details\"" not in payload


def test_a_new_record_or_replaced_attachment_is_not_joined(tmp_path):
    substitute = _summary("SO2026-1")
    upcoming.attach_proposal_details(_store(tmp_path / "a.db", record="SO2026-1"), substitute, premium=True, details=REVIEWED)
    assert substitute.subject_filings[0].proposal_details is None
    replaced = _summary()
    moved = {**NAR, "url": "https://clerk.test/n-v2.pdf"}
    upcoming.attach_proposal_details(_store(tmp_path / "b.db", attachments=(ORD, moved)), replaced, premium=True, details=REVIEWED)
    assert replaced.subject_filings[0].proposal_details is None
    assert replaced.subject_filings[0].proposal_details_status is None


def test_unreadable_store_attaches_nothing(tmp_path):
    summary = _summary()
    assert upcoming.attach_proposal_details(tmp_path / "missing.db", summary, premium=True, details=REVIEWED) == 0
    assert summary.subject_filings[0].proposal_details is None


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "pending_legislation_path", _store(tmp_path / "s.db"))
    rl = main.ResolvedLocation(41.9, -87.6, "1 W Main St", "14000000000000", "authoritative")
    with patch.object(main, "_resolve_location", new=AsyncMock(return_value=rl)), \
         patch.object(main, "_require_chicago", return_value=None), \
         patch.object(main, "_fetch_scorecard_data", new=AsyncMock(side_effect=lambda *a, **k: {"context": ContextObject(), "comparables": None})), \
         patch.object(upcoming, "summary_for", side_effect=lambda *a, **k: _summary()), \
         patch("backend.legislation.impacts.for_parcel", return_value=([], None)), \
         patch("backend.legislation.filing_details.load_details", return_value=REVIEWED):
        yield TestClient(main.app), settings
    main.app.dependency_overrides.clear()


def _filing(response):
    return response.json()["context"]["upcoming_zoning"]["subject_filings"][0]


@pytest.mark.parametrize("tier", ["premium", "admin"])
def test_endpoint_premium_response_is_private_and_carries_values(client, monkeypatch, tier):
    http, settings = client
    monkeypatch.setattr(settings, "pending_proposal_details_enabled", True)
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u", "tier": tier}
    r = http.get("/api/scorecard?pin=14000000000000")
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "private, no-store"
    assert _filing(r)["proposal_details"]["fields"][1] == {
        "id": "height", "value": "45", "unit": "ft", "page": 2,
        "document_name": NAR["file_name"], "document_url": NAR["url"],
    }


@pytest.mark.parametrize("user", [None, {"id": "u", "tier": "free"}])
def test_endpoint_free_and_anonymous_json_has_no_value_or_pdf_url(client, monkeypatch, user):
    http, settings = client
    monkeypatch.setattr(settings, "pending_proposal_details_enabled", True)
    main.app.dependency_overrides[get_current_user] = lambda: user
    r = http.get("/api/scorecard?pin=14000000000000")
    assert "private" not in r.headers.get("cache-control", "")
    assert _filing(r)["proposal_details_status"] == "premium" and "proposal_details" not in _filing(r)
    assert ".pdf" not in r.text and "B2-3" not in r.text


def test_endpoint_flag_off_serves_nothing_even_to_premium(client):
    http, settings = client
    assert settings.pending_proposal_details_enabled is False
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u", "tier": "premium"}
    r = http.get("/api/scorecard?pin=14000000000000")
    assert "proposal_details" not in r.text and "private" not in r.headers.get("cache-control", "")


def test_chat_grounding_cannot_carry_proposal_details():
    """Pydantic drops unknown keys: a client that sent upcoming_zoning to chat would still ground nothing."""
    from backend.models import ScorecardContext

    assert "upcoming_zoning" not in ScorecardContext.model_fields
    ctx = ScorecardContext.model_validate({"pin": "14000000000000", "upcoming_zoning": {"subject_filings": []}})
    assert "upcoming_zoning" not in ctx.model_dump()
