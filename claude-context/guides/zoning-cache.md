# Zoning Precompute Cache — engineering reference

**Status (2026-06-18): DEPLOYED & VERIFIED LIVE on prod (`main` @ `69d8481`).** Carries the reranker-fix commit `e59990b` (dormant), the cache `9840d37`, docs `d0c07ce`, and a deploy fix `69d8481`. `RERANKER_ENABLED` stays `false`. Verified: the running prod container returns C1-2 from the cache (FAR 2.2 + setbacks 0/0/30 + min-lot 1000, high confidence); a local `/api/report` render showed the setbacks in the PDF.

**Deploy gotcha that bit us (fixed):** the first push reported CI-green but didn't ship — the Docker build failed at `COPY ingestion/data/zoning_cache.json` because `.dockerignore` excluded the artifact (allowlisted in `.gitignore` but not `.dockerignore`), and the CI deploy script let the build failure pass (old container answered the health curl). Fixed: `.dockerignore` allowlist + `set -e` in `ci.yml`'s deploy script. **Lesson: a committed data artifact needs BOTH `.gitignore` and `.dockerignore` allowlist entries.**

This doc is the carry-across record for the report's zoning-extraction rework. Now that it's shipped + verified, the highlights can be folded into the archive incident doc (`archive/2026-06-16_report-oom-reranker.md`) when convenient.

## Why (the problem we actually found)

`/api/report` 504'd because `extract_zoning_standards` fired **5 reranked `semantic_search` calls** and the reranker is ~40s/search on the prod 4-vCPU box (see reranker status below). `RERANKER_ENABLED=false` stopped the 504s — but a build-everything measurement then revealed a *deeper* truth: **the AI zoning extraction was never delivering the headline bulk numbers (FAR/height/parking) anyway.** Even reranked, **48 of 61 zones came back `low`/null.**

Root cause = **partial-chunk retrieval, not the reranker.** The FAR/height numbers live in big Title-17 tables (e.g. `17-2-0300` "Bulk and density standards" is ~30K chars / 9 tables). The chunker splits them at 1,800 chars, so each semantic search returned a **single ~1,800-char slice** — almost never the slice with the target zone's row. Haiku then wrote "values not provided in retrieved text." The report **silently fell back to the deterministic Title-17 table** (`zoning_definitions.py` → `standards_from_definitions`) the whole time, so users always saw the *correct* bulk numbers — just never any AI value-add.

Key reframing carried forward: **the deterministic table is authoritative and correct for FAR/height/coverage for every base district.** AI's only potential value is the fields the table lacks (setbacks, min-lot-per-unit, special conditions).

## What we built

Precompute the zoning extraction **offline** into a committed JSON artifact read at serve time — so the reranker never runs on the request path, and the report gets full-quality zoning standards deterministically.

1. **Deterministic full-section retrieval (no reranker).** Per zone, `get_full_section()` fetches the **complete** Title-17 "Bulk and density standards" section for the zone's district chapter and feeds the whole table to Haiku. Verified to flip extraction from 48-low to **57/59 high-confidence** with real FAR. Map (`BULK_SECTION_BY_PREFIX` in `zoning_extract.py`, all verified):
   - residential `RS/RT/RM` → `17-2-0300` (note: residential is `-0300`, others `-0400`)
   - business/commercial `B/C` → `17-3-0400`
   - downtown `DX/DC/DR/DS` → `17-4-0400`
   - manufacturing `M` → `17-5-0400`
   - shared parking ratios = `17-10-0200`
   - `POS/PMD/PD/T` → no chapter bulk table → `None` → table/raw-code fallback (POS-1/2 are the 2 of 61 zones with no cache entry, by design)
