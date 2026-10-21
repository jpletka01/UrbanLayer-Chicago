"""The admin Data health panel's payload and endpoint (WS6 M3)."""

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.data_health import panel
from backend.data_health.registry import SOURCES
from backend.data_health.store import Store

NOW = datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc)
LIVE = [s for s in SOURCES if not s.retired]


def _rec(store, sid, state, *, now=NOW, severity="standard", reason="", as_of=None, basis=None, age=None):
    store.record(source_id=sid, state=state, reason=reason, severity=severity, as_of=as_of, basis=basis, age_days=age,
                 now=now, probe_error=False, latency_ms=12, requests=1, prev=store.previous().get(sid),
                 alerted_state=None, alerted_at=None)


def _run(store, at, error=None):
    rid = store.start_run(at)
    store.finish_run(rid, at + timedelta(minutes=2), sources=len(LIVE), alarms=0, requests=100, error=error)


@pytest.fixture
def db(tmp_path):
    return tmp_path / "data_health.db"


def test_a_missing_store_is_a_late_checker_not_an_error(tmp_path):
    p = panel.build_panel(tmp_path / "nope.db", NOW)
    assert p["checker"]["state"] == "late" and p["checker"]["last_run"] is None and p["sources"] == []
    assert p["checker"]["next_run"] == "2026-10-23T05:37:00+00:00"


def test_an_unreadable_store_is_a_late_checker(tmp_path):
    bad = tmp_path / "bad.db"
    bad.write_text("not a database")
    assert panel.build_panel(bad, NOW)["checker"]["state"] == "late"


def test_every_registered_source_has_a_row_even_before_its_first_check(db):
    with Store(db) as s:
        _run(s, NOW - timedelta(hours=3))
        s.commit()
    p = panel.build_panel(db, NOW)
    assert {r["id"] for r in p["sources"]} == {s.id for s in LIVE}
    assert {r["state"] for r in p["sources"]} == {"unknown"} and p["counts"] == {"unknown": len(LIVE)}


def test_rows_sort_worst_first_with_critical_leading_each_state(db):
    crit = next(s.id for s in LIVE if s.severity == "critical")
    std = [s.id for s in LIVE if s.severity != "critical"]
    with Store(db) as s:
        _rec(s, std[0], "ok")
        _rec(s, std[1], "acked")
        _rec(s, std[2], "warn")
        _rec(s, std[3], "alarm")
        _rec(s, std[4], "error")
        _rec(s, std[5], "alarm")
        _rec(s, crit, "alarm", severity="critical")
        _run(s, NOW - timedelta(hours=1))
        s.commit()
    ids = [r["id"] for r in panel.build_panel(db, NOW)["sources"]]
    assert ids[0] == crit                                    # the critical alarm leads the alarms
    assert ids[1:3] == sorted([std[3], std[5]])              # then the standard ones, by id
    assert ids[3] == std[4]                                  # error after alarm
    assert ids[4] == std[2]                                  # warn
    rest = [r["state"] for r in panel.build_panel(db, NOW)["sources"]][5:]
    assert rest == sorted(rest, key=lambda st: panel._RANK[st])  # unknown, acked, ok last, in rank order


def test_a_stale_source_comes_first_and_red_with_its_reason(db):
    """Plan §8(e): the stored stale/broken sources are what the admin sees first."""
    with Store(db) as s:
        _rec(s, "drill.synthetic", "alarm", severity="critical", reason="newest data 2025-09-01 is 400 days old",
             as_of="2025-09-01", basis="content", age=415)
        _run(s, NOW - timedelta(hours=1))
        s.commit()
    first = panel.build_panel(db, NOW)["sources"][0]
    assert first["id"] == "drill.synthetic" and first["state"] == "alarm" and first["severity"] == "critical"
    assert first["age_days"] == 415 and "400 days old" in first["reason"] and first["name"] == "drill.synthetic"


def test_counts_match_the_store_and_the_health_block(db):
    from backend.data_health.store import health_block

    with Store(db) as s:
        for i, st in enumerate(["alarm", "error", "error", "warn", "ok", "ok", "ok", "acked"]):
            _rec(s, LIVE[i].id, st)
        _run(s, NOW - timedelta(hours=2))
        s.commit()
    p = panel.build_panel(db, NOW)
    assert p["counts"]["alarm"] == 1 and p["counts"]["error"] == 2 and p["counts"]["warn"] == 1 and p["counts"]["acked"] == 1
    assert p["counts"]["ok"] == 3 and sum(p["counts"].values()) == len(LIVE)
    assert health_block(db, NOW)["alarms"] == p["counts"]["alarm"] + p["counts"]["error"]


def test_the_checker_is_late_after_36_hours_and_ok_before(db):
    with Store(db) as s:
        _run(s, NOW - timedelta(hours=40))
        s.commit()
    late = panel.build_panel(db, NOW)["checker"]
    assert late["state"] == "late" and late["age_h"] == pytest.approx(39.97, abs=0.1) and late["late_after_h"] == 36
    with Store(db) as s:
        _run(s, NOW - timedelta(hours=5))
        s.commit()
    assert panel.build_panel(db, NOW)["checker"]["state"] == "ok"


