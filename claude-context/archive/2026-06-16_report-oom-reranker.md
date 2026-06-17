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

- **Reranker re-enable (torch threads=1) — REVERTED.** "Thread oversubscription" hypothesis was wrong; capping threads made a single search *worse* (>60s). Reranker stays OFF until the rerank path is profiled (candidate-count, `run_in_executor` interaction, batching).
- **Parent RSS creep ~20 MB/render — UNRESOLVED but benign.** Neither `MALLOC_ARENA_MAX=2` nor `malloc_trim` flattened it (likely live caches). Ample headroom + swap; watch for plateau.

## Files Changed

`backend/report_render.py` (new), `backend/main.py`, `backend/config.py`, `backend/zoning_extract.py`, `backend/discovery/parcel_index.py`, `backend/retrieval/vector_search.py` (torch-cap added then reverted), `frontend/nginx.prod.conf`, `docker-compose.prod.yml`, `backend/tests/test_report_render.py` (new), `backend/tests/test_zoning_extract.py` (new), `backend/tests/test_report_tier0.py`. Host: `/swapfile`, `vm.swappiness`.
