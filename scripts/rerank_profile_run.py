"""Constrained-box profiler for the reranker hang. Run INSIDE a Linux
--cpus=4 --memory=8g container (the genuine 4-vCPU/8GB repro). Samples /proc
context-switches + swap + process RSS once per second while running the 5-way
rerank repro, so we can settle the thrash-vs-swap fork with real kernel
counters. NOTE: Docker Desktop on macOS clamps the VM to ~3.8GB, which makes
this run swap-bound and unrepresentative — use a real 4-vCPU/8GB Linux box to
get a clean wall-time for the prod re-enable decision.

    THREADS=<n>                python scripts/rerank_profile_run.py  # OMP threads pre-import
    RERANKER_TORCH_THREADS=<n> python scripts/rerank_profile_run.py  # the config lever
    QUICK=1                    ...                                   # 1 baseline call, not 5

See claude-context/archive/2026-06-16_report-oom-reranker.md.
"""
import asyncio
import os
import threading
import time

# Set thread count BEFORE importing torch, if requested.
_THREADS = int(os.getenv("THREADS", "0"))
if _THREADS > 0:
    os.environ["OMP_NUM_THREADS"] = str(_THREADS)
    os.environ["MKL_NUM_THREADS"] = str(_THREADS)

from backend.config import get_settings
from backend.retrieval.vector_search import semantic_search

# Opt-in probe (PROBE=1): wrap the rerank fn to log pairs-into-predict + thread
# id, so a run can CONFIRM the fix engages (batch == candidate_count, all reranks
# on one executor thread) without touching the deployed service code.
if os.getenv("PROBE"):
    import threading
    import backend.retrieval.vector_search as _vs

    _orig_rerank = _vs._rerank_payloads_sync

    def _probed_rerank(query, scored_hits):
        print(f"PROBE rerank pairs={len(scored_hits)} tid={threading.get_ident()}", flush=True)
        return _orig_rerank(query, scored_hits)

    _vs._rerank_payloads_sync = _probed_rerank

ZONE = "RM-5"
QUERIES = [
    f"{ZONE} floor area ratio maximum building height lot coverage minimum lot area",
    f"{ZONE} required setbacks front yard side yard rear yard transition setback",
    f"{ZONE} permitted uses use group special use",
    f"off-street parking spaces required {ZONE} dwelling unit commercial retail",
    f"{ZONE} landscaping screening loading dock building entrance development standards",
]


def _read_ctxt() -> int:
    with open("/proc/stat") as f:
        for line in f:
            if line.startswith("ctxt"):
                return int(line.split()[1])
    return 0


def _read_swap() -> tuple[int, int]:
    pin = pout = 0
    with open("/proc/vmstat") as f:
        for line in f:
            if line.startswith("pswpin"):
                pin = int(line.split()[1])
            elif line.startswith("pswpout"):
                pout = int(line.split()[1])
    return pin, pout


def _read_rss_mb() -> float:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS"):
                return int(line.split()[1]) / 1024.0
    return 0.0


_stop = threading.Event()
_samples: list[tuple[float, float, int, int, float]] = []  # t, rss, cs/s, swap/s, -


def _sampler() -> None:
    last_ctxt = _read_ctxt()
    last_pin, last_pout = _read_swap()
    t0 = time.perf_counter()
    while not _stop.wait(1.0):
        ctxt = _read_ctxt()
        pin, pout = _read_swap()
        rss = _read_rss_mb()
        cs = ctxt - last_ctxt
        sw = (pin - last_pin) + (pout - last_pout)
        _samples.append((time.perf_counter() - t0, rss, cs, sw, 0.0))
        print(f"  [sample t={_samples[-1][0]:5.1f}s] rss={rss:6.0f}MB "
              f"cs/s={cs:8d} swap_pages/s={sw:6d}", flush=True)
        last_ctxt, last_pin, last_pout = ctxt, pin, pout


async def main() -> None:
    s = get_settings()
    import torch
    print(f"reranker_enabled={s.reranker_enabled} candidate_count={s.reranker_candidate_count}")
    print(f"THREADS env={_THREADS} torch.get_num_threads()={torch.get_num_threads()} "
          f"nproc_visible={os.cpu_count()} torch={torch.__version__}")

    sampler = threading.Thread(target=_sampler, daemon=True)
    sampler.start()

    print(f"settings.reranker_torch_threads={s.reranker_torch_threads}")
    print("\n--- WARMUP ---", flush=True)
    await semantic_search(QUERIES[0], top_k=3)
    print(f"post-warmup torch.get_num_threads()={torch.get_num_threads()}", flush=True)

    print("\n--- SINGLE-CALL BASELINE (warm, serial) ---", flush=True)
    times = []
    baseline_qs = QUERIES[:1] if os.getenv("QUICK") else QUERIES
    for q in baseline_qs:
        t = time.perf_counter()
        await semantic_search(q, top_k=3)
        dt = time.perf_counter() - t
        times.append(dt)
        print(f"  single: {dt:.2f}s", flush=True)
    avg = sum(times) / len(times)

    print("\n--- 5-WAY CONCURRENT ---", flush=True)
    t = time.perf_counter()
    await asyncio.gather(*[semantic_search(q, top_k=3) for q in QUERIES])
    five_way = time.perf_counter() - t

    _stop.set()
    sampler.join(timeout=3)

    peak_rss = max((r for _, r, _, _, _ in _samples), default=0.0)
    max_cs = max((c for _, _, c, _, _ in _samples), default=0)
    total_swap = sum(sw for _, _, _, sw, _ in _samples)

    print("\n========== SUMMARY ==========")
    print(f"avg single-call : {avg:.2f}s   (5x serial floor = {5*avg:.2f}s)")
    print(f"5-way observed  : {five_way:.2f}s")
    print(f"observed / floor: {five_way/(5*avg):.2f}x")
    print(f"peak process RSS: {peak_rss:.0f} MB  (cgroup limit 8192 MB)")
    print(f"max context-switches/s : {max_cs:,}")
    print(f"total swap pages (in+out) over run : {total_swap}")
    print("FORK:", "SWAP-BOUND" if total_swap > 1000 else "NOT swap (negligible si/so)",
          "|", "thrash present" if five_way > 5*avg*1.1 else "serialized (no parallel gain)")


if __name__ == "__main__":
    asyncio.run(main())
