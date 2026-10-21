"""Offline staleness warnings from the committed files only (plan §7.4).

Warns when the code text is more than 90 days old, or when a review entry has been
``pending`` for more than 30 days after its passage. Never fails: with ``--ci`` it
prints GitHub ``::warning::`` lines and exits 0. WS6's registry absorbs it (WS6 M5).

    python -m backend.legislation.currency_check [--ci]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from backend.legislation import currency

VINTAGE_WARN_DAYS = 90
PENDING_WARN_DAYS = 30


def warnings(today: date | None = None) -> list[str]:
    today = today or date.today()
    out: list[str] = []
    day = currency.vintage_day()
    if day is None:
        return ["backend/code_vintage.json is missing or unreadable"]
    age = (today - day).days
    if age > VINTAGE_WARN_DAYS:
        out.append(f"Municipal Code text current through {day.isoformat()} ({age} days, > {VINTAGE_WARN_DAYS})")
    for rec, a in sorted(currency.load_reviews().items()):
        if a.get("product_effect") != "pending" or not a.get("passed_on"):
            continue
        waited = (today - date.fromisoformat(a["passed_on"])).days
        if waited > PENDING_WARN_DAYS:
            out.append(f"{rec} (passed {a['passed_on']}) has been pending review for {waited} days")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Code currency warnings (offline)")
    parser.add_argument("--ci", action="store_true", help="GitHub Actions ::warning:: annotations")
    args = parser.parse_args(argv)
    for w in warnings():
        print(f"::warning::{w}" if args.ci else f"warning: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
