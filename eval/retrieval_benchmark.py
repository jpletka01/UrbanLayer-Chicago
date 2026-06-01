"""Retrieval quality benchmark for the vector search layer.

Runs user-style questions through semantic_search() and evaluates whether the
returned chunks actually help answer the question — detecting table fragments,
section duplication, semantic drift, and low-content chunks.

Usage:
    python -m eval.retrieval_benchmark [--out PATH] [--top-k N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.retrieval.vector_search import semantic_search


QUERIES = [
    {
        "id": "setback_single_family",
        "question": "What are the setback requirements for a single-family home in Chicago?",
        "category": "dimensional_standards",
        "why": "Common homeowner question — should retrieve RS district setback rules from 17-2-0300, and the setback projection/obstruction table from 17-17-0300",
        "gold_sections": ["17-2-0300", "17-17-0300"],
        "answer_must_contain": ["setback", "feet"],
    },
    {
        "id": "home_occupation",
        "question": "Can I run a small bakery business from my home?",
        "category": "use_rules",
        "why": "Home occupation rules — should find 4-6-270 or 17-9-0202, not just food licensing",
        "gold_sections": ["4-6-270", "17-9-0200"],
        "answer_must_contain": ["home occupation"],
    },
    {
        "id": "minimum_lot_size",
        "question": "What's the minimum lot size for building in an RS-3 zoning district?",
        "category": "dimensional_standards",
        "why": "Specific district dimensional lookup",
        "gold_sections": ["17-2-0300"],
        "answer_must_contain": ["lot area", "square feet"],
    },
    {
        "id": "adu_allowed",
        "question": "Are accessory dwelling units allowed in Chicago?",
        "category": "use_rules",
        "why": "ADU/coach house rules — should find 17-7-0570 (ADU) or 17-9-0200 (coach house)",
        "gold_sections": ["17-7-0570", "17-9-0200"],
        "answer_must_contain": ["accessory dwelling", "coach house", "additional dwelling"],
    },
    {
        "id": "noise_ordinance",
        "question": "What are the noise ordinance rules in Chicago?",
        "category": "non_zoning",
        "why": "Non-zoning retrieval — noise regs in Title 8",
        "gold_sections": ["8-32"],
        "answer_must_contain": ["noise"],
    },
    {
        "id": "fence_height",
        "question": "How tall can a fence be in a residential area?",
        "category": "accessory_structures",
        "why": "Should retrieve fence/wall height limits from accessory structure or screening rules",
        "gold_sections": ["17-9", "17-11-0200", "17-5-0600", "10-28-281"],
        "answer_must_contain": ["fence"],
    },
    {
        "id": "garage_conversion",
        "question": "Can I convert my garage into a living space?",
        "category": "use_rules",
        "why": "Garage conversion touches building code + accessory use rules",
        "gold_sections": ["17-9-0200", "18-28"],
        "answer_must_contain": ["garage"],
    },
    {
        "id": "short_term_rental",
        "question": "What are the regulations for Airbnb and short-term rentals in Chicago?",
        "category": "licensing",
        "why": "STR rules in Title 4-13",
        "gold_sections": ["4-13"],
        "answer_must_contain": ["rental", "license"],
    },
    {
        "id": "deck_setback",
        "question": "How close to the property line can I build a deck?",
        "category": "dimensional_standards",
        "why": "Deck/patio setback rules — should find accessory structure setbacks, not wireless towers",
        "gold_sections": ["17-9-0200", "17-2-0300"],
        "answer_must_contain": ["setback", "property line"],
    },
    {
        "id": "food_trucks",
        "question": "What are the regulations for food trucks in Chicago?",
        "category": "licensing",
        "why": "Mobile food vendor rules in Title 4/7",
        "gold_sections": ["4-8-037", "7-38"],
        "answer_must_contain": ["food", "mobile"],
    },
    {
        "id": "tree_removal",
        "question": "Do I need a permit to cut down a tree on my property?",
        "category": "non_zoning",
        "why": "Tree protection ordinance in Title 10-32",
        "gold_sections": ["10-32"],
        "answer_must_contain": ["tree", "permit"],
    },
    {
        "id": "lot_coverage_rm5",
        "question": "What is the maximum lot coverage allowed in an RM-5 district?",
        "category": "dimensional_standards",
        "why": "Should find RM-5 bulk table with lot coverage percentage in 17-2-0300",
        "gold_sections": ["17-2-0300"],
        "answer_must_contain": ["lot coverage", "percent"],
    },
    {
        "id": "landscaping_requirements",
        "question": "What are the landscaping requirements for new construction in Chicago?",
        "category": "site_design",
        "why": "Landscape standards in 17-11",
        "gold_sections": ["17-11"],
        "answer_must_contain": ["landscap"],
    },
    {
        "id": "rooftop_deck",
        "question": "Can I build a rooftop deck on my building?",
        "category": "accessory_structures",
        "why": "Rooftop structure rules — height/setback from 17-17 or building code",
        "gold_sections": ["17-17-0300", "4-388"],
        "answer_must_contain": ["roof", "deck"],
    },
    {
        "id": "liquor_school_distance",
        "question": "How far does a bar need to be from a school to get a liquor license?",
        "category": "licensing",
        "why": "Liquor license distance restrictions in 4-60",
        "gold_sections": ["4-60"],
        "answer_must_contain": ["liquor", "feet"],
    },
    {
        "id": "restaurant_parking",
        "question": "How many parking spots does a restaurant need to provide?",
        "category": "parking",
        "why": "Parking ratios in 17-10 — should find the eating/drinking parking group, not random other groups",
        "gold_sections": ["17-10-0200"],
        "answer_must_contain": ["parking", "ratio"],
    },
    {
        "id": "affordable_housing",
        "question": "What are the affordable housing requirements for developers in Chicago?",
        "category": "planned_development",
        "why": "ARO in 2-44",
        "gold_sections": ["2-44"],
        "answer_must_contain": ["affordable"],
    },
    {
        "id": "buildable_lot_definition",
        "question": "What is the definition of a buildable lot under the Chicago zoning code?",
        "category": "definitions",
        "why": "Definition lookup — should find lot definitions in 17-17, 16-4, or 17-15",
        "gold_sections": ["17-17", "16-4", "17-15"],
        "answer_must_contain": ["lot"],
    },
]


@dataclass
class ChunkAnalysis:
    rank: int
    section: str
    section_title: str
    score: float
    char_count: int
    has_table: bool
    data_row_count: int
    is_table_fragment: bool
    is_header_only: bool
    is_legend_only: bool
    is_transitional: bool
    matches_gold_section: bool
    body_preview: str


@dataclass
class QueryResult:
    id: str
    question: str
    category: str
    chunk_count: int
    analyses: list[ChunkAnalysis]
    gold_hit_count: int
    unique_sections: int
    duplicate_section_count: int
    table_fragment_count: int
    low_content_count: int
    grade: str
    issues: list[str]
    avg_score: float
    top_score: float


_ROW_RE = re.compile(r"^Row \d+:", re.MULTILINE)
_LEGEND_RE = re.compile(r"Row \d+ \(all columns\):")


def _get_body(text: str) -> str:
    lines = text.split("\n")
    body_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("§ ") or stripped.startswith("(part "):
            body_start = i + 1
            break
    return "\n".join(lines[body_start:]).strip()


def _analyze_chunk(chunk, rank: int, gold_sections: list[str]) -> ChunkAnalysis:
    text = chunk.text
    body = _get_body(text)

    has_table = "[TABLE]" in text
    data_rows = len(_ROW_RE.findall(text))
    legend_rows = len(_LEGEND_RE.findall(text))

    is_header_only = len(body) < 30
    is_legend_only = has_table and legend_rows > 0 and data_rows == 0
    is_transitional = "17-1-1400" in chunk.section

    is_table_fragment = has_table and data_rows <= 3 and data_rows > 0

    matches_gold = any(
        chunk.section.startswith(g) for g in gold_sections
    )

    return ChunkAnalysis(
        rank=rank,
        section=chunk.section,
        section_title=chunk.section_title,
        score=round(chunk.score, 4),
        char_count=len(text),
        has_table=has_table,
        data_row_count=data_rows,
        is_table_fragment=is_table_fragment,
        is_header_only=is_header_only,
        is_legend_only=is_legend_only,
        is_transitional=is_transitional,
        matches_gold_section=matches_gold,
        body_preview=body[:200].replace("\n", " ").strip(),
    )


def _grade_query(analyses: list[ChunkAnalysis], answer_must_contain: list[str]) -> tuple[str, list[str]]:
    issues = []
    total = len(analyses)
    if total == 0:
        return "F", ["no chunks returned"]

    gold_hits = sum(1 for a in analyses if a.matches_gold_section)
    top3_gold = sum(1 for a in analyses[:3] if a.matches_gold_section)

    section_counts = Counter(a.section for a in analyses)
    dup_sections = sum(v - 1 for v in section_counts.values() if v > 1)
    unique_sections = len(section_counts)

    table_frags = sum(1 for a in analyses if a.is_table_fragment)
    low_content = sum(1 for a in analyses if a.is_header_only or a.is_legend_only or a.is_transitional)

    # Check if body text of retrieved chunks collectively addresses the question
    all_body = " ".join(a.body_preview.lower() for a in analyses)
    missing_terms = [t for t in answer_must_contain if t.lower() not in all_body]

    if gold_hits == 0:
        issues.append(f"MISS: none of the {total} chunks match expected sections")
    if top3_gold == 0 and gold_hits > 0:
        issues.append(f"gold section(s) found but not in top-3")
    if dup_sections > 0:
        dup_secs = [s for s, c in section_counts.items() if c > 1]
        issues.append(f"{dup_sections} duplicate chunk(s) from same section: {', '.join(dup_secs)}")
    if table_frags >= 3:
        issues.append(f"{table_frags}/{total} chunks are small table fragments (<=3 data rows)")
    if low_content > 0:
        issues.append(f"{low_content}/{total} chunks are low-content (header-only/legend/transitional)")
    if missing_terms:
        issues.append(f"answer terms missing from results: {missing_terms}")

    # Grade based on gold section coverage and content quality
    if gold_hits == 0:
        grade = "F"
    elif top3_gold == 0:
        grade = "D"
    elif table_frags >= 3 or dup_sections >= 3:
        grade = "C"
    elif missing_terms:
        grade = "C"
    elif gold_hits >= 2 and top3_gold >= 2 and dup_sections == 0:
        grade = "A"
    elif gold_hits >= 1 and top3_gold >= 1:
        grade = "B" if dup_sections > 0 or table_frags > 0 else "A"
    else:
        grade = "B"

    return grade, issues


def run_benchmark(top_k: int = 5) -> list[QueryResult]:
    return asyncio.run(_run_benchmark_async(top_k))


async def _run_benchmark_async(top_k: int) -> list[QueryResult]:
    results = []
    for q in QUERIES:
        chunks = await semantic_search(q["question"], top_k=top_k)
        analyses = [
            _analyze_chunk(c, i + 1, q["gold_sections"])
            for i, c in enumerate(chunks)
        ]
        grade, issues = _grade_query(analyses, q["answer_must_contain"])

        section_counts = Counter(a.section for a in analyses)
        scores = [a.score for a in analyses]

        results.append(QueryResult(
            id=q["id"],
            question=q["question"],
            category=q["category"],
            chunk_count=len(chunks),
            analyses=analyses,
            gold_hit_count=sum(1 for a in analyses if a.matches_gold_section),
            unique_sections=len(section_counts),
            duplicate_section_count=sum(v - 1 for v in section_counts.values() if v > 1),
            table_fragment_count=sum(1 for a in analyses if a.is_table_fragment),
            low_content_count=sum(1 for a in analyses if a.is_header_only or a.is_legend_only or a.is_transitional),
            grade=grade,
            issues=issues,
            avg_score=round(sum(scores) / len(scores), 4) if scores else 0,
            top_score=round(max(scores), 4) if scores else 0,
        ))
    return results


def print_report(results: list[QueryResult]) -> None:
    total = len(results)
    grades = {g: sum(1 for r in results if r.grade == g) for g in "ABCDF"}
    all_chunks = sum(r.chunk_count for r in results)

    print("=" * 80)
    print("RETRIEVAL QUALITY BENCHMARK")
    print("=" * 80)
    print()
    print(f"Queries: {total}  |  Chunks evaluated: {all_chunks}")
    print(f"Grades: A={grades['A']}  B={grades['B']}  C={grades['C']}  D={grades['D']}  F={grades['F']}")
    print()

    # Aggregate issues
    total_gold_hits = sum(r.gold_hit_count for r in results)
    total_dups = sum(r.duplicate_section_count for r in results)
    total_table_frags = sum(r.table_fragment_count for r in results)
    total_low = sum(r.low_content_count for r in results)
    print(f"Gold section hits:      {total_gold_hits}/{all_chunks} ({100*total_gold_hits/all_chunks:.0f}%)")
    print(f"Duplicate section slots: {total_dups}/{all_chunks} ({100*total_dups/all_chunks:.0f}%) — wasted on same-section chunks")
    print(f"Table fragments (<=3 rows): {total_table_frags}/{all_chunks} ({100*total_table_frags/all_chunks:.0f}%)")
    print(f"Low-content chunks:     {total_low}/{all_chunks} ({100*total_low/all_chunks:.0f}%)")
    print()

    for r in results:
        icon = {"A": "+", "B": "~", "C": "!", "D": "!!", "F": "X"}.get(r.grade, "?")
        print(f"[{r.grade}] {r.id}")
        print(f"    Q: {r.question}")
        print(f"    gold={r.gold_hit_count}/{r.chunk_count}  unique_sections={r.unique_sections}  "
              f"dups={r.duplicate_section_count}  table_frags={r.table_fragment_count}  "
              f"top_score={r.top_score}")
        if r.issues:
            for issue in r.issues:
                print(f"    >> {issue}")
        for a in r.analyses:
            flags = []
            if a.is_table_fragment:
                flags.append(f"TABLE-FRAG({a.data_row_count}rows)")
            if a.is_header_only:
                flags.append("HEADER-ONLY")
            if a.is_legend_only:
                flags.append("LEGEND-ONLY")
            if a.is_transitional:
                flags.append("TRANSITIONAL")
            gold_mark = "G" if a.matches_gold_section else " "
            flag_str = f"  [{', '.join(flags)}]" if flags else ""
            print(f"      {a.rank}. [{gold_mark}] {a.score:.4f}  §{a.section} ({a.section_title[:40]}){flag_str}")
            print(f"                {a.body_preview[:110]}")
        print()

    # Per-category
    print("=" * 80)
    print("PER-CATEGORY SUMMARY")
    print("=" * 80)
    cats = sorted(set(r.category for r in results))
    for cat in cats:
        cr = [r for r in results if r.category == cat]
        g = "".join(r.grade for r in cr)
        gold = sum(r.gold_hit_count for r in cr)
        tot = sum(r.chunk_count for r in cr)
        dups = sum(r.duplicate_section_count for r in cr)
        frags = sum(r.table_fragment_count for r in cr)
        print(f"  {cat:25s}  grades={g:6s}  gold={gold}/{tot}  dups={dups}  frags={frags}")


def write_markdown(results: list[QueryResult], path: Path) -> None:
    all_chunks = sum(r.chunk_count for r in results)
    grades = {g: sum(1 for r in results if r.grade == g) for g in "ABCDF"}
    total_gold = sum(r.gold_hit_count for r in results)
    total_dups = sum(r.duplicate_section_count for r in results)
    total_frags = sum(r.table_fragment_count for r in results)
    total_low = sum(r.low_content_count for r in results)

    lines = [
        "# Retrieval Quality Benchmark",
        "",
        "## Summary",
        "",
        f"- **Queries**: {len(results)}",
        f"- **Chunks evaluated**: {all_chunks}",
        f"- **Grades**: A={grades['A']}  B={grades['B']}  C={grades['C']}  D={grades['D']}  F={grades['F']}",
        "",
        "### Aggregate Metrics",
        "",
        f"| Metric | Count | % |",
        f"|---|---:|---:|",
        f"| Gold section hits | {total_gold}/{all_chunks} | {100*total_gold/all_chunks:.0f}% |",
        f"| Duplicate section slots | {total_dups}/{all_chunks} | {100*total_dups/all_chunks:.0f}% |",
        f"| Table fragments (<=3 rows) | {total_frags}/{all_chunks} | {100*total_frags/all_chunks:.0f}% |",
        f"| Low-content chunks | {total_low}/{all_chunks} | {100*total_low/all_chunks:.0f}% |",
        "",
        "## Per-Query Results",
        "",
        "| Grade | ID | Question | Gold Hits | Dups | Table Frags | Issues |",
        "|:---:|---|---|:---:|:---:|:---:|---|",
    ]
    for r in results:
        q = r.question.replace("|", "\\|")[:55]
        issues_str = "; ".join(r.issues)[:80].replace("|", "\\|") if r.issues else ""
        lines.append(
            f"| **{r.grade}** | `{r.id}` | {q} | {r.gold_hit_count}/{r.chunk_count} "
            f"| {r.duplicate_section_count} | {r.table_fragment_count} | {issues_str} |"
        )

    lines.extend(["", "## Detailed Chunk Analysis", ""])
    for r in results:
        lines.append(f"### `{r.id}` — Grade {r.grade}")
        lines.append(f"**Q:** {r.question}")
        lines.append("")
        if r.issues:
            for issue in r.issues:
                lines.append(f"- {issue}")
            lines.append("")
        lines.append("| # | Gold | Score | Section | Flags | Preview |")
        lines.append("|:---:|:---:|---:|---|---|---|")
        for a in r.analyses:
            flags = []
            if a.is_table_fragment:
                flags.append(f"frag({a.data_row_count})")
            if a.is_header_only:
                flags.append("empty")
            if a.is_legend_only:
                flags.append("legend")
            if a.is_transitional:
                flags.append("trans")
            gold = "Y" if a.matches_gold_section else ""
            flag_str = ", ".join(flags) if flags else ""
            preview = a.body_preview[:100].replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {a.rank} | {gold} | {a.score} | `{a.section}` | {flag_str} | {preview} |"
            )
        lines.extend(["", "---", ""])

    # Category summary
    lines.extend(["## Category Summary", ""])
    lines.append("| Category | Grades | Gold Hits | Dups | Frags |")
    lines.append("|---|---|---:|---:|---:|")
    cats = sorted(set(r.category for r in results))
    for cat in cats:
        cr = [r for r in results if r.category == cat]
        g = " ".join(r.grade for r in cr)
        gold = sum(r.gold_hit_count for r in cr)
        tot = sum(r.chunk_count for r in cr)
        dups = sum(r.duplicate_section_count for r in cr)
        frags = sum(r.table_fragment_count for r in cr)
        lines.append(f"| {cat} | {g} | {gold}/{tot} | {dups} | {frags} |")

    # Findings section
    lines.extend([
        "",
        "## Key Findings",
        "",
        "*(auto-generated from benchmark data)*",
        "",
    ])

    # Find worst queries
    problem_queries = [r for r in results if r.grade in ("C", "D", "F")]
    if problem_queries:
        lines.append("### Problem Queries")
        lines.append("")
        for r in problem_queries:
            lines.append(f"- **{r.id}** (grade {r.grade}): {'; '.join(r.issues)}")
        lines.append("")

    # Table fragmentation analysis
    frag_queries = [r for r in results if r.table_fragment_count >= 2]
    if frag_queries:
        lines.append("### Table Fragmentation")
        lines.append("")
        lines.append("These queries returned multiple small table fragments that waste retrieval slots:")
        lines.append("")
        for r in frag_queries:
            sections = [a.section for a in r.analyses if a.is_table_fragment]
            lines.append(f"- **{r.id}**: {r.table_fragment_count} fragments from {', '.join(set(sections))}")
        lines.append("")

    # Section duplication analysis
    dup_queries = [r for r in results if r.duplicate_section_count >= 2]
    if dup_queries:
        lines.append("### Section Duplication")
        lines.append("")
        lines.append("These queries returned multiple chunks from the same section, wasting result diversity:")
        lines.append("")
        for r in dup_queries:
            counts = Counter(a.section for a in r.analyses)
            dups = {s: c for s, c in counts.items() if c > 1}
            lines.append(f"- **{r.id}**: {dups}")
        lines.append("")

    path.write_text("\n".join(lines))
    print(f"\nMarkdown report written to {path}")


def write_json(results: list[QueryResult], path: Path) -> None:
    from datetime import datetime, timezone
    grades = {g: sum(1 for r in results if r.grade == g) for g in "ABCDF"}
    scores = [r.avg_score for r in results if r.avg_score > 0]
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_queries": len(results),
        "grade_distribution": grades,
        "avg_score": round(sum(scores) / len(scores), 4) if scores else 0,
        "per_query": [
            {
                "id": r.id,
                "grade": r.grade,
                "score": r.avg_score,
                "issues": r.issues,
            }
            for r in results
        ],
    }
    path.write_text(json.dumps(output, indent=2))
    print(f"\nJSON results written to {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="Write markdown report")
    parser.add_argument("--json-out", type=Path, help="Write JSON results for admin dashboard")
    parser.add_argument("--top-k", type=int, default=5, help="Chunks per query (default 5)")
    args = parser.parse_args()

    results = run_benchmark(top_k=args.top_k)
    print_report(results)
    if args.out:
        write_markdown(results, args.out)
    if args.json_out:
        write_json(results, args.json_out)


if __name__ == "__main__":
    main()
