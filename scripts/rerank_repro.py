"""Reranker verification harness — mirrors zoning_extract's 5-way gather.

Native/unconstrained runner (no /proc sampling) for the reranker-hang
investigation (2026-06-16) and its fix (2026-06-18). Use it to confirm a fix:
pairs into predict should be candidate_count (20), and the 5-way wall time
should drop vs the pre-fix ~35s native / 40-60s prod figures.

Run from the repo root with reranker forced on:
    RERANKER_ENABLED=true PYTHONPATH=. python scripts/rerank_repro.py

Measures: (1) 5-way concurrency overlap, (2) single-call baseline vs 5-way
wall time. No Anthropic calls — semantic_search only hits qdrant + local torch
models. See claude-context/archive/2026-06-16_report-oom-reranker.md.
"""
import asyncio
import os
import time

from backend.config import get_settings
from backend.retrieval.vector_search import semantic_search

# Same 5 queries zoning_extract.py fires for a report (zone RM-5 as example).
ZONE = "RM-5"
QUERIES = [
    f"{ZONE} floor area ratio maximum building height lot coverage minimum lot area",
    f"{ZONE} required setbacks front yard side yard rear yard transition setback",
    f"{ZONE} permitted uses use group special use",
    f"off-street parking spaces required {ZONE} dwelling unit commercial retail",
    f"{ZONE} landscaping screening loading dock building entrance development standards",
]


async def main() -> None:
    s = get_settings()
    print(f"reranker_enabled={s.reranker_enabled} "
          f"candidate_count={s.reranker_candidate_count} "
          f"qdrant={s.qdrant_url}")
    print(f"OMP_NUM_THREADS={os.getenv('OMP_NUM_THREADS', 'unset')} "
          f"MKL_NUM_THREADS={os.getenv('MKL_NUM_THREADS', 'unset')}")
    try:
        import torch
        print(f"torch.get_num_threads()={torch.get_num_threads()} "
              f"torch.__version__={torch.__version__}")
    except Exception as e:
        print(f"torch introspect failed: {e}")

    # Warm up: load embed + reranker models, JIT caches. Not timed.
    print("\n--- WARMUP (load models) ---")
    t = time.perf_counter()
    await semantic_search(QUERIES[0], top_k=3)
    print(f"warmup call: {time.perf_counter() - t:.2f}s")

    # Single-call baseline (warm) — the serialized floor.
    print("\n--- SINGLE-CALL BASELINE (warm) ---")
    times = []
    for q in QUERIES:
        t = time.perf_counter()
        await semantic_search(q, top_k=3)
        dt = time.perf_counter() - t
        times.append(dt)
        print(f"  single: {dt:.2f}s")
    avg = sum(times) / len(times)
    print(f"avg single-call: {avg:.2f}s  (5x serial floor = {5 * avg:.2f}s)")

    # 5-way concurrent — exactly what zoning_extract does.
    print("\n--- 5-WAY CONCURRENT (mirrors zoning_extract gather) ---")
    t = time.perf_counter()
    await asyncio.gather(*[semantic_search(q, top_k=3) for q in QUERIES])
    five_way = time.perf_counter() - t
    print(f"5-way wall: {five_way:.2f}s")

    print("\n--- VERDICT MATH ---")
    print(f"5x serial floor : {5 * avg:.2f}s")
    print(f"5-way observed  : {five_way:.2f}s")
    ratio = five_way / (5 * avg) if avg else float('nan')
    print(f"observed / floor: {ratio:.2f}x  "
          f"(>1 = worse-than-serial = active thrash; ~<=1 = parallel speedup)")


if __name__ == "__main__":
    asyncio.run(main())
