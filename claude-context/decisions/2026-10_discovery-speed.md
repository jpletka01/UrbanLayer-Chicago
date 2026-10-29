# Discovery speed (redesign Phase 1): engineering decisions

Phase 1 of the Property Discovery redesign makes a search fast on the backend. The cause, measured on 2026-10-29 against a copy of the production index (949,014 rows): every `/search` and `/search/pins` call ran the evaluator over every parcel in pure Python, sorted survivors with a `cmp_to_key` comparator, and `/search` then re-scanned the index once per exclude-policy filter for diagnostics. The page made both calls per edit and nothing was cached. Format: see `README.md` in this folder.

Standing constraints: INV-1 (one evaluator), INV-2 (deterministic per `dataVersion`, `meta` and `source` excluded), INV-4 (summary and count come from `response.cqs`); no model use; no tier-rule, schema, registry or index change. Front-end adoption is out of this arc's first pass (Phase 0 is rewriting `searchClient.ts`, `api.ts` and `DiscoveryPage.tsx`).

---

## Decision 1: sort with C-level keys, proven against the old comparator

**Decision.** `evaluator._order` replaces the `cmp_to_key` comparator with two stable key sorts: candidates with a value are sorted by normalized PIN, then stably by value (`reverse=True` for descending); candidates with no value follow, in PIN order. Output is identical to the comparator's: value, missing last in both directions, ascending-PIN tie-break.

**Alternatives.** (1) Single-pass tuple keys `(±value, pin)`: correct on all 8 key/direction combinations I tried at 949k, but 1.4 to 2.4 s against 0.3 to 0.4 s for the two-pass form (tuple allocation and tuple comparison). (2) Leave the comparator and rely on a cache: broad queries stay 3 to 4 s on every cold edit. (3) Precomputed rank columns or numpy: larger, a second evaluation shape, deferred (see Decision 6).

**Why.** Profile of `evaluate` at 949k parcels: the comparator and its key calls are 85 to 95% of a broad query (about 2.4 s at 600k matches, 3.5 to 4.1 s at 949k); the filter pass is about 390 ms for any filtered query regardless of match count. The prototype matched the old pin order exactly on `lot_size`, `year_built`, `upside_score` and `pin`, ascending and descending, on the real index. `test_key_sort_matches_original_comparator` keeps the old comparator as an oracle on randomized data with ties, missing values and dashed PINs.

**Revisit if** a sort key ever holds mixed types or NaN (both the old and the new sort misbehave there; the index writes JSON numbers only), or if a new sort needs a non-total order.

## Decision 2: count missing-value exclusions inside the single filter pass

**Decision.** `evaluate` returns `OrderedResult.excludedUnknown` (diagnostics D4), computed in the same pass as the filter. A parcel stops at its first failing predicate; if that filter is a tracked scalar exclude-policy filter and the parcel's field is missing, it counts for that filter iff every later predicate passes (earlier ones already did). It cannot count for any other filter, since any other filter's count requires passing this one. `diagnostics.build` passes the field through. The old per-filter scan `_excluded_unknown` stays as the oracle and is no longer on the request path.

**Alternatives.** (1) Move the scans after the response and fetch diagnostics lazily: a second request and one more state for the page to keep consistent (and it does not make the work smaller). (2) One shared scan instead of one per filter: the same order of cost as the fused version without being exact in one pass. (3) Leave as is: about 110 ms per exclude-policy filter, 440 ms for the four-filter recipe, which is the whole gap between `/search` and `/search/pins` on narrow queries.

**Why.** This keeps one evaluator (INV-1): the counts are a deterministic function of `(cqs, dataVersion)` produced by the same code that filters, and the cache stores them with the result. `test_fused_excluded_unknown_matches_reference_scan` compares the fused result to the reference scan for every contiguous subset of five filters (enum, flag, two ranges, a region), with and without a viewport scope, requiring equal values and key order and requiring non-empty results in more than five cases.

**Revisit if** a filter kind other than enum, range, flag or region is added, or `unknownPolicy` stops being per-filter (the fused logic reads both from the registry).

## Decision 3: an INV-2-safe result cache keyed by dataVersion, snapshot generation and the canonical CQS key

**Decision.** `result_cache.cached_evaluate` memoises `evaluate` by `(dataVersion, snapshot generation, canonical_key(cqs))`. The canonical key covers `filters`, `sort` and `scope` only, so `meta` and `source` tags cannot split or merge entries (INV-2). The generation is a process-unique id assigned each time a snapshot is registered (`ParcelSource.generation`), so a snapshot replaced under the same version string (a test convenience in `parcel.py`) cannot serve rows computed on the old one; entries for any other version or generation are dropped when the next entry is stored. Entries are immutable tuples of the PIN strings the parcels already hold, in an LRU of at most 32 entries and 4,000,000 PINs; a result larger than the whole budget is returned but not stored. A failed evaluation raises and stores nothing. `/search`, `/search/pins`, `/search/export` and the zero-result diagnostics all resolve through it, so undo, re-adding a filter, a repeated recipe and every Pro infinite-scroll page after the first are cache hits. `evaluate` itself stays pure and uncached.