def test_a_failed_run_does_not_count_as_the_last_run_and_its_error_is_shown(db):
    with Store(db) as s:
        _run(s, NOW - timedelta(hours=30))
        _run(s, NOW - timedelta(hours=1), error="database is locked")
        s.commit()
    c = panel.build_panel(db, NOW)["checker"]
    assert c["state"] == "ok" and c["age_h"] > 29 and c["last_error"] == "database is locked"
    assert len(c["runs"]) == 2 and c["runs"][0]["error"] == "database is locked"


def test_the_ack_carries_its_reason_and_expiry(db):
    acked = next(s for s in LIVE if s.ack)
    with Store(db) as s:
        _rec(s, acked.id, "acked", reason="acked until ...")
        _run(s, NOW - timedelta(hours=1))
        s.commit()
    row = next(r for r in panel.build_panel(db, NOW)["sources"] if r["id"] == acked.id)
    assert row["ack"] == {"reason": acked.ack.reason, "until": acked.ack.until.isoformat(), "owner": acked.ack.owner}


def test_the_publisher_link_points_at_the_dataset_or_service():
    soc = next(s for s in LIVE if s.kind == "socrata")
    _, dataset = soc.locator.split(":")
    assert panel.publisher_link(soc).endswith(f"/d/{dataset}") and panel.publisher_link(soc).startswith("https://")
    layer = next(s for s in LIVE if s.kind == "arcgis_layer")
    assert panel.publisher_link(layer) == layer.locator
    assert panel.publisher_link(next(s for s in LIVE if s.kind == "artifact")) is None


def test_history_is_a_90_day_strip_oldest_first(db):
    with Store(db) as s:
        _rec(s, "a.b", "ok", now=NOW - timedelta(days=120))
        for d, st in ((60, "ok"), (30, "warn"), (1, "alarm")):
            _rec(s, "a.b", st, now=NOW - timedelta(days=d))
        _rec(s, "c.d", "ok", now=NOW - timedelta(days=1))
        s.commit()
    h = panel.build_history(db, "a.b", NOW)
    assert [p["state"] for p in h["history"]] == ["ok", "warn", "alarm"] and h["source"] == "a.b"
    assert panel.build_history(db, "zzz", NOW)["history"] == []
    assert panel.build_history(db.parent / "none.db", "a.b", NOW)["history"] == []


def test_next_run_is_the_timers_0537_utc():
    assert panel.next_run(datetime(2026, 10, 22, 5, 0, tzinfo=timezone.utc)).isoformat() == "2026-10-22T05:37:00+00:00"
    assert panel.next_run(datetime(2026, 10, 22, 5, 37, tzinfo=timezone.utc)).isoformat() == "2026-10-23T05:37:00+00:00"


def test_the_module_imports_none_of_the_serving_stack():
    code = "import sys, backend.data_health.panel; bad=[m for m in ('torch','backend.main','backend.discovery') if m in sys.modules]; print(bad)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[2]))
    assert out.stdout.strip() == "[]", out.stdout + out.stderr


# --- the endpoint ---------------------------------------------------------------------------------

@pytest.fixture
def client(db):
    from backend import main

    with patch("backend.main.get_settings") as s, patch("backend.main.db") as mdb, \
            patch("backend.retrieval.vector_search._get_known_sections", new=AsyncMock(return_value=frozenset())):
        s.return_value = MagicMock(anthropic_api_key="k", socrata_app_token="t", qdrant_url="http://localhost:6333",
                                   router_model="m", synthesizer_model="m", message_limit=10, data_health_db_path=db)
        mdb.init_db = AsyncMock()
        mdb.close_db = AsyncMock()
        yield TestClient(main.app)


def test_the_endpoint_is_admin_only_and_serves_the_panel_and_history(client, db):
    from backend import main
    from backend.auth import require_admin

    route = next(r for r in main.app.routes if getattr(r, "path", "") == "/api/admin/data-health")
    assert require_admin in [d.call for d in route.dependant.dependencies]
    with Store(db) as s:
        _rec(s, LIVE[0].id, "alarm", severity="critical", reason="stale")
        _run(s, datetime.now(timezone.utc) - timedelta(hours=1))
        s.commit()
    main.app.dependency_overrides[require_admin] = lambda: {"id": 1, "tier": "admin"}
    try:
        d = client.get("/api/admin/data-health").json()
        h = client.get(f"/api/admin/data-health?source={LIVE[0].id}").json()
    finally:
        main.app.dependency_overrides.pop(require_admin, None)
    assert d["sources"][0]["id"] == LIVE[0].id and d["sources"][0]["state"] == "alarm" and d["checker"]["state"] == "ok"
    assert h["source"] == LIVE[0].id and [p["state"] for p in h["history"]] == ["alarm"]
