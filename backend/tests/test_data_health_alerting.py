"""Alarms and the dead-man (WS6 M2): the required test of plan §8, layer 1.

A fake registry of three sources, a fake Sentry sink, and ``check(write=True, alert=True)``.
"""

import asyncio
import contextlib
import sys
import types
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.data_health import alerting, check
from backend.data_health.evaluate import ProbeError, ProbeResult
from backend.data_health.probes import PROBES
from backend.data_health.registry import Contract, SourceSpec
from backend.data_health.store import Store

T0 = datetime(2026, 10, 21, 5, 37, tzinfo=timezone.utc)
DAY = timedelta(days=1)


class FakeSink:
    """Stands in for Sentry: records every event and check-in."""

    def __init__(self):
        self.events: list[dict] = []
        self.checkins: list[tuple[str, str | None]] = []
        self.flushed = 0

    def event(self, message, level, fingerprint, tags, extra):
        self.events.append(dict(message=message, level=level, fingerprint=fingerprint, tags=tags, extra=extra))

    def checkin(self, status, check_in_id=None):
        self.checkins.append((status, check_in_id))
        return "ci-1"

    def flush(self):
        self.flushed += 1

    def fingerprints(self):
        return [tuple(e["fingerprint"]) for e in self.events]


def spec(sid, probe, **kw):
    base = SourceSpec(id=sid, name=sid, publisher="Test", tier="official_record", kind="socrata", locator="city:abcd-1234",
                      owner_modules=("backend/config.py",), severity="critical", probe=probe, warn_days=30, alarm_days=90)
    return replace(base, **kw)


@pytest.fixture
def world(monkeypatch):
    """Three sources whose behaviour the test steers through ``w``."""
    w = {"stale": True, "fields": False, "raises": True}

    async def stale(s, ctx):
        return ProbeResult(content=ctx.today - timedelta(days=400 if w["stale"] else 1))

    async def fields(s, ctx):
        return ProbeResult(content=ctx.today, fields=("OBJECTID", "ZONE_CLASS") if w["fields"] else ("OBJECTID",))

    async def raises(s, ctx):
        if w["raises"]:
            raise ProbeError("transient", "ConnectError")
        return ProbeResult(content=ctx.today)

    for name, fn in (("t_stale", stale), ("t_fields", fields), ("t_raises", raises)):
        monkeypatch.setitem(PROBES, name, fn)
    specs = (
        spec("test.stale", "t_stale"),
        spec("test.fields", "t_fields", contract=Contract(required_fields=("ZONE_CLASS",))),
        spec("test.raises", "t_raises"),
    )
    return w, specs


def go(specs, tmp_path, sink, now, **kw):
    return asyncio.run(check.check(specs, write=True, alert=True, store_path=tmp_path / "h.db", sink=sink, now=now, **kw))


def states(result):
    return {r.spec.id: r.status.state for r in result.rows}


def test_stale_and_broken_sources_raise_exactly_one_alert_each(world, tmp_path):
    """Plan §8, layer 1 (a)-(d)."""
    w, specs = world
    sink = FakeSink()

    # (a) run 1: stale -> alarm, missing field -> error, the first probe failure -> warn (a blip)
    r1 = go(specs, tmp_path, sink, T0)
    assert states(r1) == {"test.stale": "alarm", "test.fields": "error", "test.raises": "warn"}
    # (b) one event per red source, with the fingerprint and tags Sentry groups by; warn sends nothing
    assert sorted(sink.fingerprints()) == [("data-health", "test.fields", "error"), ("data-health", "test.stale", "alarm")]
    stale = next(e for e in sink.events if e["fingerprint"][1] == "test.stale")
    assert stale["message"] == "Data source stale: test.stale" and stale["level"] == "error"
    assert stale["tags"]["source_id"] == "test.stale" and stale["tags"]["severity"] == "critical" and stale["tags"]["kind"] == "stale"
    broken = next(e for e in sink.events if e["fingerprint"][1] == "test.fields")
    assert broken["message"] == "Data source broken: test.fields" and broken["tags"]["kind"] == "broken"
    assert "ZONE_CLASS" in broken["extra"]["reason"]
    assert sink.checkins == [("in_progress", None), ("ok", "ci-1")] and sink.flushed == 1

    # (c) the same run again, minutes later. The two red sources stay silent (their issue is open). The blip
    # repeated, which is "failed twice in a row": warn -> alarm, a new issue.
    n = len(sink.events)
    r2 = go(specs, tmp_path, sink, T0 + timedelta(minutes=5))
    assert states(r2)["test.raises"] == "alarm"
    assert sink.fingerprints()[n:] == [("data-health", "test.raises", "alarm")]

    # the next day: every red source sends a heartbeat with the SAME fingerprint (bumps the count, no new email)
    n = len(sink.events)
    go(specs, tmp_path, sink, T0 + DAY)
    new = sink.events[n:]
    assert sorted(tuple(e["fingerprint"]) for e in new) == [
        ("data-health", "test.fields", "error"), ("data-health", "test.raises", "alarm"), ("data-health", "test.stale", "alarm")]
    assert all(e["extra"]["heartbeat"] for e in new)

    # (d) recovery: an info event per source, then silence
    w.update(stale=False, fields=True, raises=False)
    n = len(sink.events)
    r4 = go(specs, tmp_path, sink, T0 + 2 * DAY)
    assert set(states(r4).values()) == {"ok"}
    rec = sink.events[n:]
    assert sorted(e["message"] for e in rec) == [
        "Data source recovered: test.fields", "Data source recovered: test.raises", "Data source recovered: test.stale"]
    assert {e["level"] for e in rec} == {"info"}
    go(specs, tmp_path, sink, T0 + 3 * DAY)
    assert len(sink.events) == n + 3


