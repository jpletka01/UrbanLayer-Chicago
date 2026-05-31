"""Run the canned query test set against the router and (optionally) a live backend.

Modes:
  --router-only      Hit the LLM router with each query; check plan-level expectations
                     (sources, intent, location resolution, disclaimer). No backend
                     required. Useful as a fast regression check on prompt changes.

  --full <URL>       POST each query to a running /chat endpoint, stream the SSE
                     response, capture retrieval section IDs from the context event
                     and the phase latencies from t_ms. Checks retrieval + plan
                     expectations and records per-phase timings.

  --judge            (requires --full) After the normal eval, use Claude as a judge
                     to grade synthesis quality on 4 dimensions: citation accuracy,
                     factuality, completeness, and rule compliance. Writes results
                     to eval/judge_results.json for the admin dashboard.

Outputs:
  - stdout: pass/fail counts, per-query result
  - --out PATH: markdown report with results table and timing percentiles
  - --judge-out PATH: JSON judge results (default: eval/judge_results.json)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUERIES_FILE = Path(__file__).resolve().parent / "queries.json"

GRADE_TO_NUM = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
NUM_TO_GRADE = {v: k for k, v in GRADE_TO_NUM.items()}
GRADE_TO_SCORE = {"A": 1.0, "B": 0.75, "C": 0.5, "D": 0.25, "F": 0.0}
DIMENSION_WEIGHTS = {
    "citation_accuracy": 0.30,
    "factuality": 0.30,
    "completeness": 0.20,
    "rule_compliance": 0.20,
}
DIMENSIONS = list(DIMENSION_WEIGHTS.keys())


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
    full_answer: str = ""
    context_dict: dict | None = None


@dataclass
class DimensionScore:
    dimension: str
    grade: str
    reasoning: str


@dataclass
class JudgeResult:
    query_id: str
    question: str
    dimensions: list[DimensionScore]
    overall_grade: str
    overall_reasoning: str


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
    context_dict: dict | None = None
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
                context_dict = ctx
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

    full_answer = "".join(answer_parts)
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
        answer_excerpt=full_answer[:400],
        full_answer=full_answer,
        context_dict=context_dict,
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


JUDGE_SYSTEM = """You are an expert evaluator of RAG system answers about Chicago city data and municipal code.

You will be given:
1. The user's question
2. The context data that was retrieved (code chunks, API data summaries, zoning info, analytics)
3. The synthesized answer that the system produced
4. Metadata flags indicating which synthesis rules apply to this query

Your job is to grade the answer on 4 dimensions. For each dimension, assign a letter grade (A, B, C, D, or F) and provide a 1-2 sentence justification.

## Grading Dimensions

### Citation Accuracy (weight 30%)
- [N] markers must reference valid 1-indexed positions in code_chunks (if code_chunks has 3 items, only [1], [2], [3] are valid)
- [data:X] markers must reference data sources actually present in the context (e.g., [data:crime] only valid if crime_last_90d is present)
- Citations must appear immediately after the relevant statement, not clustered at the end of a paragraph
- If no code_chunks or data sources exist in the context, and the answer has no citations, grade A (citations not applicable)
- Grade A if all citations valid and well-placed; F if fabricated indices or no citations when context demands them

### Factuality (weight 30%)
- All numbers and statistics stated in the answer must be traceable to the context data
- When a summary has "capped": true, the answer must say "at least N" not state N as an exact count
- No raw JSON should appear in the answer — data must be rendered as readable prose
- Grade A if all facts match context with no hallucination; F if the answer invents statistics not in context

### Completeness (weight 20%)
- The answer must address the user's question directly, leading with a direct answer in 1-3 sentences
- If crime data is present in the context, the answer should mention the ~7-day data lag
- If analytics/trends are present in the context, the answer should weave 2-4 notable month-over-month changes naturally
- Grade A if fully addressed with all applicable subsidiary notes; F if the question is not answered

### Rule Compliance (weight 20%)
- If requires_disclaimer is true: the answer must end with a legal disclaimer about not constituting legal advice
- If parcel_zoning is present: the answer must state the zoning classification as a definitive fact
- If neither rule applies to this query, grade A (no rules to comply with)
- Grade A if all applicable rules followed; F if required rules are systematically ignored

## Output Format

