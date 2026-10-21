"""Daily legislation sync: what City Council passed since the code text's vintage.

Runs on prod as a oneshot (``deploy/legislation-sync.timer``, 06:00 Chicago) in its own
container, and writes the snapshot that ``currency`` reads. It is the only caller of
the Clerk API in the serving stack; the request path never makes a Clerk call.

- **ok:** the passed Municipal Code amendments after the vintage, classified (Title 17,
  other cited titles; the rest are counted, not stored), with ``checked_at``.
- **suspect:** the contract drifted: a final ``subStatus`` we have never seen, or a
  record the previous check listed for the same vintage has vanished (passed laws don't
  un-pass). ``currency`` treats it as unknown, so no count is shown.
- **failed:** the Clerk was unreachable. The previous rows and ``checked_at`` are kept
  (they are still true; ``currency`` ages them out), with ``last_error`` and a failure
  count. The process exits 1 and reports to Sentry.

The file is replaced atomically (temp file + rename), so the app never reads half of it.

    python -m backend.legislation.sync            # write the snapshot
    python -m backend.legislation.sync --print    # check and print, write nothing
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backend.legislation import currency
from backend.legislation.amendments import live_record
from backend.retrieval import clerk

log = logging.getLogger(__name__)

SCHEMA = 1


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


async def build_snapshot(previous: dict | None, *, now: datetime | None = None, client=None) -> dict:
    """The new snapshot. Raises ``clerk.ClerkUnavailable``/``ClerkQueryError`` when the
    Clerk can't be checked (the caller records the failure)."""
    now = now or datetime.now(timezone.utc)
    day = currency.vintage_day()
    if day is None:
        raise RuntimeError("backend/code_vintage.json is missing; nothing to compare against")

    final = await clerk.final_since(day, (clerk.CODE_AMENDMENTS,), client=client)
    problems = sorted({f"unknown final subStatus {m.sub_status!r} on {m.record_number}"
                       for m in final if m.sub_status not in clerk.KNOWN_FINAL_SUBSTATUSES})
    passed = [m for m in final if m.passed and m.passed_on and m.passed_on > day]
    rows = [live_record(m) for m in passed]
    kept = [r for r in rows if r["relevance"] != "other"]

    if previous and previous.get("vintage") == day.isoformat() and previous.get("status") == "ok":
        now_records = {r["record"] for r in rows}
        gone = [r["record"] for r in previous.get("code_amendments") or [] if r.get("record") not in now_records]
        problems += [f"{rec} was listed as passed on the last check and is gone now" for rec in gone]

    return {
        "schema": SCHEMA,
        "vintage": day.isoformat(),
        "checked_at": _iso(now),
        "last_attempt_at": _iso(now),
        "status": "suspect" if problems else "ok",
        "last_error": None,
        "consecutive_failures": 0,
        "contract_problems": problems,
        "counts": {
            "passed_code_amendments": len(rows),
            "title17": sum(1 for r in rows if r["relevance"] == "title17"),
            "cited_other": sum(1 for r in rows if r["relevance"] == "cited_other"),
        },
        "code_amendments": kept,
        "rezonings": [],  # WS1 M5
    }


def failed_snapshot(previous: dict | None, error: str, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    prev = dict(previous or {})
    return {
        **prev,
        "schema": SCHEMA,
        "last_attempt_at": _iso(now),
        "status": "failed",
        "last_error": error[:500],
        "consecutive_failures": int(prev.get("consecutive_failures") or 0) + 1,
        "code_amendments": prev.get("code_amendments") or [],
    }


async def run(path: Path | None = None, *, write: bool = True) -> tuple[int, dict]:
    path = path or currency.snapshot_path()
    previous = currency._read_json(path)
    previous = previous if isinstance(previous, dict) else None
    try:
        snap = await build_snapshot(previous)
        code = 0 if snap["status"] == "ok" else 2
        if snap["status"] == "suspect":
            log.error("Legislation snapshot is suspect: %s", "; ".join(snap["contract_problems"]))
    except (clerk.ClerkUnavailable, clerk.ClerkQueryError) as exc:
        log.error("Clerk check failed: %s", exc)
        snap, code = failed_snapshot(previous, f"{type(exc).__name__}: {exc}"), 1
        _report(exc)
    if write:
        write_atomic(path, snap)
    return code, snap


def _report(exc: BaseException) -> None:
    from backend.config import get_settings

    dsn = get_settings().sentry_dsn
    if not dsn:
        return
    import sentry_sdk

    sentry_sdk.init(dsn=dsn, send_default_pii=False)
    sentry_sdk.capture_exception(exc)
    sentry_sdk.flush(timeout=10)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daily City Clerk legislation sync")
    parser.add_argument("--print", action="store_true", help="check and print the snapshot; write nothing")
    parser.add_argument("--out", type=Path, help="write here instead of settings.legislation_snapshot_path")
    args = parser.parse_args(argv)
    code, snap = asyncio.run(run(args.out, write=not args.print))
    c = snap.get("counts") or {}
    print(f"status={snap.get('status')} vintage={snap.get('vintage')} checked_at={snap.get('checked_at')} "
          f"passed={c.get('passed_code_amendments')} title17={c.get('title17')} cited_other={c.get('cited_other')}")
    for p in snap.get("contract_problems") or []:
        print(f"  problem: {p}")
    if snap.get("last_error"):
        print(f"  error: {snap['last_error']}")
    if code == 2:
        _report(RuntimeError("legislation snapshot suspect: " + "; ".join(snap.get("contract_problems") or [])))
    return code


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.exit(main())