def test_the_store_holds_what_the_run_found(world, tmp_path):
    w, specs = world
    go(specs, tmp_path, FakeSink(), T0)
    with Store(tmp_path / "h.db") as s:
        prev = s.previous()
        assert {k: v.state for k, v in prev.items()} == {"test.stale": "alarm", "test.fields": "error", "test.raises": "warn"}
        assert prev["test.raises"].probe_error and prev["test.stale"].alerted_state == "alarm"
        assert s.con.execute("SELECT sources, alarms, error FROM check_runs").fetchone()[:] == (3, 2, None)


def test_a_standard_source_is_held_back_for_the_first_two_weeks_then_alerts(world, tmp_path):
    w, specs = world
    specs = tuple(replace(s, severity="standard") if s.id == "test.stale" else s for s in specs)
    sink = FakeSink()
    go(specs, tmp_path, sink, T0)
    assert ("data-health", "test.stale", "alarm") not in sink.fingerprints()      # still on the panel
    assert ("data-health", "test.fields", "error") in sink.fingerprints()          # critical: straight away
    go(specs, tmp_path, sink, T0 + timedelta(days=13))
    assert ("data-health", "test.stale", "alarm") not in sink.fingerprints()
    go(specs, tmp_path, sink, T0 + timedelta(days=15))
    assert sink.fingerprints().count(("data-health", "test.stale", "alarm")) == 1  # a new issue once the period ends


def test_warn_never_reaches_sentry(world, tmp_path):
    w, specs = world
    sink = FakeSink()
    go((specs[2],), tmp_path, sink, T0)
    assert sink.events == []


def test_an_ack_keeps_a_source_amber_and_quiet(world, tmp_path):
    from backend.data_health.registry import Ack
    w, specs = world
    acked = replace(specs[0], ack=Ack("known", date(2026, 12, 1), "jack"))
    sink = FakeSink()
    r = go((acked,), tmp_path, sink, T0)
    assert states(r) == {"test.stale": "acked"} and sink.events == []
    # the ack expires: it becomes an alarm and alerts
    r = go((acked,), tmp_path, sink, datetime(2026, 12, 2, 5, 37, tzinfo=timezone.utc))
    assert states(r) == {"test.stale": "alarm"} and len(sink.events) == 1


def test_alerting_needs_the_store(world, tmp_path):
    with pytest.raises(ValueError):
        asyncio.run(check.check(world[1], write=False, alert=True, sink=FakeSink(), now=T0))


