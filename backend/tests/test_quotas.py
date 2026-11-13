"""Quotas (decision Item 120): durable counters, atomic under races, Chicago months, refunds, the signed anonymous
cookie, the soft network ceiling, the spend caps over every phase, and the llm_calls rebuild. No model is called:
the chat stream is replaced by a stub that answers, clarifies or fails."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend import db, quotas
from backend.auth import get_current_user
from backend.main import app
from backend.rate_limit import check_daily_budget, clear_rate_limits

CHI = ZoneInfo("America/Chicago")
FREE = {"id": "u_free", "email": "f@example.com", "name": "F", "tier": "free"}
PRO = {"id": "u_pro", "email": "p@example.com", "name": "P", "tier": "premium"}
ADMIN = {"id": "u_admin", "email": "a@example.com", "name": "A", "tier": "admin"}


@pytest_asyncio.fixture
async def store(tmp_path, monkeypatch):
    settings = MagicMock()
    settings.db_path = str(tmp_path / "q.db")
    settings.upload_dir = tmp_path / "uploads"
    settings.report_store_dir = tmp_path / "reports"
    for k in ("QUOTA_ANON_TOTAL", "QUOTA_ANON_IP_DAY", "QUOTA_FREE_MONTH", "QUOTA_PRO_MONTH"):
        monkeypatch.delenv(k, raising=False)
    with patch("backend.db.get_settings", return_value=settings):
        await db.init_db()
        clear_rate_limits()
        yield
        await db.close_db()


def _request(ip: str = "203.0.113.9", cookie: str | None = None):
    req = MagicMock()
    req.cookies = {quotas.ANON_COOKIE: cookie} if cookie else {}
    req.headers = {"x-real-ip": ip}
    req.client = MagicMock(host="10.0.0.2")
    return req


class TestPeriods:
    def test_month_and_reset_in_chicago(self):
        late = datetime(2026, 11, 30, 23, 59, tzinfo=CHI)
        assert quotas.month_period(late) == "2026-11" and quotas.resets_on(late) == "2026-12-01"
        # 5:30 UTC on Dec 1 is still Nov 30 in Chicago.
        utc = datetime(2026, 12, 1, 5, 30, tzinfo=ZoneInfo("UTC"))
        assert quotas.month_period(utc) == "2026-11"
        assert quotas.resets_on(datetime(2026, 12, 15, tzinfo=CHI)) == "2027-01-01"

    def test_plans(self):
        assert quotas.plan_of(None) == "anonymous"
        assert quotas.plan_of(FREE) == "free" and quotas.plan_of(PRO) == "pro" and quotas.plan_of(ADMIN) == "admin"
        # A voucher's premium_until reaches here as tier "premium" (auth's single choke point).
        assert quotas.plan_of({"id": "v", "tier": "premium", "comp_premium": True}) == "pro"


class TestAnonCookie:
    def test_signed_roundtrip_and_tamper(self):
        token = quotas.sign_anon("abc123")
        assert quotas.read_anon(token) == "abc123"
        assert quotas.read_anon(token[:-1] + ("A" if token[-1] != "A" else "B")) is None
        assert quotas.read_anon("abc123") is None
        assert quotas.read_anon("other." + token.split(".")[1]) is None


class TestReserve:
    async def test_free_monthly_limit_and_reset(self, store, monkeypatch):
        monkeypatch.setenv("QUOTA_FREE_MONTH", "3")
        nov = datetime(2026, 11, 20, tzinfo=CHI)
        for _ in range(3):
            await quotas.reserve(_request(), FREE, now=nov)
        with pytest.raises(quotas.QuotaExceeded) as e:
            await quotas.reserve(_request(), FREE, now=nov)
        assert e.value.status_code == 429
        assert e.value.detail == {"error": "quota", "plan": "free", "limit": 3, "used": 3, "resets_on": "2026-12-01",
                                  "pro_limit": 200}
        # December starts fresh.
        await quotas.reserve(_request(), FREE, now=datetime(2026, 12, 1, 0, 1, tzinfo=CHI))

    async def test_pro_gets_its_own_limit(self, store, monkeypatch):
        monkeypatch.setenv("QUOTA_FREE_MONTH", "1")
        monkeypatch.setenv("QUOTA_PRO_MONTH", "2")
        await quotas.reserve(_request(), PRO)
        await quotas.reserve(_request(), PRO)
        with pytest.raises(quotas.QuotaExceeded):
            await quotas.reserve(_request(), PRO)

    async def test_admin_counted_never_refused(self, store, monkeypatch):
        monkeypatch.setenv("QUOTA_FREE_MONTH", "1")
        for _ in range(5):
            await quotas.reserve(_request(), ADMIN)
        assert (await quotas.usage(_request(), ADMIN))["used"] == 5

    async def test_fifty_at_once_admit_exactly_fifty(self, store, monkeypatch):
        monkeypatch.setenv("QUOTA_FREE_MONTH", "50")
        results = await asyncio.gather(*(quotas.reserve(_request(), FREE) for _ in range(80)), return_exceptions=True)
        ok = [r for r in results if not isinstance(r, BaseException)]
        refused = [r for r in results if isinstance(r, quotas.QuotaExceeded)]
        assert len(ok) == 50 and len(refused) == 30
        assert (await quotas.usage(_request(), FREE))["used"] == 50

    async def test_refund_once(self, store, monkeypatch):
        monkeypatch.setenv("QUOTA_FREE_MONTH", "1")
        ticket, _ = await quotas.reserve(_request(), FREE)
        await ticket.refund()
        await ticket.refund()  # a second refund changes nothing
        assert (await quotas.usage(_request(), FREE))["used"] == 0
        await quotas.reserve(_request(), FREE)
        with pytest.raises(quotas.QuotaExceeded):
            await quotas.reserve(_request(), FREE)

    async def test_counts_survive_a_restart(self, store, tmp_path):
        await quotas.reserve(_request(), FREE)
        settings = MagicMock()
        settings.db_path = str(tmp_path / "q.db")
        await db.close_db()
        with patch("backend.db.get_settings", return_value=settings):
            await db.init_db()
            assert (await quotas.usage(_request(), FREE))["used"] == 1


class TestAnonymous:
    async def test_three_in_total_on_one_cookie(self, store):
        ticket, cookie = await quotas.reserve(_request(), None)
        assert cookie and quotas.read_anon(cookie)
        for _ in range(2):
            _, again = await quotas.reserve(_request(cookie=cookie), None)
            assert again is None  # the same cookie is kept
        with pytest.raises(quotas.QuotaExceeded) as e:
            await quotas.reserve(_request(cookie=cookie), None)
        assert e.value.detail["plan"] == "anonymous" and e.value.detail["resets_on"] is None
        assert (await quotas.usage(_request(cookie=cookie), None))["used"] == 3

    async def test_cleared_cookies_meet_the_network_ceiling(self, store, monkeypatch):
        monkeypatch.setenv("QUOTA_ANON_IP_DAY", "4")
        for _ in range(4):
            await quotas.reserve(_request(), None)  # a new cookie every time
        with pytest.raises(quotas.QuotaExceeded) as e:
            await quotas.reserve(_request(), None)
        assert e.value.detail.get("network") is True
        # Another network is unaffected.
        await quotas.reserve(_request(ip="198.51.100.4"), None)

    async def test_network_refusal_gives_back_the_cookie_count(self, store, monkeypatch):
        monkeypatch.setenv("QUOTA_ANON_IP_DAY", "1")
        _, cookie = await quotas.reserve(_request(), None)
        with pytest.raises(quotas.QuotaExceeded):
            await quotas.reserve(_request(cookie=cookie), None)
        assert (await quotas.usage(_request(cookie=cookie), None))["used"] == 1

    async def test_forged_cookie_is_a_new_visitor(self, store):
        _, cookie = await quotas.reserve(_request(), None)
        _, fresh = await quotas.reserve(_request(cookie=cookie + "x"), None)
        assert fresh and fresh != cookie

    async def test_prune_old_anonymous_rows_only(self, store):
        await quotas.reserve(_request(), None)
        await quotas.reserve(_request(), FREE)
        later = datetime.now(CHI).replace(year=datetime.now(CHI).year + 1)
        assert await quotas.prune(later) == 2  # the cookie row and the network row
        assert (await quotas.usage(_request(), FREE))["used"] == 1


class TestChatEndpoint:
    """The real /chat route with the stream stubbed: answered counts, clarification and failure give it back."""

    def _client(self, user):
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app)

    def _stub(self, kind):
        async def fake(req, outcome=None):
            if kind == "answer" and outcome is not None:
                outcome["answered"] = True
            yield 'data: {"type":"done"}\n\n'
        return fake

    @pytest.fixture(autouse=True)
    def _clean(self):
        yield
        app.dependency_overrides.clear()

    async def _ask(self, user, kind, cookies=None):
        auth_settings = MagicMock(google_client_id="", microsoft_client_id="", apple_client_id="", auth_dev_login=False, jwt_secret="test-secret")
        with patch("backend.main._event_stream", self._stub(kind)), \
             patch("backend.rate_limit.get_current_user", return_value=user), \
             patch("backend.auth.get_settings", return_value=auth_settings):
            c = self._client(user)
            if cookies:
                c.cookies.update(cookies)
            return await asyncio.to_thread(c.post, "/chat", json={"message": "Can I build here?"})

    async def test_answer_counts_clarification_and_failure_do_not(self, store, monkeypatch):
        monkeypatch.setenv("QUOTA_FREE_MONTH", "1")
        for kind in ("clarify", "fail", "clarify"):
            assert (await self._ask(FREE, kind)).status_code == 200
        assert (await quotas.usage(_request(), FREE))["used"] == 0
        assert (await self._ask(FREE, "answer")).status_code == 200
        r = await self._ask(FREE, "answer")
        assert r.status_code == 429 and r.json()["detail"]["resets_on"]

    async def test_signed_out_gets_a_cookie_and_three_questions(self, store):
        first = await self._ask(None, "answer")
        cookie = first.cookies.get(quotas.ANON_COOKIE)
        assert first.status_code == 200 and cookie
        for _ in range(2):
            assert (await self._ask(None, "answer", {quotas.ANON_COOKIE: cookie})).status_code == 200
        r = await self._ask(None, "answer", {quotas.ANON_COOKIE: cookie})
        assert r.status_code == 429 and r.json()["detail"]["plan"] == "anonymous"

    async def test_usage_endpoint(self, store):
        await quotas.reserve(_request(), FREE)
        with patch("backend.main.get_current_user", return_value=FREE):
            r = await asyncio.to_thread(TestClient(app).get, "/api/usage")
        body = r.json()
        assert body["plan"] == "free" and body["used"] == 1 and body["limit"] == 50 and body["resets_on"]


class TestSpendCap:
    async def _log(self, phase, model="claude-sonnet-4-6", out=200_000, when_ms=None):
        await db.save_llm_call(request_group="g", conversation_id=None, phase=phase, model=model, input_tokens=0,
                               output_tokens=out, duration_ms=1, user_id="u_free")
        if when_ms is not None:
            await db._get_db().execute("UPDATE llm_calls SET created_at = ? WHERE id = (SELECT MAX(id) FROM llm_calls)", (when_ms,))
            await db._get_db().commit()

    async def test_translation_calls_are_logged_and_counted(self, store, monkeypatch):
        monkeypatch.setenv("DAILY_API_BUDGET_USD", "5")
        await self._log("translation", out=400_000)  # $6 at Sonnet output prices
        cur = await db._get_db().execute("SELECT phase, user_id FROM llm_calls")
        assert [tuple(r) for r in await cur.fetchall()] == [("translation", "u_free")]
        with pytest.raises(Exception) as e:
            await check_daily_budget(FREE)
        assert e.value.status_code == 503 and e.value.detail["until"] == "tomorrow"

    async def test_admin_exempt(self, store, monkeypatch):
        monkeypatch.setenv("DAILY_API_BUDGET_USD", "1")
        await self._log("synthesizer")
        await check_daily_budget(ADMIN)

    async def test_monthly_cap_counts_earlier_days(self, store, monkeypatch):
        monkeypatch.setenv("DAILY_API_BUDGET_USD", "1000")
        monkeypatch.setenv("MONTHLY_API_BUDGET_USD", "5")
        now = datetime(2026, 11, 20, 12, tzinfo=CHI)
        earlier = int(datetime(2026, 11, 3, 12, tzinfo=CHI).timestamp() * 1000)
        last_month = int(datetime(2026, 10, 30, 12, tzinfo=CHI).timestamp() * 1000)
        await self._log("synthesizer", out=200_000, when_ms=last_month)  # $3, October: not this month
        await check_daily_budget(FREE, now=now)
        await self._log("synthesizer", out=400_000, when_ms=earlier)  # $6 this month
        with pytest.raises(Exception) as e:
            await check_daily_budget(FREE, now=now)
        assert e.value.detail["until"] == "month"


def test_v17_llm_calls_with_check_is_rebuilt(tmp_path):
    """A database from before v18 keeps its rows and loses the phase CHECK."""
    async def run():
        settings = MagicMock()
        settings.db_path = str(tmp_path / "old.db")
        with patch("backend.db.get_settings", return_value=settings):
            await db.init_db()
            await db.close_db()
        con = sqlite3.connect(tmp_path / "old.db")
        con.executescript("""
            DROP TABLE llm_calls;
            CREATE TABLE llm_calls (id INTEGER PRIMARY KEY AUTOINCREMENT, request_group TEXT NOT NULL, conversation_id TEXT,
              phase TEXT NOT NULL CHECK(phase IN ('conversation', 'router', 'synthesizer')), model TEXT NOT NULL,
              input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL, cache_read_tokens INTEGER NOT NULL DEFAULT 0,
              cache_create_tokens INTEGER NOT NULL DEFAULT 0, duration_ms INTEGER NOT NULL,
              status TEXT NOT NULL DEFAULT 'ok' CHECK(status IN ('ok', 'error')), error_message TEXT,
              created_at INTEGER NOT NULL, user_id TEXT);
            INSERT INTO llm_calls (request_group, phase, model, input_tokens, output_tokens, duration_ms, created_at)
              VALUES ('old', 'router', 'm', 1, 2, 3, 4);
            DROP TABLE usage_counters;
            UPDATE schema_version SET version = 17;
        """)
        con.commit()
        con.close()
        with patch("backend.db.get_settings", return_value=settings):
            await db.init_db()
            conn = db._get_db()
            await db.save_llm_call(request_group="new", conversation_id=None, phase="translation", model="m",
                                   input_tokens=1, output_tokens=1, duration_ms=1)
            rows = [tuple(r) for r in await (await conn.execute("SELECT request_group, phase FROM llm_calls ORDER BY id")).fetchall()]
            ver = (await (await conn.execute("SELECT version FROM schema_version")).fetchone())[0]
            has_usage = await (await conn.execute("SELECT name FROM sqlite_master WHERE name = 'usage_counters'")).fetchone()
            await db.close_db()
        return rows, ver, has_usage
    rows, ver, has_usage = asyncio.run(run())
    assert rows == [("old", "router"), ("new", "translation")] and ver >= 18 and has_usage
