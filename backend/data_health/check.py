"""The checker.

    python -m backend.data_health.check --dry-run                 # probe, print, write nothing
    python -m backend.data_health.check --write --alert           # the daily timer's command
    python -m backend.data_health.check --write --alert --inject-fault stale:drill.synthetic
    python -m backend.data_health.check --clear drill.synthetic   # drop a drill row

Runs every registry probe against the live services, evaluates each, and prints a table. With
``--write`` it stores the result (``data_health.db``); with ``--alert`` it also tells Sentry about
transitions (``alerting.py``) and sends the Sentry Cron check-in. No model calls: HTTP reads and
local files only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from backend.data_health import alerting
from backend.data_health.evaluate import ALERTING, ProbeError, ProbeResult, Status, evaluate
from backend.data_health.probes import ProbeContext, make_client, run_probe
from backend.data_health.registry import SOURCES, SourceSpec
from backend.data_health.store import Store

_ORDER = {"error": 0, "alarm": 1, "warn": 2, "acked": 3, "unknown": 4, "ok": 5, "frozen_ok": 6}
_MARK = {"error": "ERR ", "alarm": "ALRM", "warn": "warn", "acked": "ack ", "unknown": "?   ", "ok": "ok  ", "frozen_ok": "froz"}


@dataclass
class Row:
    spec: SourceSpec
    probe: ProbeResult | None
    status: Status


async def run_all(
    specs: tuple[SourceSpec, ...] = SOURCES, *, today: date | None = None, concurrency: int = 8,
    previous_errors: set[str] | None = None, transport=None,
    overrides: dict[str, ProbeResult] | None = None, live_calls: dict[str, tuple[int, int]] | None = None,
) -> tuple[list[Row], int]:
    """Probe and evaluate ``specs``. Returns the rows and the total HTTP request count.

    ``overrides`` replaces a source's probe with a canned result (the fault-injection drill)."""
    today = today or date.today()
    overrides = overrides or {}
    if live_calls is None:
        from backend.data_health import live

        live_calls = live.read_window()  # the app's own call outcomes over the last day; {} when it has none
    client, total = make_client(transport)
    ctx = ProbeContext(client=client, sem=asyncio.Semaphore(concurrency), today=today)

    async def probe(s: SourceSpec) -> ProbeResult | None:
        return overrides[s.id] if s.id in overrides else await run_probe(s, ctx)

    try:
        results = await asyncio.gather(*(probe(s) for s in specs))
    finally:
        await client.aclose()
    prev = previous_errors or set()
    rows = [Row(s, r, evaluate(s, r, today, previous_error=s.id in prev, live=live_calls.get(s.id))) for s, r in zip(specs, results)]
    # Second pass: a source with a working fallback can only warn, so it needs its peer's state.
    peers = {r.spec.id: r.status.state for r in rows}
    for r in rows:
        if r.spec.warns_only_while_ok:
            r.status = evaluate(r.spec, r.probe, today, previous_error=r.spec.id in prev, peers=peers,
                                live=live_calls.get(r.spec.id))
    return rows, total()


DRILL_PREFIX = "drill."


def drill_source(source_id: str) -> SourceSpec:
    """A synthetic critical source for the alarm drill (never in the registry)."""
    return SourceSpec(
        id=source_id, name="Alarm drill (synthetic)", publisher="UrbanLayer", tier="internal", kind="internal",
        locator="drill", probe="none", owner_modules=("backend/data_health/check.py",), severity="critical",
        warn_days=30, alarm_days=90, note="Injected by --inject-fault; removed on the next normal run.",
    )


def parse_fault(text: str, today: date) -> tuple[SourceSpec, ProbeResult]:
    """``stale:drill.x`` (newest data 400 days old) or ``broken:drill.x`` (the service answers with an error)."""
    kind, _, source_id = text.partition(":")
    if kind not in ("stale", "broken") or not source_id.startswith(DRILL_PREFIX):
        raise ValueError(f"--inject-fault takes stale:{DRILL_PREFIX}<name> or broken:{DRILL_PREFIX}<name>, got {text!r}")
    if kind == "stale":
        return drill_source(source_id), ProbeResult(content=today - timedelta(days=400))
    return drill_source(source_id), ProbeResult(error=ProbeError("service", "injected fault: the source returned an error body"))


@dataclass
class CheckResult:
    rows: list[Row]
    requests: int
    sent: list[tuple[str, str]] = field(default_factory=list)   # (source_id, action)
    run_id: int | None = None