Respond with ONLY a JSON object (no markdown fences, no commentary):
{"dimensions": [{"dimension": "citation_accuracy", "grade": "A", "reasoning": "..."}, {"dimension": "factuality", "grade": "A", "reasoning": "..."}, {"dimension": "completeness", "grade": "B", "reasoning": "..."}, {"dimension": "rule_compliance", "grade": "A", "reasoning": "..."}], "overall_grade": "A", "overall_reasoning": "..."}
"""


def _extract_metadata_flags(ctx: dict) -> dict[str, Any]:
    code_chunks = ctx.get("code_chunks") or []
    data_sources = []
    capped_sources: dict[str, bool] = {}
    for key, label in [
        ("crime_last_90d", "crime"),
        ("open_311_requests", "311"),
        ("permits", "permits"),
        ("violations", "violations"),
        ("businesses", "business"),
    ]:
        summary = ctx.get(key)
        if summary:
            data_sources.append(label)
            capped_sources[label] = bool(summary.get("capped", False))

    return {
        "has_code_chunks": len(code_chunks) > 0,
        "num_code_chunks": len(code_chunks),
        "data_sources_present": data_sources,
        "capped_sources": {k: v for k, v in capped_sources.items() if v},
        "requires_disclaimer": bool(ctx.get("requires_disclaimer", False)),
        "has_parcel_zoning": ctx.get("parcel_zoning") is not None,
        "has_analytics": ctx.get("analytics") is not None,
        "has_crime_data": ctx.get("crime_last_90d") is not None,
    }


def _extract_citations(answer: str) -> dict[str, list[str]]:
    code_refs = re.findall(r"\[(\d+)\]", answer)
    data_refs = re.findall(r"\[data:(\w+)\]", answer)
    return {
        "code_citations": sorted(set(code_refs)),
        "data_citations": sorted(set(data_refs)),
    }


def _compute_overall_grade(dimensions: list[DimensionScore]) -> str:
    weighted = 0.0
    for d in dimensions:
        w = DIMENSION_WEIGHTS.get(d.dimension, 0.25)
        weighted += GRADE_TO_NUM.get(d.grade, 0) * w
    rounded = round(weighted)
    return NUM_TO_GRADE.get(min(4, max(0, rounded)), "C")


async def _run_judge(result: Result, model: str) -> JudgeResult:
    from anthropic import AsyncAnthropic

    ctx = result.context_dict or {}
    flags = _extract_metadata_flags(ctx)
    citations = _extract_citations(result.full_answer)

    # Build a trimmed context for the judge (truncate long chunk text to save tokens)
    judge_ctx = dict(ctx)
    if judge_ctx.get("code_chunks"):
        trimmed = []
        for chunk in judge_ctx["code_chunks"]:
            c = dict(chunk)
            if isinstance(c.get("text"), str) and len(c["text"]) > 600:
                c["text"] = c["text"][:600] + "... [truncated]"
            trimmed.append(c)
        judge_ctx["code_chunks"] = trimmed

    user_prompt = f"""## Question
{result.question}

## Metadata Flags
- code_chunks present: {flags['has_code_chunks']} ({flags['num_code_chunks']} chunks)
- Data sources present: {', '.join(flags['data_sources_present']) or 'none'}
- Capped sources: {flags['capped_sources'] or 'none'}
- requires_disclaimer: {flags['requires_disclaimer']}
- parcel_zoning present: {flags['has_parcel_zoning']}
- analytics/trends present: {flags['has_analytics']}
- crime data present: {flags['has_crime_data']}

## Citation Markers Found in Answer
- Code citations: {citations['code_citations'] or 'none'}
- Data citations: {citations['data_citations'] or 'none'}

## Context Data
{json.dumps(judge_ctx, indent=2, default=str)[:15000]}