**Alternatives.** (1) Cache the serialized response: the key would carry tier, `limit` and `offset`, so repeats rarely hit and the same data would be stored twice. (2) Store row indices in an `array('I')`: 4 bytes per match instead of 8, but it adds an index-to-parcel hop on every read and the savings are small next to the measured allocator overhead below. (3) Key on `dataVersion` alone: the stricter key costs nothing and removes a class of stale-row bugs. (4) A TTL: the answer is deterministic per version, so a TTL would only add misses.

**Why (memory).** Measured in-process on the 949k-row index copy (macOS RSS): 1,353 MB with the index loaded; each 949k-match entry added about 17 to 20 MB (the first +84 MB includes the evaluation's transient lists and allocator high-water). At my first budget of 6M PINs the worst case was +203 MB, so the budget was lowered to 4M PINs, about +130 MB worst case, on a box whose index alone is about 3 GB of 8 GB. Typical entries (thousands of matches) cost kilobytes. Production's allocator (Linux, glibc) may differ; this is a local figure.

**Why (tests).** Cache key ignores `meta`/`source` and enum value order; separates filters, sort and scope; drops older entries on a new version; does not serve a replaced snapshot; `set_snapshot` invalidates; failures and unknown versions store nothing; entry-count LRU order and the PIN budget hold; an oversize result is correct but not stored; a repeated API search is a hit with an identical body.

**Revisit if** production RSS with the cache is more than a few hundred MB above the 2.98 GB baseline, the index grows past about 2M parcels (a 4M-PIN budget then holds only two broad results), or a second worker process is added (the cache is per process).

## Decision 4: coalesce identical in-flight queries and cap concurrent evaluations

**Decision.** Concurrent identical cache misses share one evaluation: the first caller is the leader, the others wait for its result or its exception. Distinct misses queue behind a `BoundedSemaphore(2)` (`MAX_CONCURRENT_EVALS`). The leader stores the entry before it removes its in-flight record, so a newcomer sees either the entry or the in-flight flight, never neither. A shared failure reaches every waiter and is not cached; the next request recomputes.

**Alternatives.** (1) A cap of 1: serialises everything, but 2 lets one request finish while a second is read-blocked or being serialised. (2) A bigger cap: the evaluator is pure Python under the GIL, so more concurrent evaluations only lengthen each one on a 4 vCPU box. (3) Shed load with 503 past a queue depth: not needed until measured under real load; left as the next step if queues build up.

**Why.** The page issues `/search` and `/search/pins` in parallel; without coalescing both miss the cache and evaluate in parallel. A client abort does not stop a server thread (plan, section 3.3), so rapid edits queue full scans. Tests: six identical threads evaluate once; four threads share one failure and nothing is stored; eight distinct queries with a cap of two never exceed two concurrent evaluations and each gets the right result.

**Revisit if** a queue builds up in production (add a depth limit and a 503 with `Retry-After`), or the evaluator becomes cheap enough that the cap only adds latency.

## Decision 5: an additive combined response (`includePins`) as the atomic list-and-map contract

**Decision.** `POST /api/discovery/search` accepts `includePins: bool = False`. When true, the response carries `pins` (the same shape `POST /search/pins` returns), built from the same evaluation as `result`, so `dataVersion`, `total` and ordering are one and the same. `pins` is `null` otherwise. `/search/pins` and `/search/export` are unchanged and remain the rollback path and the export route. Tier behaviour is unchanged: free users still get the capped teaser rows, `gated`, the true total and every map dot.

**This is the single atomic response that Item 30 (`2026-10_build-queue.md`) named as its revisit trigger.** What Item 30 requires stays true in the combined response and is asserted: `pins.dataVersion == dataVersion`, `pins.total == result.total`, the list rows are a prefix of the point sequence, and `pins` equals the `/search/pins` body key for key. The front end keeps Item 30's checks; adopting the combined call is a later change that branches from Phase 0.

**Alternatives.** (1) A new combined route: a second path to keep consistent with the first. (2) Pins always included: every Pro scroll page and every export-adjacent call would carry about 115 KB gzipped it does not need. (3) A server-issued query id that the map echoes: more state for the same guarantee.

**Why (honest accounting).** After the cache (Decision 3) and coalescing (Decision 4), the combined call is not much faster on the server than today's pair. Cold single edit, local, median of 3 backend restarts: the legacy pair issued in parallel is 645 / 353 / 648 / 531 ms for the first four ladder queries, the combined call 527 / 358 / 650 / 533 ms. The recipe differs because the first request after a restart pays one-time warm-up (the pin lookup is built on first use) and the two parallel threads contend for the GIL. So the reason to adopt it is the one Item 30 gave: list and map from one evaluation cannot disagree, and the page makes one request instead of two. It is not a speed claim.

**Revisit if** the page adopts it and a map failure needs to be reported separately from the list (today a failed pins request leaves the list valid), or a server-issued query id is added.

## Decision 6: not done, on purpose

- **Columnar/numpy filtering.** The filter pass is about 390 ms for any filtered query at 949k parcels and is now the largest remaining cost of a cold 4-filter search. A numpy path would reduce it to tens of milliseconds but replaces the evaluator wholesale (INV-1 risk) and needs a second in-memory representation. Revisit if cold narrow searches must be under about 200 ms.
- **`gc.freeze()` after the index loads.** A full garbage collection with the index in memory costs about 760 ms (1.93M tracked objects), which shows up as an occasional ~1 s spike on an otherwise 10 ms cached request (seen once per ladder run, in different cells). `gc.freeze()` after `ensure_loaded` took it to 0 ms in a probe. Not built, because it changes process-wide GC behaviour and was outside the approved design; it is one line and its own commit if wanted.
- **Warming the pin lookup at startup.** The first request after a restart builds the pin-to-parcel dict (about 100 to 150 ms).

---

## Numbers

Measured 2026-10-29 on a local idle Mac (macOS 15, arm64) against the 949,014-row production index copy, backend started from this branch, single uvicorn worker, dev auth (Pro). **Not production**: production is a busy 4 vCPU box and was about 1.5 to 2.5 times slower on the plan's own measurements. Sort `lot_size desc`, medians in ms.

| Query | Matches | Before: /search | Before: /pins | Before: both (sum) | After: cold edit, legacy pair in parallel | After: cold edit, combined | After: repeat or undo |
|---|---:|---:|---:|---:|---:|---:|---:|
| recipe (4 filters) | 5,005 | 876 | 408 | 1,284 | 645 | 527 | ~1 to 11 |
| 3 filters (no lot size) | 7,531 | 675 | 409 | 1,084 | 353 | 358 | ~1 to 11 |
| 1 filter (zoning: residential) | 599,804 | 3,221 | 3,177 | 6,398 | 648 | 650 | ~1 to 11 |
| no filters | 949,014 | 4,017 | 4,113 | 8,130 | 531 | 533 | ~1 to 11 |
| recipe again (repeat) | 5,005 | 864 | 402 | 1,266 | 12 | 12 | ~1 to 11 |

"Before: both" is the sum of the two calls run one after another (sequential, as in the plan's ladder); the parallel pair was not measured before the change. The first recipe cell after a restart includes a one-time pin-lookup build. "After: repeat" is 1 to 2 ms for `/search` and about 10 to 11 ms for `/search/pins` and the combined call (building up to 5,000 map points).

Step by step (cold `/search`, median unless noted): comparator sort replaced and D4 fused: recipe 876 to 343, 1 filter 3,221 to 616, no filters 4,017 to 496 (`after-sort-and-fused-d4`); the cache then takes the repeat to 1 to 2 ms (`after-cache`).

| Other | Before | After |
|---|---|---|
| Backend tests (`backend/tests/test_discovery_*.py`) | 199 | 225 (26 new) |
| Full backend suite (`-m "not integration"`) | n/a (origin/main not re-run) | 2,453 passed, 5 skipped, 66 deselected |
| Eval tests | n/a | 171 passed |
| Frontend vitest (unchanged code) | 816 | 816 passed, 68 files |
| In-process RSS, index loaded | n/a | 1,353 MB; cache +17 to 20 MB per 949k-match entry |
| `pytest -k discovery` parity | n/a | list rows = map prefix, equal totals and versions, combined `pins` = `/search/pins` body |

**Reproduce:**
- Start a local backend with the index copy, then `PYTHONPATH=. python -m eval.discovery_latency --base http://localhost:<port> --label <name> --runs 5` for the ladder (results in `eval/results/2026-10-29-discovery/`; `baseline` is the commit before this arc's changes, `final` is the end state).
- Cold single-edit: restart the backend, then `... --cold legacy --label cold-legacy-1` and `... --cold combined ...` (three restarts each; medians above).
- Sort parity, D4 parity, cache, coalescing and combined-response tests: `python -m pytest backend/tests/test_discovery_*.py -q`.
- Memory and GC probes were scratch scripts (not committed): load the index, call `_resolve` on eight no-filter sorts and read `ps -o rss`; `gc.collect()` timing before and after `gc.freeze()`.

**Not measured:** any production latency or memory (a read-only production re-measure is a separate, approved step); multi-user load (the concurrency cap and coalescing are covered by unit tests, not by a load test); Linux/glibc memory behaviour of the cache; Pro infinite-scroll paging end to end (it is a cache hit by construction, not timed); the front end (no page adopts `includePins` yet); how often the GC spike occurs in production; first-request warm-up on the production box.
