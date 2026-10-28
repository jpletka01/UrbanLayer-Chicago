"""How old are the committed data artifacts? (WS6 M5, plan §3.9)

CI runs ``python -m backend.data_health.artifacts --ci`` on every push and PR. It prints one
``::warning`` annotation per artifact that is past its tolerance, plus a table in the job summary.
**It never fails the build** (the step is ``continue-on-error``): a stale artifact must not block a
hotfix deploy. The real alarm is the daily checker on the server; this is the nudge a person sees
while they are already looking at a PR.

Checked here (all from files in the repo, no network):

- ``backend/code_vintage.json``: the code text's "current through" date (60 / 90 days);
- ``ingestion/data/zoning_cache.json``: its build date, and that the code vintage it records equals the
  code text's (``_meta.code_vintage``, written by ``zoning_cache_build``);
- ``ingestion/data/transit_stations.json``: build date from its ``.meta.json`` sidecar (180 / 365 days);
- ``ingestion/data/rent_by_area.json``: build date from its ``.meta.json`` sidecar (400 / 730 days);
- ``ingestion/data/assessor_model_by_area.json``: build date from its sidecar (1095 / 1460 days) and the Assessor's
  assessment year (a new city-wide reassessment is due three years on);
- ``eval/kit/parcels.json``: the answer key's version date (180 days: a person should re-review it);
- ``docs/benchmark/results.json``: the newest recorded run (45 days);
- ``zoning_definitions.VERIFIED_AGAINST``: the code text the hand table was last checked against.

A source the data-health registry has acked (the code text, until 2026-12-15) still annotates, but the
message says so, so a PR author is not left wondering whether it is news.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# (warn after, alarm after) in days.
CODE_VINTAGE_DAYS = (60, 90)
ZONING_CACHE_DAYS = (365, 730)
TRANSIT_DAYS = (180, 365)
RENT_DAYS = (400, 730)  # ACS 5-year releases arrive each December
ASSESSOR_MODEL_DAYS = (1095, 1460)  # the Assessor revalues the city every three years (2021, 2024, 2027)
ASSESSOR_CYCLE_YEARS = 3
KIT_KEY_DAYS = (180, 365)
BENCHMARK_DAYS = (45, 90)


@dataclass(frozen=True)
class Check:
    name: str
    path: str
    state: str           # "ok" | "warn" | "alarm" | "missing"
    message: str
    age_days: int | None = None

    @property
    def annotates(self) -> bool:
        return self.state != "ok"


def _age(d: date, today: date) -> int:
    return (today - d).days


def _grade(age: int, limits: tuple[int, int]) -> str:
    return "alarm" if age > limits[1] else "warn" if age > limits[0] else "ok"


def _iso(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _read(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _acked(source_id: str, today: date) -> str:
    """" (acked in the registry until D)" when the data-health registry has a live ack for it."""
    try:
        from backend.data_health.registry import BY_ID

        ack = BY_ID[source_id].ack
    except (ImportError, KeyError):
        return ""
    return f" (acked in the data-health registry until {ack.until}, so the daily checker is not alarming)" if ack and ack.until >= today else ""


def check_code_vintage(today: date, root: Path = REPO) -> Check:
    rec = _read(root / "backend/code_vintage.json")
    through = _iso(rec.get("current_through")) if rec else None
    if through is None:
        return Check("code text vintage", "backend/code_vintage.json", "alarm", "no current_through date")
    age = _age(through, today)
    state = _grade(age, CODE_VINTAGE_DAYS)
    msg = f"Municipal Code text is current through {through} ({age} days old; warn after {CODE_VINTAGE_DAYS[0]}, alarm after {CODE_VINTAGE_DAYS[1]})"
    return Check("code text vintage", "backend/code_vintage.json", state, msg + (_acked("code.municipal_text", today) if state != "ok" else ""), age)


def check_zoning_cache(today: date, root: Path = REPO) -> Check:
    path = "ingestion/data/zoning_cache.json"
    meta = ((_read(root / path) or {}).get("_meta")) or {}
    code = _read(root / "backend/code_vintage.json") or {}
    built = date.fromtimestamp(meta["built_at"]) if isinstance(meta.get("built_at"), (int, float)) else None
    if built is None:
        return Check("zoning cache", path, "alarm", "no built_at in _meta")
    age = _age(built, today)
    state = _grade(age, ZONING_CACHE_DAYS)
    problems = []
    recorded = meta.get("code_vintage")
    if not recorded:
        state = "warn" if state == "ok" else state
        problems.append("it records no code_vintage (a rebuild or a reviewed rebase writes one)")
    elif code.get("current_through") and recorded != code["current_through"]:
        state = "alarm"
        problems.append(f"it was checked against code text {recorded}, the code text is now {code['current_through']}")
    msg = f"zoning cache built {built} ({age} days old)" + ("; " + "; ".join(problems) if problems else "")
    return Check("zoning cache", path, state, msg, age)


def check_transit(today: date, root: Path = REPO) -> Check:
    path = "ingestion/data/transit_stations.json"
    side = _read(root / "ingestion/data/transit_stations.meta.json")
    built = _iso(side.get("built_at")) if side else None
    if built is None:
        return Check("transit stations", path, "warn", "no transit_stations.meta.json sidecar with a built_at date")
    age = _age(built, today)
    return Check("transit stations", path, _grade(age, TRANSIT_DAYS),
                 f"transit stations built {built} from the CTA and Metra feeds ({age} days old; warn after {TRANSIT_DAYS[0]})", age)


def check_rent(today: date, root: Path = REPO) -> Check:
    path = "ingestion/data/rent_by_area.json"
    side = _read(root / "ingestion/data/rent_by_area.meta.json")
    built = _iso(side.get("built_at")) if side else None
    if built is None:
        return Check("rent by community area", path, "warn", "no rent_by_area.meta.json sidecar with a built_at date")
    age = _age(built, today)
    return Check("rent by community area", path, _grade(age, RENT_DAYS),
                 f"rent by community area built {built} from ACS {side.get('acs_period', '?')} ({age} days old; warn after {RENT_DAYS[0]})", age)


def check_assessor_model(today: date, root: Path = REPO) -> Check:
    path = "ingestion/data/assessor_model_by_area.json"
    side = _read(root / "ingestion/data/assessor_model_by_area.meta.json")
    built = _iso(side.get("built_at")) if side else None
    if built is None:
        return Check("Assessor model by community area", path, "warn", "no assessor_model_by_area.meta.json sidecar with a built_at date")
    age = _age(built, today)
    state = _grade(age, ASSESSOR_MODEL_DAYS)
    year = str(side.get("assessor_year") or "")
    msg = f"Assessor model built {built} from the {year or '?'} city reassessment ({age} days old; warn after {ASSESSOR_MODEL_DAYS[0]})"
    if year.isdigit() and today.year >= int(year) + ASSESSOR_CYCLE_YEARS and state == "ok":
        state, msg = "warn", msg + f"; the Assessor revalues the city every {ASSESSOR_CYCLE_YEARS} years, so a {int(year) + ASSESSOR_CYCLE_YEARS} reassessment is due: check for it and rebuild"
    return Check("Assessor model by community area", path, state, msg, age)


def check_kit_key(today: date, root: Path = REPO) -> Check:
    path = "eval/kit/parcels.json"
    key = _read(root / path)
    version = str((key or {}).get("version", ""))
    day = _iso(version.split(".")[0])
    if day is None:
        return Check("answer key", path, "warn", f"key version {version!r} has no date")
    age = _age(day, today)
    return Check("answer key", path, _grade(age, KIT_KEY_DAYS),
                 f"the parcel kit's answer key is version {version} ({age} days old); a person should re-review it after {KIT_KEY_DAYS[0]}", age)


def check_benchmark(today: date, root: Path = REPO) -> Check:
    path = "docs/benchmark/results.json"
    data = _read(root / path)
    dates = [d for d in (_iso(v.get("date")) for v in ((data or {}).get("current") or {}).values() if isinstance(v, dict)) if d]
    if not dates:
        return Check("benchmark", path, "warn", "no dated run in results.json")
    newest = max(dates)
    age = _age(newest, today)
    return Check("benchmark", path, _grade(age, BENCHMARK_DAYS),
                 f"the newest recorded benchmark run is {newest} ({age} days old; warn after {BENCHMARK_DAYS[0]})", age)


def check_hand_table(today: date, root: Path = REPO) -> Check:
    from backend.retrieval import zoning_definitions

    verified = getattr(zoning_definitions, "VERIFIED_AGAINST", None)
    code = (_read(root / "backend/code_vintage.json") or {}).get("current_through")
    path = "backend/retrieval/zoning_definitions.py"
    if not verified:
        return Check("hand table", path, "alarm", "VERIFIED_AGAINST is not set")
    if code and verified != code:
        return Check("hand table", path, "alarm", f"the zoning table was verified against code text {verified}, the code text is now {code}: re-verify")
    return Check("hand table", path, "ok", f"the zoning table was verified against code text {verified}")


def run_checks(today: date | None = None, root: Path = REPO) -> list[Check]:
    today = today or date.today()
    return [f(today, root) for f in (check_code_vintage, check_zoning_cache, check_transit, check_rent, check_assessor_model, check_kit_key, check_benchmark, check_hand_table)]


def annotation(c: Check) -> str:
    level = "warning"  # never ``error``: this step must not turn a PR red
    return f"::{level} file={c.path},title=Stale artifact ({c.name})::{c.message}"


def summary_table(checks: list[Check]) -> str:
    rows = ["| Artifact | State | Detail |", "|---|---|---|"]
    rows += [f"| {c.name} | {c.state} | {c.message} |" for c in checks]
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Age of the committed data artifacts (warn-only).")
    ap.add_argument("--ci", action="store_true", help="print GitHub annotations and write the job summary; always exit 0")
    ap.add_argument("--today", type=date.fromisoformat)
    args = ap.parse_args(argv)
    checks = run_checks(args.today)
    for c in checks:
        print(f"{c.state:7} {c.name:18} {c.message}")
        if args.ci and c.annotates:
            print(annotation(c))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if args.ci and summary:
        with open(summary, "a") as f:
            f.write("### Committed artifact ages\n\n" + summary_table(checks) + "\n")
    return 0 if args.ci else (1 if any(c.state in ("alarm", "missing") for c in checks) else 0)


if __name__ == "__main__":
    sys.exit(main())
