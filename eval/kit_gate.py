"""Pass/fail gate for the weekly Profile kit run against production (WS6 M5, plan §3.7).

``eval.parcel_kit`` scores a run and prints a report. This turns the report into a verdict a scheduled
workflow can act on, against the last *accepted* run committed in ``eval/kit/accepted_profile.json``:

- **A (the district) must be 2 for every parcel**: a wrong or missing district is the product's worst failure;
- **no confident-wrong (CW) claim anywhere**;
- **no cell scores below the accepted run** (a claim that was right and now isn't, or a number that stopped
  being stated). A cell that improves is fine and is reported, so the accepted file can be refreshed on purpose.

Profile only: the run calls ``/api/scorecard``, which is free and anonymous, so this uses no model and no secret.

    PYTHONPATH=. python -m eval.kit_gate eval/results/weekly/parcel_kit.json
    PYTHONPATH=. python -m eval.kit_gate <parcel_kit.json> --inject-mismatch      # the drill: must exit 1
    PYTHONPATH=. python -m eval.kit_gate <parcel_kit.json> --update-accepted      # after a person reviews an improvement

``--sentry`` sends one Sentry event on failure when ``SENTRY_DSN`` is set (a GitHub secret); without the
secret the failed workflow run, and GitHub's email about it, is the alarm.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

ACCEPTED_PATH = Path(__file__).resolve().parent / "kit" / "accepted_profile.json"
SURFACE = "profile"
# An unanswered cell (the kit's "NP") ranks between a wrong answer and a half-right one: dropping from a
# claim to silence is a regression, and going from silence to a wrong claim is too.
_NP = 0.5


def cells(report: dict) -> dict[str, dict[str, dict]]:
    """``{parcel: {field: {"score": 0|1|2|None, "cw": bool}}}`` for the Profile surface."""
    fields = ((report.get("surfaces") or {}).get(SURFACE) or {}).get("fields")
    if not fields:
        raise SystemExit(f"the report has no {SURFACE!r} surface: was the kit run with --surfaces profile?")
    return {p: {f: {"score": c.get("score"), "cw": bool(c.get("cw"))} for f, c in fs.items()} for p, fs in fields.items()}


def _rank(score: int | None) -> float:
    return _NP if score is None else float(score)


def judge(current: dict, accepted: dict | None) -> tuple[list[str], list[str]]:
    """``(failures, improvements)`` as sentences. ``accepted`` maps parcel -> field -> score (or None)."""
    failures: list[str] = []
    improvements: list[str] = []
    for parcel, fs in sorted(current.items()):
        a = fs.get("A", {})
        if a.get("score") != 2:
            failures.append(f"{parcel} field A (the district) scored {a.get('score')!r}, must be 2")
        for field, c in sorted(fs.items()):
            if c["cw"]:
                failures.append(f"{parcel} field {field} is a confident-wrong claim")
            if accepted is None:
                continue
            was = (accepted.get(parcel) or {}).get(field, "absent")
            if was == "absent":
                continue
            if _rank(c["score"]) < _rank(was):
                failures.append(f"{parcel} field {field} fell from {was!r} to {c['score']!r}")
            elif _rank(c["score"]) > _rank(was):
                improvements.append(f"{parcel} field {field} rose from {was!r} to {c['score']!r}")
    return failures, improvements


def inject_mismatch(current: dict) -> dict:
    """The drill: break P1's district in a copy so the gate must fail (never writes anything)."""
    out = deepcopy(current)
    first = sorted(out)[0]
    out[first]["A"] = {"score": 0, "cw": True}
    return out


def load_accepted(path: Path = ACCEPTED_PATH) -> dict | None:
    try:
        return json.loads(path.read_text())["scores"]
    except (OSError, ValueError, KeyError):
        return None


def write_accepted(current: dict, report: dict, path: Path = ACCEPTED_PATH) -> None:
    meta = report.get("meta") or {}
    scores = {p: {f: c["score"] for f, c in fs.items()} for p, fs in sorted(current.items())}
    path.write_text(json.dumps({
        "note": "The last accepted Profile kit scores (WS6 M5). The weekly run fails if any cell falls below these, "
                "if field A is not 2, or on any confident-wrong claim. Refresh only after a person reviews the run: "
                "python -m eval.kit_gate <parcel_kit.json> --update-accepted",
        "key_version": meta.get("key_version"), "accepted_on": meta.get("date"), "scores": scores,
    }, indent=1) + "\n")


def summary_markdown(failures: list[str], improvements: list[str], report: dict, injected: bool) -> str:
    agg = ((report.get("surfaces") or {}).get(SURFACE) or {}).get("aggregate") or {}
    lines = ["### Weekly parcel kit (Profile, production)", ""]
    if injected:
        lines += ["**Drill: a mismatch was injected into P1's district; this run is meant to fail.**", ""]
    lines += [f"Accuracy {agg.get('points')}/{agg.get('possible')}, coverage {agg.get('answered')}/{agg.get('scored_fields')}, "
              f"confident-wrong {agg.get('cw')}, district correct {agg.get('a_correct')}/{agg.get('parcels')}.", ""]
    lines += [f"**FAILED: {len(failures)} problem(s)**", ""] + [f"- {f}" for f in failures] if failures else ["**Passed.**"]
    if improvements:
        lines += ["", "Improved since the accepted run (refresh `eval/kit/accepted_profile.json` after review):"] + [f"- {i}" for i in improvements]
    return "\n".join(lines) + "\n"


def _sentry(failures: list[str]) -> None:
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        print("no SENTRY_DSN: the failed run itself is the alarm")
        return
    import sentry_sdk

    sentry_sdk.init(dsn=dsn, send_default_pii=False)
    with sentry_sdk.new_scope() as scope:
        scope.fingerprint = ["kit-weekly", "failed"]
        sentry_sdk.capture_message("Weekly parcel kit failed: " + "; ".join(failures[:5]), level="error")
    sentry_sdk.flush(timeout=10)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("report", type=Path, help="parcel_kit.json from `eval.parcel_kit --surfaces profile`")
    ap.add_argument("--accepted", type=Path, default=ACCEPTED_PATH)
    ap.add_argument("--inject-mismatch", action="store_true", help="the drill: corrupt P1's district; must exit 1")
    ap.add_argument("--update-accepted", action="store_true", help="write this run as the accepted baseline (after review)")
    ap.add_argument("--sentry", action="store_true", help="send a Sentry event on failure when SENTRY_DSN is set")
    args = ap.parse_args(argv)

    report = json.loads(args.report.read_text())
    current = cells(report)
    if args.update_accepted:
        write_accepted(current, report, args.accepted)
        print(f"wrote {args.accepted}")
        return 0
    if args.inject_mismatch:
        current = inject_mismatch(current)
    failures, improvements = judge(current, load_accepted(args.accepted))
    md = summary_markdown(failures, improvements, report, args.inject_mismatch)
    print(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(md)
    for f in failures:
        print(f"::error title=Weekly parcel kit::{f}")
    if failures and args.sentry:
        _sentry(failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
