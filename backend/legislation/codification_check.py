"""After a code refresh: which passed amendments made it into the new export (plan §3.4).

For each amendment passed after the old vintage and on or before the new one, it looks
for an added or modified section whose legislative history cites the amendment's
Council Journal date and overlaps the amendment's sections (when they are known; an
omnibus with no section list matches on the date within its titles).

- **matched:** codified. ``--write`` sets ``codified: true`` in the review file.
- **missing:** American Legal skipped or delayed it. ``--write`` keeps ``codified:
  false``, so it stays in the "since" list although its date is before the vintage.
- **unexplained:** the reverse check, a modified section citing a Journal date that is
  no known passed amendment's (e.g. one the title classifier missed). Review by hand.

Offline: the diff from ``ingestion.update --dry-run``, the parsed sections, the review
file and the snapshot.

    python -m backend.legislation.codification_check --diff ingestion/data/diff/<vintage>/diff.json \\
        [--sections ingestion/data/sections.new] [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from backend.legislation import currency
from backend.legislation.amendments import sections_overlap


def coun_j(d: date) -> str:
    """The legislative-history spelling of a Journal date: 2026-05-20 -> 5-20-26."""
    return f"{d.month}-{d.day}-{d.year % 100:02d}"


def _title_of(section: str) -> str:
    return section.split("-", 1)[0]


def changed_sections(diff: dict, sections_dir: Path | None) -> dict[str, list[str]]:
    """{section id: Coun. J. dates} for every added or modified section."""
    out = {m["section"]: list(m.get("coun_j_dates") or []) for m in diff.get("modified_detail") or []}
    for sid in diff.get("added") or []:
        dates: list[str] = []
        path = sections_dir / f"{sid}.json" if sections_dir else None
        if path and path.exists():
            dates = list(json.loads(path.read_text()).get("effective_dates") or [])
        out[sid] = dates
    return out


def check(diff: dict, amendments: list[dict], sections_dir: Path | None = None) -> dict:
    old_v, new_v = diff.get("old_vintage"), diff["new_vintage"]
    changed = changed_sections(diff, sections_dir)
    in_window = [a for a in amendments if (old_v is None or a["passed_on"] > old_v) and a["passed_on"] <= new_v]

    matched, missing = [], []
    for a in in_window:
        stamp = coun_j(date.fromisoformat(a["passed_on"]))
        secs = a.get("sections") or []
        hits = [
            sid for sid, dates in changed.items() if stamp in dates and (
                any(sections_overlap(sid, s) for s in secs) if secs else _title_of(sid) == "17"
            )
        ]
        (matched if hits else missing).append({"record": a["record"], "passed_on": a["passed_on"], "sections": hits or secs})

    known = {coun_j(date.fromisoformat(a["passed_on"])) for a in amendments}
    new_dates = {m["section"]: m.get("new_coun_j_dates") or [] for m in diff.get("modified_detail") or []}
    unexplained = sorted(
        {(sid, d) for sid, dates in new_dates.items() for d in dates if d not in known and sid.startswith(("17-", "14", "2-44-", "2-120-"))}
    )
    return {
        "old_vintage": old_v, "new_vintage": new_v,
        "matched": matched, "missing": missing,
        "unexplained": [{"section": s, "coun_j": d} for s, d in unexplained],
    }


def write_codified(result: dict, review_file: Path = currency.REVIEW_FILE) -> list[str]:
    """Set ``codified`` on the review entries the check decided; returns records it
    couldn't set (not in the review file yet: add a review entry first)."""
    doc = json.loads(review_file.read_text())
    entries = doc["amendments"]
    absent = []
    for flag, rows in ((True, result["matched"]), (False, result["missing"])):
        for r in rows:
            if r["record"] in entries:
                entries[r["record"]]["codified"] = flag
            else:
                absent.append(r["record"])
    review_file.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return absent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--diff", type=Path, required=True)
    parser.add_argument("--sections", type=Path, help="parsed sections of the NEW export (for added sections' dates)")
    parser.add_argument("--write", action="store_true", help="record codified true/false in backend/code_amendments.json")
    args = parser.parse_args(argv)

    diff = json.loads(args.diff.read_text())
    since = date.fromisoformat(diff["old_vintage"]) if diff.get("old_vintage") else date(1900, 1, 1)
    result = check(diff, currency.amendments_since(since, currency.ALL_SCOPES), args.sections)
    print(f"{result['old_vintage']} -> {result['new_vintage']}")
    for r in result["matched"]:
        print(f"  codified  {r['passed_on']}  {r['record']:<16} {', '.join(r['sections'])}")
    for r in result["missing"]:
        print(f"  MISSING   {r['passed_on']}  {r['record']:<16} {', '.join(r['sections']) or '-'}")
    for u in result["unexplained"]:
        print(f"  unexplained Coun. J. {u['coun_j']} in {u['section']}")
    if args.write:
        absent = write_codified(result)
        for rec in absent:
            print(f"  not in the review file, add an entry: {rec}")
    return 1 if result["missing"] or result["unexplained"] else 0


if __name__ == "__main__":
    sys.exit(main())
