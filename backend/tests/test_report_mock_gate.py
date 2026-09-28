"""/api/report?mock=true renders fixture data and must not reach customers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.auth import require_auth
from backend.main import app


@pytest.fixture
def client_as():
    auth_settings = MagicMock()
    auth_settings.google_client_id = ""

    def _as(tier: str) -> TestClient:
        app.dependency_overrides[require_auth] = lambda: {"id": "u1", "tier": tier}
        return TestClient(app)

    with patch("backend.auth.get_settings", return_value=auth_settings):
        yield _as
    app.dependency_overrides.clear()


@pytest.mark.parametrize("tier", ["free", "premium"])
def test_mock_report_forbidden_for_customers(client_as, tier):
    with patch("backend.main._resolve_location", new_callable=AsyncMock) as resolve:
        resp = client_as(tier).get("/api/report", params={"pin": "14313320180000", "mock": "true"})
    assert resp.status_code == 403
    resolve.assert_not_called()  # rejected before any data work
