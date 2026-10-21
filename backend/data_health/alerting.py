"""Sentry alarms and the cron check-in for the daily checker (WS6 plan §3.5).

One Sentry issue per source and state, so Sentry's new-issue email is the page:
- a source *entering* ``alarm`` / ``error``: one ``error`` event, fingerprint ``["data-health", id, state]``;
- still red on a later day: one more event a day with the same fingerprint (bumps the count, no new email);
- recovered: an ``info`` event; ``warn`` never reaches Sentry (it lives on the admin panel).

For the first ``QUIET_DAYS`` after the checker's first run only ``critical`` sources alert; the rest are
on the panel. What we last notified about lives in the store (``alerted_state``), so a source that was
held back by the quiet period alerts as a new transition when the period ends.

The Sentry SDK is behind :class:`Sink` so tests inject a fake and CI (which doesn't install the SDK) needs
nothing. :class:`SentrySink` imports it lazily, only when ``SENTRY_DSN`` is set.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from backend.data_health.evaluate import ALERTING

log = logging.getLogger(__name__)

QUIET_DAYS = 14
MONITOR_SLUG = "data-health-check"
# 05:37 UTC daily; a run may start up to 90 min late and take 30 min before Sentry calls it missed.
MONITOR_CONFIG = {
    "schedule": {"type": "crontab", "value": "37 5 * * *"},
    "timezone": "UTC",
    "checkin_margin": 90,
    "max_runtime": 30,
    "failure_issue_threshold": 1,
    "recovery_threshold": 1,
}


class Sink(Protocol):
    def event(self, message: str, level: str, fingerprint: list[str], tags: dict[str, str], extra: dict) -> None: ...
    def checkin(self, status: str, check_in_id: str | None = None) -> str | None: ...
    def flush(self) -> None: ...


class NullSink:
    """No Sentry DSN: log and carry on."""

    def event(self, message, level, fingerprint, tags, extra) -> None:
        log.info("data-health %s: %s %s", level, message, tags)

    def checkin(self, status, check_in_id=None):
        return None

    def flush(self) -> None:
        pass


class SentrySink:
    def __init__(self, dsn: str):
        import sentry_sdk

        sentry_sdk.init(dsn=dsn, send_default_pii=False, traces_sample_rate=0)
        self._sdk = sentry_sdk

    def event(self, message, level, fingerprint, tags, extra) -> None:
        with self._sdk.new_scope() as scope:
            scope.fingerprint = fingerprint
            for k, v in tags.items():
                scope.set_tag(k, v)
            scope.set_context("data_health", extra)
            self._sdk.capture_message(message, level=level, scope=scope)

    def checkin(self, status, check_in_id=None):
        from sentry_sdk.crons import capture_checkin

        return capture_checkin(monitor_slug=MONITOR_SLUG, check_in_id=check_in_id, status=status,
                               monitor_config=MONITOR_CONFIG)

    def flush(self) -> None:
        self._sdk.flush(timeout=10)


def make_sink(dsn: str) -> Sink:
    if not dsn:
        return NullSink()
    try:
        return SentrySink(dsn)
    except Exception:  # SDK missing or init failed: alarms must not take the run down
        log.exception("Sentry unavailable; data-health alarms will only be logged")
        return NullSink()


@dataclass
class Decision:
    """What to tell Sentry about one source this run, and what to remember afterwards."""

    action: str                       # "transition" | "heartbeat" | "recovered" | "none"
    alerted_state: str | None
    alerted_at: datetime | None


_KIND = {"alarm": "stale", "error": "broken"}


def decide(*, state: str, severity: str, prev_alerted: str | None, prev_alerted_at: datetime | None,
           now: datetime, quiet: bool) -> Decision:
    if state in ALERTING:
        if quiet and severity != "critical":
            return Decision("none", prev_alerted, prev_alerted_at)
        if prev_alerted != state:
            return Decision("transition", state, now)
        if prev_alerted_at is None or prev_alerted_at.date() < now.date():
            return Decision("heartbeat", state, now)
        return Decision("none", prev_alerted, prev_alerted_at)
    if prev_alerted is not None:
        return Decision("recovered", None, None)
    return Decision("none", None, None)


def in_quiet_period(first_run: datetime | None, now: datetime) -> bool:
    """True until ``QUIET_DAYS`` after the first run ever recorded (and on the first run itself)."""
    return first_run is None or now < first_run + timedelta(days=QUIET_DAYS)


def send(sink: Sink, decision: Decision, *, source_id: str, state: str, severity: str, reason: str,
         source_kind: str, name: str) -> bool:
    """Send the event a decision calls for. Returns True if one went out."""
    if decision.action == "none":
        return False
    tags = {"source_id": source_id, "severity": severity, "kind": _KIND.get(state, "stale"), "source_kind": source_kind}
    extra = {"state": state, "reason": reason, "name": name}
    if decision.action == "recovered":
        sink.event(f"Data source recovered: {source_id}", "info", ["data-health", source_id, "recovered"],
                   {**tags, "kind": "recovered"}, extra)
        return True
    kind = _KIND[state]
    sink.event(f"Data source {kind}: {source_id}", "error", ["data-health", source_id, state], tags,
               {**extra, "heartbeat": decision.action == "heartbeat"})
    return True

