# Report 504 incident — reranker hang + OOM hardening

**Completed**: 2026-06-16
**Status**: Shipped to production (with one reverted attempt; two open follow-ups)

## What Was Built

Diagnosed and fixed the "Development Feasibility Report never generates" (`/api/report` 504) incident. The **actual** root cause was the reranker hanging `semantic_search`, not memory. Disabling the reranker restored reports (~10s). Alongside it, shipped real OOM-hardening (subprocess-isolated PDF render, swap, nginx timeout) and fixed a long-silent zoning-extraction bug.

## Investigation (the story, because the first diagnosis was wrong)

1. **Symptom**: `/api/report?pin=14301010290000` → 504 at exactly 60s (old nginx default), report never downloads. Scorecard for the same PIN worked.
2. **First lead (partly wrong)**: dmesg showed a 6.8 GB OOM-kill of uvicorn. Concluded the WeasyPrint render spike (inferred ~2.8 GB) on top of the resident citywide discovery index (~3 GB) OOM'd the single worker. Shipped isolation for it (below). **Later finding: the render in isolation is only ~118 MB, and reports were hanging *before* `write_pdf` ran — so the OOM was the worker's accumulated footprint under load, not a single render.**
3. **Real cause**: phase-timed `_fetch_report_data` on prod → only `extract_zoning_standards` hung (>55s); everything else <2.3s. It fires **5 `semantic_search` calls in parallel**, and a single reranked search takes **>40–60s** on the box. `RERANKER_ENABLED=false` → searches 0.2–1.4s, reports render. Reranker `predict(4 pairs)`=0.3s, so the slowness is in the rerank-over-candidates path, not raw inference.
4. **Bonus bug**: while there, found `extract_zoning_standards` returned `None` for everyone — Haiku returns ```` ```json ````-fenced output and the bare `json.loads` failed at char 0, so AI zoning extraction had been silently OFF (always table fallback).

## Implementation Details (shipped)

- **Reranker disabled** (`docker-compose.prod.yml` `RERANKER_ENABLED=false`) — the fix + documented escape valve.
- **Subprocess-isolated PDF render** (`backend/report_render.py`): `render_pdf()` spawns `python -m backend.report_render` (HTML in temp file, PDF out), child imports only weasyprint (no app, no discovery index), `oom_score_adj=1000`, generous `RLIMIT_AS` backstop, parent wall-clock timeout (`report_render_timeout_s=150s`) → clean 503. Measured ~118 MB peak, no index inheritance. `report_concurrency` 2→1.
- **nginx** dedicated `location = /api/report` `proxy_read_timeout 180s` (`frontend/nginx.prod.conf`); rest of `/api/` stays 60s.
- **Host swap 2→8 GB** + `vm.swappiness=10`; `MALLOC_ARENA_MAX=2` on the backend.
- **Discovery index string interning** on load (`parcel_index.py` `_interned_attrs`/`_interned_regions`) — intern attr keys + region strings (not values) to shrink the resident index.
- **Zoning markdown-fence fix** (`zoning_extract.py` `_json_from_model_text` + `test_zoning_extract.py`) — strips fences before `json.loads`; R1 confidence→table fallback still guards low-confidence.
- **Per-report `malloc_trim(0)`** as a response BackgroundTask (`main.py`).
- Tests: `test_report_render.py` (11: timeout/spawn-fail/cleanup/perms), `test_zoning_extract.py` (5).

Commits on `fix/report-oom` → `main`: `9f4bd4d` (isolation+interning+nginx+concurrency), `9a56f92` (reranker off), `4f9d562` (comments+ARENA_MAX), `c78f7aa` (fence fix), `c3410ba` (reranker re-enable attempt) **reverted** by `a465014`, `fc4b846` (honest comments).

## Key Decisions

- **Stayed on the 8 GB CPX32** (Hetzner price hikes made CPX42 ~5× cost) → fixed in code, not hardware.
- **`report_concurrency=1`**: with the render isolated this is about bounding the parent's per-request matplotlib/HTML work, not render OOM.
- **Verify every change against the live API before trusting it** — this caught the reranker re-enable, which *looked* right and still hung.

## What failed / open follow-ups

- **Reranker re-enable (torch threads=1) — REVERTED.** "Thread oversubscription" hypothesis was wrong; capping threads made a single search *worse* (>60s). Reranker stays OFF until the rerank path is profiled (candidate-count, `run_in_executor` interaction, batching). → **RESOLVED 2026-06-18, see follow-up below.**
- **Parent RSS creep ~20 MB/render — UNRESOLVED but benign.** Neither `MALLOC_ARENA_MAX=2` nor `malloc_trim` flattened it (likely live caches). Ample headroom + swap; watch for plateau.

## Files Changed

`backend/report_render.py` (new), `backend/main.py`, `backend/config.py`, `backend/zoning_extract.py`, `backend/discovery/parcel_index.py`, `backend/retrieval/vector_search.py` (torch-cap added then reverted), `frontend/nginx.prod.conf`, `docker-compose.prod.yml`, `backend/tests/test_report_render.py` (new), `backend/tests/test_zoning_extract.py` (new), `backend/tests/test_report_tier0.py`. Host: `/swapfile`, `vm.swappiness`.

---

## 2026-06-18 follow-up — rerank path profiled and fixed (flag still OFF)

The "needs profiling before re-enabling" follow-up above is now done. The rerank hang was **fixed in code on `fix/report-oom`**, but `RERANKER_ENABLED` stays `false` pending one prod-scale verification run (see "Remaining" below).

**Root cause (confirmed, not inferred).** Two compounding bugs, both CPU/concurrency — *not* memory:
1. **Unbounded rerank concurrency.** The report's `extract_zoning_standards` fires **5 `semantic_search` in parallel**; each dispatched its cross-encoder `predict()` to the shared default `ThreadPoolExecutor`. The 5 predicts (each spawning torch intra-op threads) thrash a 4-vCPU box and get **zero parallel speedup** — they serialize at best.
2. **3× oversized batch.** `_rerank_payloads_sync` reranked *all* `scored_hits` (= `fetch_limit` ≈ **60** pairs) to return `top_k`=3, when only `reranker_candidate_count`=20 were ever needed. `predict(4 pairs)`=0.3s, so per-pair inference was never the problem — batch size × serialized concurrency was.

Net effect: 5 × (60-pair predict), serialized → 40–60s on the 4-vCPU box → `/api/report` past the nginx ceiling → 504.

**The diagnostic that settled thrash-vs-swap.** A **native run with swap physically impossible** (48 GB RAM, tiny index) still reproduced the stall: 5-way wall **35.7s = 0.99× the 5×serial floor**, each concurrent `predict` ballooning 6s→35.6s. Since the pathology reproduces where swap cannot occur, it is **CPU-serialization, not swap-bound**. (A constrained `--cpus=4 --memory=8g` Docker run could *not* settle it cleanly — Docker Desktop clamps the VM to ~3.8 GB, so it went swap-bound on an artifact, not prod's 8 GB. Lesson: this Mac cannot faithfully repro prod's 4-vCPU **+8 GB** profile.)

**Why earlier hypotheses were wrong (do not retry):**
- *OOM* — the render in isolation is ~118 MB and reports hung *before* `write_pdf`; the dmesg OOM was the worker's accumulated footprint under load, a separate (already-hardened) issue.
- *torch threads=1* — made a single search **worse**: it stripped each predict's intra-op parallelism *without* removing the 5-way serialization. Thread count was never the lever in isolation; **bounding concurrency is**.

**The fix (`vector_search.py` + `config.py`):**
- Rerank only the **top `reranker_candidate_count` (20)** candidates (sorted by combined dense+keyword score) — the wider `fetch_limit` is still used for dense/keyword recall + dedup. **This 60→20 cut is the dominant, core-independent win.**
- Route every `predict()` through a dedicated **single-worker** `ThreadPoolExecutor` (`_get_rerank_executor()`) so concurrent searches **queue instead of thrash**. (Profiling showed they serialize anyway, so bounding to 1 costs no throughput.)
- New `reranker_torch_threads` setting (default **2**, configurable; applied via the executor's `initializer` so it lands on the thread that runs `predict`). Safe *only* because concurrency is now bounded — the exact thing that made threads=1 backfire before.

**Verified (core-independent dims):** native 5-way **35.7s → 12.4s** (~2.9×), single-call 7.24s → 2.72s, pairs into predict 60 → 20, all reranks on one thread id; **240 tests green**, no regressions.

**Verified on prod 2026-06-18 (empty site = the real 4-vCPU/8 GB box) — fix is insufficient, reranker stays OFF.** Deployed `e59990b` to prod with the flag still false, flipped `RERANKER_ENABLED=true`, measured, rolled back. The fix engages perfectly (pairs=20 confirmed via probe, all reranks on one executor thread, **swap negligible — 124 pages, NOT swap-bound at real 8 GB**) but a single 20-pair `predict()` is still **~40s** and the 5-way report path **~280s ≫ 180s** — *worse* than the original hang. The bge-reranker cross-encoder is simply too slow on these vCPUs (~15× the M4 Pro per-core); the 60→20 cut can't close a 15× hardware gap. **More RAM would do nothing — the wall is CPU, and faster cores are the expensive CPX42 jump we're avoiding.** Verification harness: `scripts/rerank_repro.py` (native) + `scripts/rerank_profile_run.py` (constrained, /proc sampling).

**Real resolution (2026-06-18): decouple the report from the reranker entirely via a precomputed zoning cache.** Rather than make the reranker fast enough, we removed it from the report path: `extract_zoning_standards` is now precomputed offline (deterministic full-section fetch + hybrid table merge) into a committed JSON the report reads. This *also* fixed a latent quality bug — the AI extraction was never delivering bulk numbers even reranked (partial-chunk retrieval). Committed on `fix/report-oom` (`9840d37`), **not yet deployed**. Full record + remaining work: **`guides/zoning-cache.md`**. The branch fix `e59990b` stays as the foundation for any future chat-rerank attempt (ONNX/smaller model).
