"""The one free Deep analysis (decision Item 123): per person, survives account deletion and identity moves."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import auth, db, entitlements
from backend import main as main_mod
from backend.main import app

LOT_A = "14331030110000"
LOT_B = "14283190070000"


@pytest_asyncio.fixture
async def test_db(tmp_path):
    s = MagicMock()
    s.db_path = tmp_path / "test.db"
    with patch("backend.db.get_settings", return_value=s):
        await db.init_db()
        yield
        await db.close_db()


async def _sign_in(uid: str, provider: str = "google", subject: str | None = None) -> dict:
    user, _ = await db.sign_in_identity({"provider": provider, "subject": subject or f"s-{uid}"}, uid)
    return user


class TestClaim:
    @pytest.mark.asyncio
    async def test_one_free_lot_then_409_for_another(self, test_db):
        user = await _sign_in("u1")
        assert (await entitlements.status(user))["deep_analysis"] == {
            "unlimited": False, "free_left": 1, "free_pin": None}
        assert (await entitlements.claim(user, LOT_A))["ok"] is True
        assert (await entitlements.claim(user, LOT_A))["ok"] is True  # the same lot again
        with pytest.raises(HTTPException) as e:
            await entitlements.claim(user, LOT_B)
        assert e.value.status_code == 409 and e.value.detail == {"error": "free_used", "free_pin": LOT_A}
        assert (await entitlements.status(user))["deep_analysis"]["free_pin"] == LOT_A

    @pytest.mark.asyncio
    async def test_pro_and_admin_use_nothing(self, test_db):
        user = await _sign_in("u1")
        for tier in ("premium", "admin"):
            r = await entitlements.claim({**user, "tier": tier}, LOT_B)
            assert r["unlimited"] is True
        assert (await entitlements.status(user))["deep_analysis"]["free_left"] == 1

    @pytest.mark.asyncio
    async def test_twenty_claims_at_once_one_lot(self, test_db):
        user = await _sign_in("u1")
        pins = [f"1433103011{i:04d}" for i in range(20)]
        results = await asyncio.gather(*[entitlements.claim(user, p) for p in pins], return_exceptions=True)
        ok = [r for r in results if isinstance(r, dict)]
        assert len(ok) == 1
        assert all(isinstance(r, HTTPException) and r.status_code == 409 for r in results if r not in ok)

    @pytest.mark.asyncio
    async def test_signed_out_has_none(self, test_db):
        assert (await entitlements.status(None)) == {
            "signed_in": False, "deep_analysis": {"unlimited": False, "free_left": 0, "free_pin": None}}


class TestFollowsThePerson:
    @pytest.mark.asyncio
    async def test_delete_and_sign_in_again_finds_it_used(self, test_db):
        user = await _sign_in("u1", subject="google-person")
        await entitlements.claim(user, LOT_A)
        await db.delete_user_account("u1")
        again = await _sign_in("u2", subject="google-person")
        status = await entitlements.status(again)
        assert status["deep_analysis"] == {"unlimited": False, "free_left": 0, "free_pin": LOT_A}
        assert await entitlements.opens_lot(again, LOT_A)  # the same lot stays open to the person

    @pytest.mark.asyncio
    async def test_identity_linked_after_use_carries_it(self, test_db):
        """Use it with Google, link Microsoft, drop Google, delete; a new account by Microsoft finds it used."""
        user = await _sign_in("u1", subject="g-person")
        await entitlements.claim(user, LOT_A)
        assert await db.link_identity("u1", {"provider": "microsoft", "subject": "tid:oid"}) == "linked"
        await entitlements.carry_on_link("u1", "microsoft", "tid:oid")
        await db.remove_identity("u1", "google")
        await db.delete_user_account("u1")
        newcomer = await _sign_in("u2", provider="microsoft", subject="tid:oid")
        assert (await entitlements.status(newcomer))["deep_analysis"]["free_left"] == 0

    @pytest.mark.asyncio
    async def test_link_callback_records_the_carry(self, test_db):
        """The real link path (identity flow) calls carry_on_link on a new link."""
        from backend.identity import flow
        user = await _sign_in("u1", subject="g-person")
        await entitlements.claim(user, LOT_A)
        request = SimpleNamespace(cookies={})
        await flow._finish_link(request, "microsoft", {"u": "u1"}, {"provider": "microsoft", "subject": "t:o"}, "/")
        await db.remove_identity("u1", "google")
        await db.delete_user_account("u1")
        newcomer = await _sign_in("u2", provider="microsoft", subject="t:o")
        assert (await entitlements.status(newcomer))["deep_analysis"]["free_pin"] == LOT_A

    @pytest.mark.asyncio
    async def test_another_person_is_unaffected(self, test_db):
        a = await _sign_in("u1")
        b = await _sign_in("u2")
        await entitlements.claim(a, LOT_A)
        assert (await entitlements.status(b))["deep_analysis"]["free_left"] == 1
        assert not await entitlements.opens_lot(b, LOT_A)

    @pytest.mark.asyncio
    async def test_deletion_drops_the_account_row(self, test_db):
        user = await _sign_in("u1")
        await entitlements.claim(user, LOT_A)
        await db.delete_user_account("u1")
        cur = await db._get_db().execute("SELECT COUNT(*) FROM entitlement_uses WHERE subject = 'user:u1'")
        assert (await cur.fetchone())[0] == 0


class TestRoutes:
    @pytest.fixture
    def client(self):
        c = TestClient(app)
        c.cookies.set("csrf_token", "csrf-test")
        yield c
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_claim_validates_the_pin_and_needs_sign_in(self, test_db, client):
        user = await _sign_in("u1")
        app.dependency_overrides[auth.require_auth] = lambda: user
        h = {"x-csrf-token": "csrf-test"}
        assert client.post("/api/entitlements/deep-analysis", json={"pin": "123"}, headers=h).status_code == 422
        assert client.post("/api/entitlements/deep-analysis", json={"pin": LOT_A, "user_id": "u2"},
                           headers=h).status_code == 422
        r = client.post("/api/entitlements/deep-analysis", json={"pin": LOT_A}, headers=h)
        assert r.status_code == 200 and r.json()["pin"] == LOT_A

    @pytest.mark.asyncio
    async def test_report_access_opens_the_free_lot_only(self, test_db, client):
        user = await _sign_in("u1")
        await entitlements.claim(user, LOT_A)
        app.dependency_overrides[auth.require_auth] = lambda: user
        for pin, expected in ((LOT_A, True), (LOT_B, False)):
            rl = SimpleNamespace(lat=41.9, lon=-87.6, address="x", pin=pin, confidence="authoritative")
            with patch.object(main_mod, "_resolve_location", AsyncMock(return_value=rl)):
                r = client.get(f"/api/report/access?pin={pin}")
            assert r.json()["has_access"] is expected
