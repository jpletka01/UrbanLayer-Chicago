"""Run the canned query test set against the router and (optionally) a live backend.

Modes:
  --router-only      Hit the LLM router with each query; check plan-level expectations
                     (sources, intent, location resolution, disclaimer). No backend
                     required. Useful as a fast regression check on prompt changes.

  --full <URL>       POST each query to a running /chat endpoint, stream the SSE
                     response, capture retrieval section IDs from the context event
                     and the phase latencies from t_ms. Checks retrieval + plan
                     expectations and records per-phase timings.

Outputs:
  - stdout: pass/fail counts, per-query result
  - --out PATH: markdown report with results table and timing percentiles
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUERIES_FILE = Path(__file__).resolve().parent / "queries.json"


@dataclass
class Result:
    id: str
    question: str
    category: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    plan: dict | None = None
    retrieved_sections: list[str] = field(default_factory=list)
    timings: dict[str, int] = field(default_factory=dict)
    answer_excerpt: str = ""


def _check_plan(plan: dict, expect: dict) -> list[str]:
    failures: list[str] = []

    sources = plan.get("sources") or []
    if "sources_include" in expect:
        for s in expect["sources_include"]:
            if s not in sources:
                failures.append(f"expected source {s!r} in plan, got {sources}")
    if "sources_any_of" in expect:
        if not any(s in sources for s in expect["sources_any_of"]):
            failures.append(f"expected at least one of {expect['sources_any_of']} in plan, got {sources}")

    intent = plan.get("intent")
    if "intent" in expect and intent != expect["intent"]:
        failures.append(f"expected intent={expect['intent']!r}, got {intent!r}")
    if "intent_one_of" in expect and intent not in expect["intent_one_of"]:
        failures.append(f"expected intent in {expect['intent_one_of']}, got {intent!r}")

    if "requires_disclaimer" in expect:
        actual = bool(plan.get("requires_disclaimer"))
        if actual != expect["requires_disclaimer"]:
            failures.append(f"requires_disclaimer expected {expect['requires_disclaimer']}, got {actual}")

    loc = plan.get("location") or {}
    if "location_resolved" in expect:
        resolved = loc.get("resolved_community_area") is not None
        if resolved != expect["location_resolved"]:
            failures.append(f"location_resolved expected {expect['location_resolved']}, got {resolved}")
    if "expected_community_area" in expect:
        ca = loc.get("resolved_community_area")
        if ca != expect["expected_community_area"]:
            failures.append(f"expected community area {expect['expected_community_area']}, got {ca}")
    if "location_type_one_of" in expect:
        if loc.get("type") not in expect["location_type_one_of"]:
            failures.append(f"location.type expected one of {expect['location_type_one_of']}, got {loc.get('type')!r}")

    if "time_range_days_at_most" in expect:
        days = plan.get("time_range_days") or 0
        if days > expect["time_range_days_at_most"]:
            failures.append(f"time_range_days={days} exceeds max {expect['time_range_days_at_most']}")

    if "clarification_present" in expect:
        present = bool(plan.get("clarification"))
        if present != expect["clarification_present"]:
            failures.append(f"clarification_present expected {expect['clarification_present']}, got {present}")

    return failures


def _check_retrieval(sections: list[str], expect: dict) -> list[str]:
    failures: list[str] = []
    if "retrieval_section_contains_any" in expect:
        wanted = expect["retrieval_section_contains_any"]
        hits = [w for w in wanted if any(w in s for s in sections)]
        if not hits:
            failures.append(
                f"none of {wanted} appeared in retrieved sections {sections[:5]}..."
            )
    return failures


async def _run_router_only(query: dict) -> Result:
    # Avoid importing backend.router at module level so --full can run without
    # an Anthropic key in the environment.
    from backend.router import route

    plan = await route(query["question"])
    plan_dict = plan.model_dump()
    failures = _check_plan(plan_dict, query["expect"])
    return Result(
        id=query["id"],
        question=query["question"],
        category=query["category"],
        passed=not failures,
        failures=failures,
        plan=plan_dict,
    )


async def _run_full(query: dict, base_url: str, http: httpx.AsyncClient) -> Result:
    started = time.monotonic()
    plan_dict: dict | None = None
    retrieved_sections: list[str] = []
    timings: dict[str, int] = {}
    answer_parts: list[str] = []

    async with http.stream(
        "POST",
        f"{base_url}/chat",
        json={"message": query["question"], "history": []},
        timeout=httpx.Timeout(60.0),
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
                plan_dict = evt.get("plan")
                if t is not None:
                    timings["router_ms"] = t
            elif evt["type"] == "context":
                ctx = evt.get("context") or {}
                for chunk in ctx.get("code_chunks") or []:
                    sec = chunk.get("section")
                    if sec:
                        retrieved_sections.append(sec)
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

    failures: list[str] = []
    if plan_dict is None:
        failures.append("no plan event received")
    else:
        failures.extend(_check_plan(plan_dict, query["expect"]))
        failures.extend(_check_retrieval(retrieved_sections, query["expect"]))

    return Result(
        id=query["id"],
        question=query["question"],
        category=query["category"],
        passed=not failures,
        failures=failures,
        plan=plan_dict,
        retrieved_sections=retrieved_sections,
        timings=timings,
        answer_excerpt="".join(answer_parts)[:400],
    )


def _print_summary(results: list[Result], mode: str) -> None:
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\n{passed}/{total} passed ({mode})")

    if mode == "full":
        for phase in ("router_ms", "retrieval_ms", "first_token_ms", "total_ms"):
            vals = [r.timings[phase] for r in results if phase in r.timings]
            if vals:
                p50 = statistics.median(vals)
                p95 = statistics.quantiles(vals, n=20)[18] if len(vals) >= 20 else max(vals)
                print(f"  {phase:>16}: p50={int(p50)}ms p95={int(p95)}ms  (n={len(vals)})")

    fails = [r for r in results if not r.passed]
    if fails:
        print("\nFailures:")
        for r in fails:
            print(f"  [{r.id}] {r.question}")
            for f in r.failures:
                print(f"      - {f}")


def _write_markdown(results: list[Result], path: Path, mode: str) -> None:
    passed = sum(1 for r in results if r.passed)
    lines = [
        f"# Eval report — {mode}",
        "",
        f"**{passed}/{len(results)} passed.**",
        "",
    ]

    if mode == "full":
        lines.append("## Latency (ms)")
        lines.append("")
        lines.append("| Phase | p50 | p95 | n |")
        lines.append("|---|---:|---:|---:|")
        for phase in ("router_ms", "retrieval_ms", "first_token_ms", "total_ms"):
            vals = [r.timings[phase] for r in results if phase in r.timings]
            if not vals:
                continue
            p50 = int(statistics.median(vals))
            p95 = int(statistics.quantiles(vals, n=20)[18]) if len(vals) >= 20 else max(vals)
            lines.append(f"| {phase} | {p50} | {p95} | {len(vals)} |")
        lines.append("")

    lines.append("## Results")
    lines.append("")
    lines.append("| ID | ✓ | Category | Question | Notes |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        flag = "✅" if r.passed else "❌"
        notes = ("; ".join(r.failures))[:120] if r.failures else ""
        # Escape pipes
        question = r.question.replace("|", "\\|")
        notes = notes.replace("|", "\\|")
        lines.append(f"| `{r.id}` | {flag} | {r.category} | {question} | {notes} |")

    path.write_text("\n".join(lines))
    print(f"\nMarkdown report → {path}")


async def main_async(args: argparse.Namespace) -> int:
    data = json.loads(QUERIES_FILE.read_text())
    queries: list[dict] = data["queries"]
    if args.filter:
        queries = [q for q in queries if args.filter in q["id"] or args.filter in q["category"]]
        if not queries:
            print(f"No queries match filter {args.filter!r}", file=sys.stderr)
            return 1

    results: list[Result] = []
    if args.full:
        async with httpx.AsyncClient() as http:
            for q in queries:
                print(f"… [{q['id']}] {q['question']}")
                try:
                    r = await _run_full(q, args.full, http)
                except Exception as exc:
                    r = Result(
                        id=q["id"],
                        question=q["question"],
                        category=q["category"],
                        passed=False,
                        failures=[f"request failed: {exc}"],
                    )
                results.append(r)
    else:
        for q in queries:
            print(f"… [{q['id']}] {q['question']}")
            try:
                r = await _run_router_only(q)
            except Exception as exc:
                r = Result(
                    id=q["id"],
                    question=q["question"],
                    category=q["category"],
                    passed=False,
                    failures=[f"router failed: {exc}"],
                )
            results.append(r)

    mode = "full" if args.full else "router_only"
    _print_summary(results, mode)
    if args.out:
        _write_markdown(results, args.out, mode)
    return 0 if all(r.passed for r in results) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--router-only", action="store_true", help="Default mode: hit the router only")
    group.add_argument("--full", metavar="URL", default=None, help="Hit a running backend at this base URL (e.g. http://localhost:8000)")
    parser.add_argument("--filter", help="Only run queries whose id or category contains this string")
    parser.add_argument("--out", type=Path, help="Write a markdown report to this path")
    args = parser.parse_args()

    code = asyncio.run(main_async(args))
    sys.exit(code)


if __name__ == "__main__":
    main()
