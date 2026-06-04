"""Data source coverage benchmark.

Sends questions to a live /chat endpoint and checks whether each data
sub-source is (a) present in the retrieved ContextObject and (b) mentioned
in the synthesized response.  Produces a coverage matrix showing COVERED,
SYNTHESIS_GAP, RETRIEVAL_GAP, or HALLUCINATION per sub-source per query.

Usage:
  python -m eval.source_coverage --full http://localhost:8001
  python -m eval.source_coverage --full http://localhost:8001 --filter property
  python -m eval.source_coverage --full http://localhost:8001 --out eval/coverage_report.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

QUERIES_FILE = Path(__file__).resolve().parent / "coverage_queries.json"
DEFAULT_JSON_OUT = Path(__file__).resolve().parent / "coverage_results.json"

CAP_LIMITS = {
    "crime_api": ("crime_last_90d", 35),
    "311_api": ("open_311_requests", 50),
    "permits_api": ("permits", 500),
    "violations_api": ("violations", 200),
    "business_api": ("businesses", 500),
}


class CoverageStatus(str, Enum):
    COVERED = "COVERED"
    SYNTHESIS_GAP = "SYNTHESIS_GAP"
    RETRIEVAL_GAP = "RETRIEVAL_GAP"
    HALLUCINATION = "HALLUCINATION"
    NOT_TESTED = "NOT_TESTED"


@dataclass
class FieldCheck:
    field_path: str
    present: bool
    value_preview: str = ""


@dataclass
class SynthesisCheck:
    pattern: str
    matched: bool
    match_type: str = "required"


@dataclass
class CapInfo:
    source: str
    capped: bool
    limit: int
    at_least_used: bool


@dataclass
class SubSourceResult:
    sub_source: str
    status: CoverageStatus
    context_fields: list[FieldCheck] = field(default_factory=list)
    synthesis_matches: list[SynthesisCheck] = field(default_factory=list)


@dataclass
class QueryCoverageResult:
    id: str
    question: str
    category: str
    sub_sources: list[SubSourceResult] = field(default_factory=list)
    caps: list[CapInfo] = field(default_factory=list)
    timings: dict[str, int] = field(default_factory=dict)
    synthesis_text: str = ""


def _resolve_field(obj: Any, path: str) -> Any:
    """Traverse a nested dict by dot-separated path."""
    for key in path.split("."):
        if obj is None:
            return None
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            return None
    return obj


def _field_is_present(value: Any, *, allow_false: bool = False, allow_empty_list: bool = False) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, list) and len(value) == 0:
        return allow_empty_list
    if isinstance(value, bool):
        return value or allow_false
    return True


BOOLEAN_PRESENCE_FIELDS = {
    "incentives.in_tif_district",
    "incentives.in_opportunity_zone",
    "incentives.in_enterprise_zone",
    "regulatory.in_tod_area",
    "regulatory.in_historic_district",
    "regulatory.in_landmark_district",
    "regulatory.on_national_register",
}

ALLOW_EMPTY_LIST_FIELDS = {
    "regulatory.brownfield_sites",
}


def check_context_field(ctx: dict, field_path: str) -> FieldCheck:
    """Check a single field path (supports pipe-separated OR logic).

    Boolean incentive/regulatory fields count as present even when False
    (the source was queried and returned a definitive answer).
    Brownfield_sites counts as present even when empty (checked, none found).
    """
    if "|" in field_path:
        parts = field_path.split("|")
        for part in parts:
            part = part.strip()
            val = _resolve_field(ctx, part)
            allow_false = part in BOOLEAN_PRESENCE_FIELDS
            allow_empty = part in ALLOW_EMPTY_LIST_FIELDS
            if _field_is_present(val, allow_false=allow_false, allow_empty_list=allow_empty):
                preview = str(val)[:80] if val is not None else ""
                return FieldCheck(field_path=field_path, present=True, value_preview=preview)
        return FieldCheck(field_path=field_path, present=False, value_preview="")

    allow_false = field_path in BOOLEAN_PRESENCE_FIELDS
    allow_empty = field_path in ALLOW_EMPTY_LIST_FIELDS
    val = _resolve_field(ctx, field_path)
    present = _field_is_present(val, allow_false=allow_false, allow_empty_list=allow_empty)
    preview = str(val)[:80] if val is not None else ""
    return FieldCheck(field_path=field_path, present=present, value_preview=preview)


def check_synthesis_patterns(text: str, patterns_spec: dict) -> tuple[list[SynthesisCheck], bool]:
    """Check synthesis text against required patterns and any_of_groups.

    Returns (checks, all_passed).
    """
    checks: list[SynthesisCheck] = []
    all_ok = True

    for pat in patterns_spec.get("patterns", []):
        matched = bool(re.search(pat, text, re.IGNORECASE))
        checks.append(SynthesisCheck(pattern=pat, matched=matched, match_type="required"))
        if not matched:
            all_ok = False

    for group in patterns_spec.get("any_of_groups", []):
        group_matched = False
        for pat in group:
            if re.search(pat, text, re.IGNORECASE):
                group_matched = True
                break
        label = "|".join(group[:3])
        if len(group) > 3:
            label += f"|... (+{len(group) - 3})"
        checks.append(SynthesisCheck(pattern=f"any_of({label})", matched=group_matched, match_type="any_of"))
        if not group_matched:
            all_ok = False

    return checks, all_ok


def determine_status(context_ok: bool, synthesis_ok: bool, optional: bool = False) -> CoverageStatus:
    if context_ok and synthesis_ok:
        return CoverageStatus.COVERED
    if context_ok and not synthesis_ok:
        return CoverageStatus.SYNTHESIS_GAP
    if not context_ok and synthesis_ok:
        return CoverageStatus.HALLUCINATION
    if optional:
        return CoverageStatus.NOT_TESTED
    return CoverageStatus.RETRIEVAL_GAP


def _check_caps(ctx: dict, synthesis: str) -> list[CapInfo]:
    """Check which Socrata sources hit API caps and whether synthesis hedges."""
    caps: list[CapInfo] = []
    for source, (ctx_key, limit) in CAP_LIMITS.items():
        summary = ctx.get(ctx_key)
        if summary is None:
            continue
        capped = bool(summary.get("capped", False))
        at_least_used = bool(re.search(r"at least", synthesis, re.IGNORECASE)) if capped else False
        caps.append(CapInfo(source=source, capped=capped, limit=limit, at_least_used=at_least_used))
    return caps


async def _run_query(query: dict, base_url: str, http: httpx.AsyncClient) -> QueryCoverageResult:
    """Send query to /chat, parse SSE, evaluate coverage."""
    context_dict: dict = {}
    answer_parts: list[str] = []
    timings: dict[str, int] = {}

    async with http.stream(
        "POST",
        f"{base_url}/chat",
        json={"message": query["question"], "history": []},
        timeout=httpx.Timeout(90.0),
    ) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload:
                continue
            try:
                evt = json.loads(payload)
            except json.JSONDecodeError:
                continue
            t = evt.get("t_ms")
            if evt["type"] == "plan":
                if t is not None:
                    timings["router_ms"] = t
            elif evt["type"] == "context":
                context_dict = evt.get("context") or {}
                if t is not None:
                    timings["retrieval_ms"] = t
            elif evt["type"] == "token":
                if t is not None and "first_token_ms" not in timings:
                    timings["first_token_ms"] = t
                if evt.get("text"):
                    answer_parts.append(evt["text"])
            elif evt["type"] == "done":
                if t is not None:
                    timings["total_ms"] = t

    synthesis = "".join(answer_parts)

    sub_results: list[SubSourceResult] = []
    for check in query.get("checks", []):
        sub_source = check["sub_source"]
        is_optional = check.get("optional", False) or query.get("optional", False)

        field_checks: list[FieldCheck] = []
        context_ok = True
        for fp in check.get("context_fields", []):
            fc = check_context_field(context_dict, fp)
            field_checks.append(fc)
            if not fc.present:
                context_ok = False

        synth_spec = check.get("synthesis_patterns", {})
        synth_checks, synthesis_ok = check_synthesis_patterns(synthesis, synth_spec)

        status = determine_status(context_ok, synthesis_ok, optional=is_optional)
        sub_results.append(SubSourceResult(
            sub_source=sub_source,
            status=status,
            context_fields=field_checks,
            synthesis_matches=synth_checks,
        ))

    caps = _check_caps(context_dict, synthesis)

    return QueryCoverageResult(
        id=query["id"],
        question=query["question"],
        category=query["category"],
        sub_sources=sub_results,
        caps=caps,
        timings=timings,
        synthesis_text=synthesis[:500],
    )


def _print_coverage_matrix(results: list[QueryCoverageResult]) -> None:
    """Print a per-sub-source coverage summary table."""
    source_stats: dict[str, dict[str, int]] = {}
    for r in results:
        for ss in r.sub_sources:
            if ss.sub_source not in source_stats:
                source_stats[ss.sub_source] = {"tested": 0, "covered": 0, "synthesis_gap": 0, "retrieval_gap": 0, "hallucination": 0, "not_tested": 0}
            stats = source_stats[ss.sub_source]
            stats["tested"] += 1
            if ss.status == CoverageStatus.COVERED:
                stats["covered"] += 1
            elif ss.status == CoverageStatus.SYNTHESIS_GAP:
                stats["synthesis_gap"] += 1
            elif ss.status == CoverageStatus.RETRIEVAL_GAP:
                stats["retrieval_gap"] += 1
            elif ss.status == CoverageStatus.HALLUCINATION:
                stats["hallucination"] += 1
            elif ss.status == CoverageStatus.NOT_TESTED:
                stats["not_tested"] += 1

    print(f"\n{'='*78}")
    print("Source Coverage Matrix")
    print(f"{'='*78}")
    print(f"{'Sub-Source':<30} {'Tested':>6} {'Coverd':>6} {'SynGap':>6} {'RetGap':>6} {'Halluc':>6}")
    print("-" * 78)
    for source in sorted(source_stats.keys()):
        s = source_stats[source]
        effective = s["tested"] - s["not_tested"]
        if effective == 0:
            continue
        print(
            f"{source:<30} {effective:>6} {s['covered']:>6} "
            f"{s['synthesis_gap']:>6} {s['retrieval_gap']:>6} {s['hallucination']:>6}"
        )


def _print_cap_report(results: list[QueryCoverageResult]) -> None:
    """Print API cap hit summary."""
    cap_stats: dict[str, dict[str, int]] = {}
    for r in results:
        for cap in r.caps:
            if cap.source not in cap_stats:
                cap_stats[cap.source] = {"tested": 0, "capped": 0, "limit": cap.limit, "at_least": 0}
            stats = cap_stats[cap.source]
            stats["tested"] += 1
            if cap.capped:
                stats["capped"] += 1
                if cap.at_least_used:
                    stats["at_least"] += 1

    if not cap_stats:
        return

    print(f"\n{'='*78}")
    print("API Cap Report")
    print(f"{'='*78}")
    at_least_hdr = '"at least" Used'
    print(f"{'Source':<20} {'Capped In':>10} {'Limit':>8} {at_least_hdr:>18}")
    print("-" * 60)
    for source in sorted(cap_stats.keys()):
        s = cap_stats[source]
        capped_str = f"{s['capped']}/{s['tested']}"
        if s["capped"] > 0:
            at_least_str = f"{s['at_least']}/{s['capped']} ({round(100 * s['at_least'] / s['capped'])}%)"
        else:
            at_least_str = "n/a"
        print(f"{source:<20} {capped_str:>10} {s['limit']:>8} {at_least_str:>18}")


def _print_per_query(results: list[QueryCoverageResult]) -> None:
    """Print per-query results with failure details."""
    print(f"\n{'='*78}")
    print("Per-Query Results")
    print(f"{'='*78}")

    for r in results:
        statuses = [ss.status for ss in r.sub_sources if ss.status != CoverageStatus.NOT_TESTED]
        if all(s == CoverageStatus.COVERED for s in statuses):
            icon = "OK"
        elif any(s == CoverageStatus.HALLUCINATION for s in statuses):
            icon = "!!"
        elif any(s == CoverageStatus.RETRIEVAL_GAP for s in statuses):
            icon = "RG"
        elif any(s == CoverageStatus.SYNTHESIS_GAP for s in statuses):
            icon = "SG"
        else:
            icon = "??"

        total_ms = r.timings.get("total_ms", 0)
        print(f"\n  [{icon}] {r.id} ({total_ms}ms)")
        print(f"      Q: {r.question}")

        for ss in r.sub_sources:
            if ss.status == CoverageStatus.NOT_TESTED:
                print(f"      {ss.sub_source}: NOT_TESTED (optional, data unavailable)")
                continue
            status_label = ss.status.value
            print(f"      {ss.sub_source}: {status_label}")

            if ss.status != CoverageStatus.COVERED:
                for fc in ss.context_fields:
                    if not fc.present:
                        print(f"        ctx MISS: {fc.field_path}")
                    else:
                        print(f"        ctx  HIT: {fc.field_path} = {fc.value_preview}")
                for sc in ss.synthesis_matches:
                    if not sc.matched:
                        print(f"        syn MISS: {sc.pattern}")

        for cap in r.caps:
            if cap.capped:
                hedge = "with 'at least'" if cap.at_least_used else "WITHOUT 'at least'"
                print(f"      CAP HIT: {cap.source} hit limit={cap.limit}, {hedge}")


def _write_json(results: list[QueryCoverageResult], path: Path) -> None:
    """Write structured JSON results."""
    source_stats: dict[str, dict[str, int]] = {}
    cap_stats: dict[str, dict[str, Any]] = {}

    for r in results:
        for ss in r.sub_sources:
            if ss.sub_source not in source_stats:
                source_stats[ss.sub_source] = {"tested": 0, "covered": 0, "synthesis_gap": 0, "retrieval_gap": 0, "hallucination": 0, "not_tested": 0}
            stats = source_stats[ss.sub_source]
            effective_key = ss.status.value.lower()
            stats["tested"] += 1
            stats[effective_key] = stats.get(effective_key, 0) + 1

        for cap in r.caps:
            if cap.source not in cap_stats:
                cap_stats[cap.source] = {"times_tested": 0, "times_capped": 0, "limit": cap.limit, "at_least_used": 0}
            cs = cap_stats[cap.source]
            cs["times_tested"] += 1
            if cap.capped:
                cs["times_capped"] += 1
                if cap.at_least_used:
                    cs["at_least_used"] += 1

    total_checks = sum(1 for r in results for ss in r.sub_sources if ss.status != CoverageStatus.NOT_TESTED)
    covered = sum(1 for r in results for ss in r.sub_sources if ss.status == CoverageStatus.COVERED)
    synthesis_gap = sum(1 for r in results for ss in r.sub_sources if ss.status == CoverageStatus.SYNTHESIS_GAP)
    retrieval_gap = sum(1 for r in results for ss in r.sub_sources if ss.status == CoverageStatus.RETRIEVAL_GAP)
    hallucination = sum(1 for r in results for ss in r.sub_sources if ss.status == CoverageStatus.HALLUCINATION)

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_queries": len(results),
        "total_checks": total_checks,
        "summary": {
            "covered": covered,
            "synthesis_gap": synthesis_gap,
            "retrieval_gap": retrieval_gap,
            "hallucination": hallucination,
            "coverage_rate": round(covered / max(total_checks, 1), 4),
        },
        "per_source": source_stats,
        "caps": cap_stats,
        "per_query": [
            {
                "id": r.id,
                "question": r.question,
                "category": r.category,
                "timings": r.timings,
                "checks": [
                    {
                        "sub_source": ss.sub_source,
                        "status": ss.status.value,
                        "context_fields": [
                            {"path": fc.field_path, "present": fc.present, "preview": fc.value_preview}
                            for fc in ss.context_fields
                        ],
                        "synthesis_matches": [
                            {"pattern": sc.pattern, "matched": sc.matched, "type": sc.match_type}
                            for sc in ss.synthesis_matches
                        ],
                    }
                    for ss in r.sub_sources
                ],
                "synthesis_excerpt": r.synthesis_text,
                "caps": [
                    {"source": c.source, "capped": c.capped, "limit": c.limit, "at_least_used": c.at_least_used}
                    for c in r.caps
                ],
            }
            for r in results
        ],
    }

    path.write_text(json.dumps(output, indent=2))
    print(f"\nJSON results -> {path}")


def _write_markdown(results: list[QueryCoverageResult], path: Path) -> None:
    """Write a markdown coverage report."""
    total_checks = sum(1 for r in results for ss in r.sub_sources if ss.status != CoverageStatus.NOT_TESTED)
    covered = sum(1 for r in results for ss in r.sub_sources if ss.status == CoverageStatus.COVERED)

    lines = [
        "# Data Source Coverage Report",
        "",
        f"**{covered}/{total_checks} sub-source checks covered** across {len(results)} queries.",
        "",
        "## Coverage Matrix",
        "",
        "| Sub-Source | Tested | Covered | Synthesis Gap | Retrieval Gap | Hallucination |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    source_stats: dict[str, dict[str, int]] = {}
    for r in results:
        for ss in r.sub_sources:
            if ss.status == CoverageStatus.NOT_TESTED:
                continue
            if ss.sub_source not in source_stats:
                source_stats[ss.sub_source] = {"tested": 0, "covered": 0, "synthesis_gap": 0, "retrieval_gap": 0, "hallucination": 0}
            stats = source_stats[ss.sub_source]
            stats["tested"] += 1
            stats[ss.status.value.lower()] = stats.get(ss.status.value.lower(), 0) + 1

    for source in sorted(source_stats.keys()):
        s = source_stats[source]
        lines.append(
            f"| `{source}` | {s['tested']} | {s['covered']} | "
            f"{s['synthesis_gap']} | {s['retrieval_gap']} | {s['hallucination']} |"
        )

    lines.extend(["", "## API Cap Report", ""])
    cap_stats: dict[str, dict[str, Any]] = {}
    for r in results:
        for cap in r.caps:
            if cap.source not in cap_stats:
                cap_stats[cap.source] = {"tested": 0, "capped": 0, "limit": cap.limit, "at_least": 0}
            cs = cap_stats[cap.source]
            cs["tested"] += 1
            if cap.capped:
                cs["capped"] += 1
                if cap.at_least_used:
                    cs["at_least"] += 1

    if cap_stats:
        lines.append("| Source | Capped In | Limit | \"at least\" Used |")
        lines.append("|---|---:|---:|---|")
        for source in sorted(cap_stats.keys()):
            cs = cap_stats[source]
            capped_str = f"{cs['capped']}/{cs['tested']}"
            if cs["capped"] > 0:
                at_least_str = f"{cs['at_least']}/{cs['capped']} ({round(100 * cs['at_least'] / cs['capped'])}%)"
            else:
                at_least_str = "n/a"
            lines.append(f"| `{source}` | {capped_str} | {cs['limit']} | {at_least_str} |")
    else:
        lines.append("No capped sources detected.")

    lines.extend(["", "## Per-Query Detail", ""])
    lines.append("| Query | Sub-Source | Status | Context | Synthesis |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        for ss in r.sub_sources:
            if ss.status == CoverageStatus.NOT_TESTED:
                continue
            ctx_hits = sum(1 for fc in ss.context_fields if fc.present)
            ctx_total = len(ss.context_fields)
            syn_hits = sum(1 for sc in ss.synthesis_matches if sc.matched)
            syn_total = len(ss.synthesis_matches)
            lines.append(
                f"| `{r.id}` | `{ss.sub_source}` | {ss.status.value} | "
                f"{ctx_hits}/{ctx_total} | {syn_hits}/{syn_total} |"
            )

    path.write_text("\n".join(lines))
    print(f"\nMarkdown report -> {path}")


async def main_async(args: argparse.Namespace) -> int:
    data = json.loads(QUERIES_FILE.read_text())
    queries: list[dict] = data["queries"]

    if args.filter:
        queries = [q for q in queries if args.filter in q["id"] or args.filter in q["category"]]
        if not queries:
            print(f"No queries match filter {args.filter!r}", file=sys.stderr)
            return 1

    print(f"Running {len(queries)} coverage queries against {args.full}...")

    results: list[QueryCoverageResult] = []
    async with httpx.AsyncClient() as http:
        for i, q in enumerate(queries, 1):
            print(f"  [{i}/{len(queries)}] {q['id']}: {q['question'][:60]}...", flush=True)
            try:
                r = await _run_query(q, args.full, http)
            except Exception as exc:
                print(f"    ERROR: {exc}")
                r = QueryCoverageResult(
                    id=q["id"],
                    question=q["question"],
                    category=q["category"],
                    sub_sources=[
                        SubSourceResult(
                            sub_source=check["sub_source"],
                            status=CoverageStatus.RETRIEVAL_GAP,
                        )
                        for check in q.get("checks", [])
                    ],
                )
            results.append(r)

    _print_coverage_matrix(results)
    _print_cap_report(results)
    _print_per_query(results)

    json_out = args.json_out or DEFAULT_JSON_OUT
    _write_json(results, json_out)

    if args.out:
        _write_markdown(results, args.out)

    total_checks = sum(1 for r in results for ss in r.sub_sources if ss.status != CoverageStatus.NOT_TESTED)
    covered = sum(1 for r in results for ss in r.sub_sources if ss.status == CoverageStatus.COVERED)
    gaps = sum(1 for r in results for ss in r.sub_sources if ss.status in (CoverageStatus.SYNTHESIS_GAP, CoverageStatus.RETRIEVAL_GAP))
    print(f"\n{'='*78}")
    print(f"TOTAL: {covered}/{total_checks} covered, {gaps} gaps found")
    print(f"{'='*78}")

    return 0 if gaps == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--full", required=True, metavar="URL", help="Base URL of running backend (e.g. http://localhost:8001)")
    parser.add_argument("--filter", help="Only run queries whose id or category contains this string")
    parser.add_argument("--out", type=Path, help="Write a markdown report to this path")
    parser.add_argument("--json-out", type=Path, default=None, help="Path for JSON output (default: eval/coverage_results.json)")
    args = parser.parse_args()

    code = asyncio.run(main_async(args))
    sys.exit(code)


if __name__ == "__main__":
    main()