## Synthesized Answer
{result.full_answer}"""

    client = AsyncAnthropic()
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=800,
            temperature=0,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:
        return JudgeResult(
            query_id=result.id,
            question=result.question,
            dimensions=[DimensionScore(d, "F", f"Judge call failed: {exc}") for d in DIMENSIONS],
            overall_grade="F",
            overall_reasoning=f"Judge call failed: {exc}",
        )

    text = "".join(
        block.text for block in response.content
        if getattr(block, "type", "") == "text"
    )

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return JudgeResult(
            query_id=result.id,
            question=result.question,
            dimensions=[DimensionScore(d, "F", "Judge response unparseable") for d in DIMENSIONS],
            overall_grade="F",
            overall_reasoning=f"Judge response unparseable: {text[:200]}",
        )

    dimensions = []
    for dim_data in data.get("dimensions", []):
        grade = dim_data.get("grade", "F")
        if grade not in GRADE_TO_NUM:
            grade = "F"
        dimensions.append(DimensionScore(
            dimension=dim_data.get("dimension", "unknown"),
            grade=grade,
            reasoning=dim_data.get("reasoning", ""),
        ))

    # Ensure all 4 dimensions are present
    found = {d.dimension for d in dimensions}
    for d in DIMENSIONS:
        if d not in found:
            dimensions.append(DimensionScore(d, "F", "Dimension missing from judge response"))

    overall = data.get("overall_grade", _compute_overall_grade(dimensions))
    if overall not in GRADE_TO_NUM:
        overall = _compute_overall_grade(dimensions)

    return JudgeResult(
        query_id=result.id,
        question=result.question,
        dimensions=dimensions,
        overall_grade=overall,
        overall_reasoning=data.get("overall_reasoning", ""),
    )


def _write_judge_json(judge_results: list[JudgeResult], skipped: int, model: str, path: Path) -> None:
    grade_dist: dict[str, int] = {}
    for jr in judge_results:
        grade_dist[jr.overall_grade] = grade_dist.get(jr.overall_grade, 0) + 1

    dim_summaries: dict[str, dict] = {}
    for dim in DIMENSIONS:
        grades_for_dim = [
            d.grade for jr in judge_results for d in jr.dimensions if d.dimension == dim
        ]
        dist: dict[str, int] = {}
        total = 0.0
        for g in grades_for_dim:
            dist[g] = dist.get(g, 0) + 1
            total += GRADE_TO_NUM.get(g, 0)
        dim_summaries[dim] = {
            "avg_numeric": round(total / max(len(grades_for_dim), 1), 2),
            "grade_distribution": dist,
        }

    scores = [GRADE_TO_SCORE.get(jr.overall_grade, 0) for jr in judge_results]
    avg_score = round(sum(scores) / max(len(scores), 1), 4)

    now = datetime.now(timezone.utc).isoformat()
    output = {
        "timestamp": now,
        "last_run": now,
        "judge_model": model,
        "total_queries": len(judge_results),
        "skipped_queries": skipped,
        "overall_grade_distribution": grade_dist,
        "dimension_summaries": dim_summaries,
        "avg_score": avg_score,
        "per_query": [
            {
                "id": jr.query_id,
                "question": jr.question,
                "overall_grade": jr.overall_grade,
                "overall_reasoning": jr.overall_reasoning,
                "dimensions": [
                    {"dimension": d.dimension, "grade": d.grade, "reasoning": d.reasoning}
                    for d in jr.dimensions
                ],
            }
            for jr in judge_results
        ],
    }

    path.write_text(json.dumps(output, indent=2))
    print(f"\nJudge results → {path}")


def _print_judge_summary(judge_results: list[JudgeResult], skipped: int) -> None:
    print(f"\n{'='*60}")
    print(f"LLM-as-Judge: {len(judge_results)} judged, {skipped} skipped")
    print(f"{'='*60}")

    grade_dist = {}
    for jr in judge_results:
        grade_dist[jr.overall_grade] = grade_dist.get(jr.overall_grade, 0) + 1
    dist_str = "  ".join(f"{g}={grade_dist.get(g, 0)}" for g in ["A", "B", "C", "D", "F"])
    print(f"Overall: {dist_str}")

    for dim in DIMENSIONS:
        grades = [d.grade for jr in judge_results for d in jr.dimensions if d.dimension == dim]
        dim_dist = {}
        for g in grades:
            dim_dist[g] = dim_dist.get(g, 0) + 1
        d_str = "  ".join(f"{g}={dim_dist.get(g, 0)}" for g in ["A", "B", "C", "D", "F"])
        label = dim.replace("_", " ").title()
        print(f"  {label:>20}: {d_str}")

    print(f"\n{'ID':<30} {'Overall':>7}  {'Cite':>5} {'Fact':>5} {'Comp':>5} {'Rule':>5}")
    print("-" * 60)
    for jr in judge_results:
        dim_grades = {d.dimension: d.grade for d in jr.dimensions}
        print(
            f"{jr.query_id:<30} {jr.overall_grade:>7}  "
            f"{dim_grades.get('citation_accuracy', '-'):>5} "
            f"{dim_grades.get('factuality', '-'):>5} "
            f"{dim_grades.get('completeness', '-'):>5} "
            f"{dim_grades.get('rule_compliance', '-'):>5}"
        )


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

    eval_exit = 0 if all(r.passed for r in results) else 1

    if getattr(args, "judge", False):
        if not args.full:
            print("ERROR: --judge requires --full", file=sys.stderr)
            return 1

        judgeable = [r for r in results if r.full_answer and (
            not r.plan or r.plan.get("intent") != "clarification_needed"
        )]
        skipped = len(results) - len(judgeable)

        judge_model = getattr(args, "judge_model", "claude-sonnet-4-6")
        judge_out = getattr(args, "judge_out", None) or Path(__file__).resolve().parent / "judge_results.json"

        print(f"\nRunning LLM-as-judge ({judge_model}) on {len(judgeable)} queries...")
        judge_results: list[JudgeResult] = []
        for r in judgeable:
            print(f"  Judging [{r.id}]...", end=" ", flush=True)
            jr = await _run_judge(r, judge_model)
            print(jr.overall_grade)
            judge_results.append(jr)

        _print_judge_summary(judge_results, skipped)
        _write_judge_json(judge_results, skipped, judge_model, judge_out)

    return eval_exit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--router-only", action="store_true", help="Default mode: hit the router only")
    group.add_argument("--full", metavar="URL", default=None, help="Hit a running backend at this base URL (e.g. http://localhost:8000)")
    parser.add_argument("--filter", help="Only run queries whose id or category contains this string")
    parser.add_argument("--out", type=Path, help="Write a markdown report to this path")
    parser.add_argument("--judge", action="store_true", help="Grade synthesis quality with LLM-as-judge (requires --full)")
    parser.add_argument("--judge-model", default="claude-sonnet-4-6", help="Model for the judge (default: claude-sonnet-4-6)")
    parser.add_argument("--judge-out", type=Path, default=None, help="Path for judge JSON output (default: eval/judge_results.json)")
    args = parser.parse_args()

    code = asyncio.run(main_async(args))
    sys.exit(code)


if __name__ == "__main__":
    main()