2. **Hybrid merge (the correctness guarantee).** AI mis-rows FAR on ~7/59 zones — always the low-density "-1" variants (e.g. **B3-1 → 3.0 when the true FAR is 1.2**, 2.5× too high). Unacceptable on a paid report. So the builder **overwrites FAR/height/coverage from the deterministic table** (`standards_from_definitions`) where the table has them, and keeps the AI's value-add fields. Result: **0 FAR errors**, plus AI setbacks (48-49/59) and min-lot (29/59) the table never had. Cache = authoritative bulk + AI nuance.
3. **Serving + invalidation.** Report reads `get_cached_zoning_standards(zone_class)`; a miss or `config_version` mismatch returns `None` → the **existing R1 table fallback** (no new degradation path; can't 504). `config_version` = hash of the section map + extraction prompt + Haiku model. `corpus_fingerprint` = hash of all Title-17 section content-hashes; `ingestion.update` prints a flag when a re-ingest touches Title 17, and `zoning_cache_build --check` reports fresh/stale.

## Files

- `backend/zoning_cache.py` — read path, `get_cached_zoning_standards`, `compute_config_version`, `compute_corpus_fingerprint`, `_normalize_zone_class` (PD-#### → PD), `reset_cache` (tests).
- `backend/zoning_cache_build.py` — offline builder CLI + the hybrid merge + `staleness_flag` + `_check`.
- `backend/zoning_extract.py` — `extract_zoning_standards_from_sections` + `BULK_SECTION_BY_PREFIX` + `_bulk_section_for` + `_haiku_extract`. Legacy `extract_zoning_standards[_with_provenance]` (semantic path) kept for tests only.
- `backend/main.py` — `_fetch_report_data` reads the cache instead of the live task (~L2184/2242).
- `ingestion/data/zoning_cache.json` — the **committed artifact** (104K, 59 zones). Shipped via a `COPY` line in `backend/Dockerfile`.
- `ingestion/update.py` — Title-17 staleness flag after the manifest diff.
- `.gitignore` — fixed so committed `ingestion/data/*` artifacts re-include (see Gotchas).
- Tests: `backend/tests/test_zoning_cache.py` (12).

## Rebuilding the cache

Dev-box command (needs local Qdrant + `ANTHROPIC_API_KEY`; ~2-3 min, no reranker):
```
python -m backend.zoning_cache_build              # full rebuild → ingestion/data/zoning_cache.json
python -m backend.zoning_cache_build --check      # fresh vs current Title-17 corpus?
python -m backend.zoning_cache_build --zones RS-3,B3-2   # subset smoke test
```
Then commit the JSON. **Rebuild whenever ingestion re-ingests Title 17** (the `ingestion.update` flag reminds you) or the extraction prompt/model/section-map changes (`config_version` will otherwise make the serving path ignore the cache and fall back to the table).

## Known issues / limitations (carry forward)

- **AI setbacks / min-lot are NOT cross-validated.** The table gives an authoritative check for FAR/height/coverage, but there's no equivalent source for setbacks/min-lot, so those AI values are plausible-but-unverified and carry the same multi-row mis-read risk that FAR did. They're a genuine uplift the table lacks, labeled as extracted — but treat as lower-trust than the merged bulk numbers.
- **Parking ratios are NOT populated.** Feeding the shared parking section (`17-10-0200`) *alongside* the bulk section regressed FAR (B3-2 → 3.0 vs 2.2 — the extra context made Haiku grab the wrong row), so the builder uses `include_parking=False`. Parking is a **deferred separate-call enhancement** (extract parking-only from `17-10-0200` and merge).
- **`lot_coverage_pct` only 10/59** — the deterministic table genuinely lacks a coverage limit for most non-residential districts; not a bug.
- **`.gitignore` had a latent bug** (now fixed): `ingestion/data/` excluded the *directory*, so `!ingestion/data/<file>` negations were inert — git can't re-include a file under an excluded dir. The pre-existing committed artifacts (`transit_stations.json`, `community_areas.geojson`) only worked because they were already tracked. Fixed by globbing dir *contents* (`ingestion/data/*`). If you add another committed data artifact, the `!` allowlist now actually works.

## Remaining work / expected next steps

1. ~~End-to-end live render~~ ✅ DONE — local `/api/report` for C1-2 rendered the cached FAR + a real Setbacks section in the PDF.
2. ~~Deploy~~ ✅ DONE 2026-06-18 (`main` @ `69d8481`), cache verified live in the prod container.
3. **Parking** via a separate extraction call (optional uplift; feeding it inline regressed FAR).
4. **Setback cross-validation** if/when a structured source is found (currently AI-only, uncross-validated).
5. **Watch for any real report whose zone falls back to the table** (the 2 POS zones + PD/PMD always do, by design) — confirms the fallback path still works in the wild.

## Cost (measured)

Haiku 4.5 = $1/1M in, $5/1M out. Full-section input is **1.4×** the old partial-chunk input (6.7K → 9.5K tok/zone — the old path already pulled ~15 chunks). **Per report: $0** (cache read, no LLM call — down from ~$0.009/report the live path cost). **Per full rebuild: ~$0.70** (offline, only on code/Title-17 change). Prompt-caching the shared section per family could roughly halve the rebuild cost (optional).

## Reranker status (related, carry forward)

`RERANKER_ENABLED=false` stays. **Verified on prod 2026-06-18** (empty site = the real 4-vCPU/8 GB box): the committed reranker fix (`e59990b`: bounded single-worker executor + 20-candidate batch) engages perfectly (pairs=20, serialized, swap negligible — **124 swap pages, NOT swap-bound**) but a single 20-pair `predict()` is still **~40s** and the 5-way report path **~280s ≫ 180s** — the bge-reranker cross-encoder is simply too slow on these vCPUs (~15× the M4 Pro per-core). Rolled back; the zoning cache now keeps the reranker **out of the report path entirely**, so this is moot for reports. Chat's ad-hoc (non-templated) rerank stays off; a smaller/ONNX-quantized cross-encoder is the deferred option there. Full reranker story: `archive/2026-06-16_report-oom-reranker.md` + `core/known-issues.md`. Verification harness: `scripts/rerank_repro.py` + `scripts/rerank_profile_run.py`.
