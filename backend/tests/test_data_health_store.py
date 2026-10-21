"""The status store and the /health block (WS6 M2)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.data_health.store import (
    LATE_AFTER_HOURS, RETENTION_DAYS, Store, health_block, open_readonly,
)

NOW = datetime(2026, 10, 21, 5, 37, tzinfo=timezone.utc)


def rec(store, sid="a.b", state="ok", now=NOW, prev=None, **kw):
    store.record(source_id=sid, state=state, reason=kw.pop("reason", ""), severity="standard", as_of=None, basis=None,
                 age_days=None, now=now, probe_error=kw.pop("probe_error", False), latency_ms=5, requests=1,
                 prev=prev, alerted_state=kw.pop("alerted_state", None), alerted_at=kw.pop("alerted_at", None))


def run(store, now=NOW, error=None):
    rid = store.start_run(now)
    store.finish_run(rid, now + timedelta(minutes=2), sources=1, alarms=0, requests=3, error=error)


def test_a_row_round_trips_and_state_since_holds_until_the_state_changes(tmp_path):
    with Store(tmp_path / "h.db") as s:
        rec(s, state="alarm", reason="old", alerted_state="alarm", alerted_at=NOW)
        s.commit()
        p = s.previous()["a.b"]
        assert (p.state, p.alerted_state, p.state_since, p.probe_error) == ("alarm", "alarm", NOW, False)
        later = NOW + timedelta(days=1)
        rec(s, state="alarm", now=later, prev=p)
        assert s.previous()["a.b"].state_since == NOW            # still red since the first day
        rec(s, state="ok", now=later + timedelta(days=1), prev=s.previous()["a.b"])
        assert s.previous()["a.b"].state_since == later + timedelta(days=1)


def test_history_is_appended_and_pruned_after_180_days(tmp_path):
    with Store(tmp_path / "h.db") as s:
        old = NOW - timedelta(days=RETENTION_DAYS + 1)
        rec(s, now=old)
        rec(s, now=NOW)
        run(s, old)
        run(s, NOW)
        s.prune(NOW)
        s.commit()
        assert s.con.execute("SELECT COUNT(*) FROM source_history").fetchone()[0] == 1
        assert s.con.execute("SELECT COUNT(*) FROM check_runs").fetchone()[0] == 1


def test_forget_missing_drops_only_sources_not_in_the_run(tmp_path):
    with Store(tmp_path / "h.db") as s:
        rec(s, "keep.me")
        rec(s, "drill.synthetic", state="alarm")
        assert s.forget_missing({"keep.me"}) == ["drill.synthetic"]
        s.commit()
        assert set(s.previous()) == {"keep.me"}


def test_forget_clears_a_source_and_its_history(tmp_path):
    with Store(tmp_path / "h.db") as s:
        rec(s, "drill.synthetic")
        assert s.forget("drill.synthetic") is True
        assert s.forget("drill.synthetic") is False
        assert s.con.execute("SELECT COUNT(*) FROM source_history").fetchone()[0] == 0


def test_first_run_at_is_the_earliest_run(tmp_path):
    with Store(tmp_path / "h.db") as s:
        assert s.first_run_at() is None
        run(s, NOW)
        run(s, NOW + timedelta(days=1))
        assert s.first_run_at() == NOW


# --- the /health block --------------------------------------------------------------------------

def test_health_block_is_ok_after_a_recent_run_and_counts_red_sources(tmp_path):
    path = tmp_path / "h.db"
    with Store(path) as s:
        rec(s, "a", "alarm")
        rec(s, "b", "error")
        rec(s, "c", "warn")
        rec(s, "d", "ok")
        run(s, NOW)
        s.commit()
    block = health_block(path, now=NOW + timedelta(hours=7, minutes=12))
    assert block == {"checker": "ok", "last_run_age_h": 7.2, "alarms": 2}


def test_health_block_turns_late_after_36_hours(tmp_path):
    path = tmp_path / "h.db"
    with Store(path) as s:
        run(s, NOW)
    just_in = NOW + timedelta(minutes=2, hours=LATE_AFTER_HOURS)
    assert health_block(path, now=just_in)["checker"] == "ok"
    assert health_block(path, now=just_in + timedelta(minutes=1))["checker"] == "late"


def test_health_block_ignores_a_crashed_run(tmp_path):
    path = tmp_path / "h.db"
    with Store(path) as s:
        run(s, NOW, error="RuntimeError: boom")
    assert health_block(path, now=NOW + timedelta(hours=1))["checker"] == "late"


@pytest.mark.parametrize("make", ["missing", "garbage"])
def test_health_block_never_raises(tmp_path, make):
    path = tmp_path / "h.db"
    if make == "garbage":
        path.write_text("not a database")
    assert health_block(path)["checker"] == "late"


def test_readonly_open_cannot_write(tmp_path):
    path = tmp_path / "h.db"
    with Store(path):
        pass
    with open_readonly(path) as con:
        with pytest.raises(Exception):
            con.execute("DELETE FROM check_runs")


def test_open_readonly_of_a_missing_file_yields_none(tmp_path):
    with open_readonly(tmp_path / "nope.db") as con:
        assert con is None


def test_health_endpoint_carries_the_block_and_stays_200_when_data_health_is_red(tmp_path):
    from fastapi.testclient import TestClient
    from backend.main import app

    path = tmp_path / "h.db"
    with Store(path) as s:
        for i in range(5):
            rec(s, f"s{i}", "alarm", alerted_state="alarm", alerted_at=NOW)
        run(s, datetime.now(timezone.utc) - timedelta(hours=3))
        s.commit()
    probe = MagicMock()
    probe.__aenter__ = AsyncMock(return_value=probe)
    probe.__aexit__ = AsyncMock(return_value=False)
    probe.get = AsyncMock(return_value=MagicMock(status_code=200))
    with patch("backend.main.httpx.AsyncClient", return_value=probe), \
            patch("backend.main.db") as mock_db, \
            patch("backend.main.get_settings") as gs:
        mock_db._get_db.return_value.execute = AsyncMock()
        gs.return_value = MagicMock(ptaxsim_enabled=False, qdrant_url="http://q", data_health_db_path=path)
        resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    block = resp.json()["data_health"]
    assert block["checker"] == "ok" and block["alarms"] == 5 and 2.9 <= block["last_run_age_h"] <= 3.1
