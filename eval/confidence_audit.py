"""Confidence audit: does every figure the Property Profile shows carry a provenance entry?

Runs the fixed 100-address panel (``eval/lot_panel.json``, the same one ``eval.lot_coverage``
uses) through the real ``/api/scorecard`` endpoint and, per fact id, reports how many payloads
have a figure present (``backend.provenance_figures.expected_fact_ids``, written from the
payload's JSON shape) and how many of those carry an entry, how many are ``low`` or
``withheld``, the oldest as-of, and the tier mix. A figure with no entry is a defect.

No model calls: ``/api/scorecard`` reads public City, County and Census data only.

Usage:
  PYTHONPATH=. python -m eval.confidence_audit --full http://localhost:8001
  PYTHONPATH=. python -m eval.confidence_audit --full https://urbanlayerchicago.com --sample 25 --concurrency 1
  PYTHONPATH=. python -m eval.confidence_audit --from-dir eval/results/2026-10-21-m4/parcel_kit_raw   # recorded payloads
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from backend.provenance_figures import expected_fact_ids

PANEL_FILE = Path(__file__).parent / "lot_panel.json"
RESULTS = Path(__file__).parent / "results"


def audit(payloads: list[dict]) -> dict[str, Any]:
    """Aggregate over scorecard payloads (each with a ``provenance`` map)."""
    facts: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"expected": 0, "with_entry": 0, "low": 0, "withheld": 0, "oldest_as_of": None, "tiers": Counter(),
                 "missing_in": [], "unexpected": 0}
    )
    sizes = {"payload_bytes": [], "provenance_bytes": [], "entries": []}
    for pl in payloads:
        prov = pl.get("provenance") or {}
        want = expected_fact_ids(pl)
        sizes["payload_bytes"].append(len(json.dumps(pl)))
        sizes["provenance_bytes"].append(len(json.dumps(prov)))
        sizes["entries"].append(len(prov))
        for f in want:
            row = facts[f]
            row["expected"] += 1
            if f in prov:
                row["with_entry"] += 1
            else:
                row["missing_in"].append(pl.get("address"))
        for f, e in prov.items():
            row = facts[f]
            if f not in want:
                row["unexpected"] += 1
            row["tiers"][e.get("tier")] += 1
            if e.get("confidence") == "low":
                row["low"] += 1
            elif e.get("confidence") == "withheld":
                row["withheld"] += 1
            a = e.get("as_of")
            if a and (row["oldest_as_of"] is None or a < row["oldest_as_of"]):
                row["oldest_as_of"] = a
    expected = sum(r["expected"] for r in facts.values())
    covered = sum(r["with_entry"] for r in facts.values())
    n = len(payloads) or 1
    return {
        "payloads": len(payloads),
        "figures_expected": expected,
        "figures_with_entry": covered,
        "coverage": round(covered / expected, 4) if expected else None,
        "mean_entries": round(sum(sizes["entries"]) / n, 1),
        "mean_payload_kb": round(sum(sizes["payload_bytes"]) / n / 1024, 1),
        "mean_provenance_kb": round(sum(sizes["provenance_bytes"]) / n / 1024, 1),
        "facts": {k: {**v, "tiers": dict(v["tiers"])} for k, v in sorted(facts.items())},
    }


def markdown(report: dict[str, Any], source: str) -> str:
    lines = [
        "# Confidence audit",
        "",
        f"- Source: {source}",
        f"- Payloads: {report['payloads']}; figures expected {report['figures_expected']}, with an entry {report['figures_with_entry']}"
        f" (**{(report['coverage'] or 0) * 100:.1f}%**)",
        f"- Mean per Profile: {report['mean_entries']} entries; payload {report['mean_payload_kb']} KB, of which provenance {report['mean_provenance_kb']} KB",
        "",
        "| Fact | Present | With entry | Low | Withheld | Oldest as-of | Tiers |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for f, r in report["facts"].items():
        tiers = ", ".join(f"{k} {v}" for k, v in sorted(r["tiers"].items()))
        flag = "" if r["expected"] == r["with_entry"] else " ⚠"
        lines.append(f"| `{f}`{flag} | {r['expected']} | {r['with_entry']} | {r['low']} | {r['withheld']} | {r['oldest_as_of'] or ''} | {tiers} |")
    gaps = {f: r["missing_in"] for f, r in report["facts"].items() if r["missing_in"]}
    if gaps:
        lines += ["", "## Figures with no entry", ""]
        lines += [f"- `{f}`: {', '.join(map(str, v[:8]))}" for f, v in gaps.items()]
    return "\n".join(lines) + "\n"


def _sample(rows: list[dict], n: int | None) -> list[dict]:
    if not n or n >= len(rows):
        return rows
    step = len(rows) / n
    return [rows[int(i * step)] for i in range(n)]


async def _collect(base: str, rows: list[dict], concurrency: int) -> tuple[list[dict], list[str]]:
    from eval.lot_coverage import _fetch_scorecard

    sem = asyncio.Semaphore(concurrency)
    out: list[dict] = []
    errors: list[str] = []
    async with httpx.AsyncClient() as http:
        async def one(i: int, row: dict) -> None:
            async with sem:
                resp, ms, _status, err = await _fetch_scorecard(row, base, http)
            if resp is None:
                errors.append(f"{row['address']}: {err}")
            else:
                resp["address"] = resp.get("address") or row["address"]
                out.append(resp)
            print(f"  [{i + 1}/{len(rows)}] {row['address']:<36} {'ERR' if resp is None else f'{ms}ms'}", flush=True)

        await asyncio.gather(*(one(i, r) for i, r in enumerate(rows)))
    return out, errors


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", metavar="URL", help="base URL of a running backend")
    ap.add_argument("--from-dir", type=Path, help="audit recorded P*.profile.json payloads instead of calling an API")
    ap.add_argument("--limit", type=int, help="first N panel addresses")
    ap.add_argument("--sample", type=int, help="N evenly spaced panel addresses")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--out-dir", type=Path, help="where to write confidence_audit.{json,md}")
    args = ap.parse_args()

    errors: list[str] = []
    if args.from_dir:
        payloads = [json.loads(p.read_text()) for p in sorted(args.from_dir.glob("P*.profile.json"))]
        for p, pl in zip(sorted(args.from_dir.glob("P*.profile.json")), payloads):
            pl.setdefault("address", p.name.split(".")[0])
        source = f"recorded payloads in {args.from_dir}"
    elif args.full:
        rows = json.loads(PANEL_FILE.read_text())["addresses"]
        rows = _sample(rows[: args.limit] if args.limit else rows, args.sample)
        print(f"Auditing {len(rows)} addresses against {args.full} (concurrency={args.concurrency})...")
        payloads, errors = asyncio.run(_collect(args.full, rows, args.concurrency))
        source = f"{args.full}, {len(rows)} panel addresses"
    else:
        ap.error("either --full URL or --from-dir is required")
        return

    report = audit(payloads)
    report["fetch_errors"] = errors
    report["source"] = source
    report["run_at"] = datetime.now(timezone.utc).isoformat()
    out = args.out_dir or RESULTS / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out.mkdir(parents=True, exist_ok=True)
    (out / "confidence_audit.json").write_text(json.dumps(report, indent=2))
    (out / "confidence_audit.md").write_text(markdown(report, source))
    gaps = [f for f, r in report["facts"].items() if r["missing_in"]]
    print(f"coverage {(report['coverage'] or 0) * 100:.1f}% of {report['figures_expected']} figures; "
          f"{len(gaps)} facts with gaps; {len(errors)} fetch errors -> {out}")
    sys.exit(1 if gaps or errors else 0)


if __name__ == "__main__":
    main()