def test_a_crash_is_recorded_and_checked_in_as_an_error(world, tmp_path, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(check, "run_all", boom)
    sink = FakeSink()
    with pytest.raises(RuntimeError):
        go(world[1], tmp_path, sink, T0)
    assert sink.checkins == [("in_progress", None), ("error", "ci-1")]
    with Store(tmp_path / "h.db") as s:
        assert "disk on fire" in s.con.execute("SELECT error FROM check_runs").fetchone()[0]
        assert s.last_run_finished() is None            # a crashed run is not a healthy checker


# --- the drill ----------------------------------------------------------------------------------

def test_drill_stale_creates_the_issue_and_the_next_run_resolves_it(world, tmp_path):
    w, specs = world
    w.update(stale=False, fields=True, raises=False)
    today = T0.date()
    drill, canned = check.parse_fault("stale:drill.synthetic", today)
    sink = FakeSink()
    r = go(specs + (drill,), tmp_path, sink, T0, overrides={drill.id: canned})
    assert states(r)["drill.synthetic"] == "alarm"
    [e] = sink.events
    assert e["message"] == "Data source stale: drill.synthetic" and e["tags"]["source_id"] == "drill.synthetic"
    assert e["tags"]["severity"] == "critical"
    # the next normal run no longer has the drill source: its row goes and Sentry hears a recovery
    go(specs, tmp_path, sink, T0 + DAY)
    assert sink.events[-1]["message"] == "Data source recovered: drill.synthetic"
    with Store(tmp_path / "h.db") as s:
        assert "drill.synthetic" not in s.previous()


def test_drill_broken_is_an_error_and_only_drill_ids_are_accepted():
    drill, canned = check.parse_fault("broken:drill.x", T0.date())
    assert canned.error is not None and canned.error.kind == "service"
    for bad in ("stale:chi.crime", "weird:drill.x", "drill.x"):
        with pytest.raises(ValueError):
            check.parse_fault(bad, T0.date())


def test_cli_rejects_nonsense_combinations(tmp_path, capsys):
    for argv in (["--alert", "--write", "--dry-run"], ["--write", "--only", "chi."], []):
        with pytest.raises(SystemExit):
            check.main(argv)


def test_cli_clear_removes_a_drill_row(world, tmp_path, monkeypatch, capsys):
    w, specs = world
    drill, canned = check.parse_fault("broken:drill.synthetic", T0.date())
    go(specs + (drill,), tmp_path, FakeSink(), T0, overrides={drill.id: canned})
    monkeypatch.setattr("backend.config.get_settings",
                        lambda: types.SimpleNamespace(data_health_db_path=tmp_path / "h.db", sentry_dsn=""))
    assert check.main(["--clear", "drill.synthetic"]) == 0
    assert "cleared drill.synthetic" in capsys.readouterr().out
    with Store(tmp_path / "h.db") as s:
        assert "drill.synthetic" not in s.previous()


# --- decide() -----------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "state,prev,prev_at,quiet,sev,action",
    [
        ("alarm", None, None, False, "critical", "transition"),
        ("error", "alarm", T0, False, "critical", "transition"),         # alarm -> error is a different issue
        ("alarm", "alarm", T0, False, "critical", "none"),                # same day
        ("alarm", "alarm", T0 - DAY, False, "critical", "heartbeat"),
        ("ok", "alarm", T0, False, "critical", "recovered"),
        ("warn", "alarm", T0, False, "critical", "recovered"),            # improved below red
        ("ok", None, None, False, "critical", "none"),
        ("alarm", None, None, True, "standard", "none"),                  # quiet period, not critical
        ("alarm", None, None, True, "critical", "transition"),
    ],
)
def test_decide(state, prev, prev_at, quiet, sev, action):
    d = alerting.decide(state=state, severity=sev, prev_alerted=prev, prev_alerted_at=prev_at, now=T0, quiet=quiet)
    assert d.action == action


# --- the real sink, with a fake SDK -------------------------------------------------------------

def test_sentry_sink_sets_fingerprint_tags_and_the_cron_monitor(monkeypatch):
    calls: dict = {"tags": {}, "captured": [], "checkins": []}

    class Scope:
        fingerprint = None

        def set_tag(self, k, v):
            calls["tags"][k] = v

        def set_context(self, k, v):
            calls["ctx"] = (k, v)

    sdk = types.ModuleType("sentry_sdk")
    sdk.init = lambda **kw: calls.setdefault("init", kw)
    sdk.new_scope = lambda: contextlib.nullcontext(Scope())
    sdk.capture_message = lambda msg, level=None, scope=None: calls["captured"].append((msg, level, scope.fingerprint))
    sdk.flush = lambda timeout=None: calls.setdefault("flush", timeout)
    crons = types.ModuleType("sentry_sdk.crons")
    crons.capture_checkin = lambda **kw: calls["checkins"].append(kw) or "id-9"
    monkeypatch.setitem(sys.modules, "sentry_sdk", sdk)
    monkeypatch.setitem(sys.modules, "sentry_sdk.crons", crons)

    sink = alerting.make_sink("https://dsn@example.invalid/1")
    assert isinstance(sink, alerting.SentrySink) and calls["init"]["send_default_pii"] is False
    alerting.send(sink, alerting.Decision("transition", "alarm", T0), source_id="a.b", state="alarm", severity="critical",
                  reason="old", source_kind="socrata", name="A B")
    assert calls["captured"] == [("Data source stale: a.b", "error", ["data-health", "a.b", "alarm"])]
    assert calls["tags"] == {"source_id": "a.b", "severity": "critical", "kind": "stale", "source_kind": "socrata"}
    assert sink.checkin("in_progress") == "id-9"
    ci = calls["checkins"][0]
    assert ci["monitor_slug"] == "data-health-check" and ci["monitor_config"]["schedule"]["value"] == "37 5 * * *"


def test_no_dsn_or_a_broken_sdk_degrades_to_logging(monkeypatch):
    assert isinstance(alerting.make_sink(""), alerting.NullSink)
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)       # import raises
    assert isinstance(alerting.make_sink("https://dsn@example.invalid/1"), alerting.NullSink)