async def check(
    specs: tuple[SourceSpec, ...] = SOURCES, *, write: bool = False, alert: bool = False,
    store_path: Path | str | None = None, sink: alerting.Sink | None = None, now: datetime | None = None,
    overrides: dict[str, ProbeResult] | None = None, concurrency: int = 8, transport=None,
) -> CheckResult:
    """One checker run: probe, evaluate, and (with ``write``) store; (with ``alert``) tell Sentry.

    Alerting needs the store: it is how a transition is told from a source that has been red for days."""
    if alert and not write:
        raise ValueError("alerting needs the store: pass write=True")
    now = now or datetime.now(timezone.utc)
    today = now.date()
    if not write:
        rows, requests = await run_all(specs, today=today, concurrency=concurrency, transport=transport, overrides=overrides)
        return CheckResult(rows, requests)

    if store_path is None:
        from backend.config import get_settings
        store_path = get_settings().data_health_db_path
    sink = sink or alerting.NullSink()
    result = CheckResult([], 0)
    with Store(store_path) as store:
        prev = store.previous()
        quiet = alerting.in_quiet_period(store.first_run_at(), now)
        run_id = store.start_run(now)
        result.run_id = run_id
        checkin = sink.checkin("in_progress") if alert else None
        try:
            rows, requests = await run_all(
                specs, today=today, concurrency=concurrency, transport=transport, overrides=overrides,
                previous_errors={sid for sid, p in prev.items() if p.probe_error},
            )
            result.rows, result.requests = rows, requests
            for r in rows:
                p = prev.get(r.spec.id)
                decision = alerting.decide(
                    state=r.status.state, severity=r.spec.severity, prev_alerted=p.alerted_state if p else None,
                    prev_alerted_at=p.alerted_at if p else None, now=now, quiet=quiet,
                ) if alert else alerting.Decision("none", p.alerted_state if p else None, p.alerted_at if p else None)
                if alerting.send(sink, decision, source_id=r.spec.id, state=r.status.state, severity=r.spec.severity,
                                 reason=r.status.reason, source_kind=r.spec.kind, name=r.spec.name):
                    result.sent.append((r.spec.id, decision.action))
                store.record(
                    source_id=r.spec.id, state=r.status.state, reason=r.status.reason, severity=r.spec.severity,
                    as_of=_date(r.status.as_of) if r.status.as_of else None, basis=r.status.basis,
                    age_days=r.status.age_days, now=now, probe_error=bool(r.probe and r.probe.error),
                    latency_ms=r.probe.latency_ms if r.probe else 0, requests=r.probe.requests if r.probe else 0,
                    prev=p, alerted_state=decision.alerted_state, alerted_at=decision.alerted_at,
                )
            for sid in store.forget_missing({r.spec.id for r in rows}):
                gone = prev[sid]
                if alert and gone.alerted_state:
                    recovered = alerting.Decision("recovered", None, None)
                    alerting.send(sink, recovered, source_id=sid, state="ok", severity=gone.severity,
                                  reason="no longer in the registry", source_kind="internal", name=sid)
                    result.sent.append((sid, "recovered"))
            store.prune(now)
            store.finish_run(run_id, datetime.now(timezone.utc), sources=len(rows),
                             alarms=sum(1 for r in rows if r.status.state in ALERTING), requests=requests)
        except BaseException as exc:
            store.finish_run(run_id, datetime.now(timezone.utc), sources=len(result.rows), alarms=0,
                             requests=result.requests, error=f"{type(exc).__name__}: {exc}"[:500])
            if alert:
                sink.checkin("error", checkin)
                sink.flush()
            raise
    if alert:
        sink.checkin("ok", checkin)
        sink.flush()
    return result


def _date(d: date | None) -> str:
    return d.isoformat() if d else "-"


