"""The checker. Today: ``python -m backend.data_health.check --dry-run``.

Runs every registry probe against the live services, evaluates each, and prints a table.
Writes nothing and alerts nobody (storage, the daily timer and Sentry arrive in WS6 M2).
No model calls: HTTP reads only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from datetime import date

from backend.data_health.evaluate import ALERTING, ProbeResult, Status, evaluate
from backend.data_health.probes import ProbeContext, make_client, run_probe
from backend.data_health.registry import SOURCES, SourceSpec

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
) -> tuple[list[Row], int]:
    """Probe and evaluate ``specs``. Returns the rows and the total HTTP request count."""
    today = today or date.today()
    client, total = make_client(transport)
    ctx = ProbeContext(client=client, sem=asyncio.Semaphore(concurrency), today=today)
    try:
        results = await asyncio.gather(*(run_probe(s, ctx) for s in specs))
    finally:
        await client.aclose()
    prev = previous_errors or set()
    rows = [Row(s, r, evaluate(s, r, today, previous_error=s.id in prev)) for s, r in zip(specs, results)]
    # Second pass: a source with a working fallback can only warn, so it needs its peer's state.
    peers = {r.spec.id: r.status.state for r in rows}
    for r in rows:
        if r.spec.warns_only_while_ok:
            r.status = evaluate(r.spec, r.probe, today, previous_error=r.spec.id in prev, peers=peers)
    return rows, total()


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
    p = argparse.ArgumentParser(description="Check every registered data source (no writes, no model calls).")
    p.add_argument("--dry-run", action="store_true", help="probe and print; the only mode until WS6 M2")
    p.add_argument("--only", help="comma-separated source ids (a prefix ending in '.' selects a family)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--today", type=date.fromisoformat, help="judge ages against this date (default: today)")
    p.add_argument("--concurrency", type=int, default=8)
    args = p.parse_args(argv)
    if not args.dry_run:
        p.error("only --dry-run exists yet (storage and alerting arrive in WS6 M2)")
    specs = SOURCES
    if args.only:
        wanted = [w.strip() for w in args.only.split(",") if w.strip()]
        specs = tuple(s for s in SOURCES if any(s.id == w or (w.endswith(".") and s.id.startswith(w)) for w in wanted))
        if not specs:
            p.error(f"no source matches {args.only!r}")
    started = time.monotonic()
    rows, requests = asyncio.run(run_all(specs, today=args.today, concurrency=args.concurrency))
    seconds = time.monotonic() - started
    print(to_json(rows, requests, seconds) if args.json else render(rows, requests, seconds))
    return 0


if __name__ == "__main__":
    sys.exit(main())