def render(rows: list[Row], requests: int, seconds: float) -> str:
    rows = sorted(rows, key=lambda r: (_ORDER[r.status.state], r.spec.severity != "critical", r.spec.id))
    lines = [f"{'':4} {'source':40} {'sev':4} {'as of':10} {'age':>5}  reason"]
    for r in rows:
        st = r.status
        age = f"{st.age_days}d" if st.age_days is not None and st.age_days >= 0 else "-"
        as_of = (str(st.as_of.year) if st.as_of and r.spec.content and r.spec.content.kind in ("max_year", "release_year")
                 else _date(st.as_of))
        sev = {"critical": "crit", "standard": "std", "info": "info"}[r.spec.severity]
        reason = st.reason if len(st.reason) <= 150 else st.reason[:147] + "..."
        lines.append(f"{_MARK[st.state]} {r.spec.id:40} {sev:4} {as_of:10} {age:>5}  {reason}")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.status.state] = counts.get(r.status.state, 0) + 1
    summary = ", ".join(f"{n} {s}" for s, n in sorted(counts.items(), key=lambda kv: _ORDER[kv[0]]))
    alerting = sum(1 for r in rows if r.status.state in ALERTING)
    lines += ["", f"{len(rows)} sources: {summary}", f"{requests} HTTP requests in {seconds:.0f}s; {alerting} would alert"]
    return "\n".join(lines)


def to_json(rows: list[Row], requests: int, seconds: float) -> str:
    return json.dumps({
        "requests": requests, "seconds": round(seconds, 1),
        "sources": [{
            "id": r.spec.id, "state": r.status.state, "reason": r.status.reason, "as_of": _date(r.status.as_of),
            "basis": r.status.basis, "age_days": r.status.age_days, "severity": r.spec.severity,
            "requests": r.probe.requests if r.probe else 0, "latency_ms": r.probe.latency_ms if r.probe else 0,
        } for r in rows],
    }, indent=2)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Check every registered data source (HTTP reads and local files; no model calls).")
    p.add_argument("--dry-run", action="store_true", help="probe and print; write nothing, alert nobody")
    p.add_argument("--write", action="store_true", help="store the result in data_health.db")
    p.add_argument("--alert", action="store_true", help="tell Sentry about transitions and send the Cron check-in (needs --write)")
    p.add_argument("--inject-fault", metavar="KIND:ID", help=f"alarm drill: stale:{DRILL_PREFIX}x or broken:{DRILL_PREFIX}x")
    p.add_argument("--clear", metavar="ID", help="delete one source's stored rows (a finished drill) and exit")
    p.add_argument("--only", help="comma-separated source ids (a prefix ending in '.' selects a family)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--today", type=date.fromisoformat, help="judge ages against this date (default: today)")
    p.add_argument("--concurrency", type=int, default=8)
    args = p.parse_args(argv)

    from backend.config import get_settings
    settings = get_settings()

    if args.clear:
        with Store(settings.data_health_db_path) as store:
            print(f"cleared {args.clear}" if store.forget(args.clear) else f"{args.clear} not in the store")
        return 0
    if not (args.dry_run or args.write):
        p.error("pass --dry-run (print only) or --write [--alert]")
    if args.dry_run and (args.write or args.alert):
        p.error("--dry-run writes and alerts nothing; drop --write/--alert")
    if args.alert and not args.write:
        p.error("--alert needs --write")
    if args.write and args.only:
        p.error("--write checks every source (a partial run would delete the others' rows)")

    specs = SOURCES
    if args.only:
        wanted = [w.strip() for w in args.only.split(",") if w.strip()]
        specs = tuple(s for s in SOURCES if any(s.id == w or (w.endswith(".") and s.id.startswith(w)) for w in wanted))
        if not specs:
            p.error(f"no source matches {args.only!r}")
    now = datetime.now(timezone.utc)
    if args.today:
        now = datetime.combine(args.today, now.timetz())
    overrides: dict[str, ProbeResult] = {}
    if args.inject_fault:
        try:
            spec, canned = parse_fault(args.inject_fault, now.date())
        except ValueError as exc:
            p.error(str(exc))
        specs = specs + (spec,)
        overrides[spec.id] = canned

    sink = alerting.make_sink(settings.sentry_dsn) if args.alert else None
    started = time.monotonic()
    try:
        result = asyncio.run(check(specs, write=args.write, alert=args.alert, sink=sink, now=now, overrides=overrides,
                                   concurrency=args.concurrency))
    except Exception as exc:
        print(f"checker failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    seconds = time.monotonic() - started
    print(to_json(result.rows, result.requests, seconds) if args.json else render(result.rows, result.requests, seconds))
    if args.alert:
        print(f"Sentry: {len(result.sent)} event(s)" + "".join(f"\n  {sid}: {action}" for sid, action in result.sent)
              + ("" if settings.sentry_dsn else "\n  (no SENTRY_DSN: logged only)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
