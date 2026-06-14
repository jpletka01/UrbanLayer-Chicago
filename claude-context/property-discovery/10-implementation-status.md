# 10 — Implementation Status & Decisions Record

**Status: SHIPPED to production in two waves, still DORMANT by design.**
- **Wave 1 (2026-06-13, `f192d57`)** — build-plan `08` steps 1–10: the invariant core,
  compilers, evaluator, diagnostics, offline index builder, and a list-first frontend.
- **Wave 2 (2026-06-14, merge `8c279c6`)** — the **result.rows workbench (PR1–PR10)**: turned
  the dormant filter form into a goal-first, map-backed prospecting workbench. See the new
  section **"The result.rows workbench"** below for the full record.

**Dormant by design (still true after Wave 2):** premium-gated for the full experience,
**unlinked from nav**, and the prod **index is still empty** (`/api/discovery/search` returns
the empty-index fallback) — so coverage reads "none", every filter/recipe reads "coming", and
the page is honestly inert until the prod index is built. The real launch is gated on
**PR-INDEX → PR-VAL → PR-LIVE** (see "What remains"), which are blocked by the 2026-06-13
Socrata 503 outage.

This doc records **what was actually built, the decisions made during implementation that
were not fully pinned by the spec (00–09), and what remains.** The spec docs 00–09 stay the
normative design; this is the reality + rationale log for future sessions.

Tests after Wave 2: backend **166 discovery tests** (full backend **unit** suite 782, no
regressions — the only full-suite failures are live external-API integration tests down on the
Socrata/ArcGIS outage); frontend **48 vitest** tests; `tsc --noEmit` clean.

---

## The result.rows workbench (PR1–PR10, merged 2026-06-14 `8c279c6`)

Wave 1 shipped a *dormant filter form*. A design review (recorded in conversation, founder-led)
concluded the **output, the cold-start honesty, the paywall, and the IA** were the real problems
— not the filter labels. Wave 2 rebuilt around that, in ten independently-shippable PRs on
branch `feat/discovery-result-rows`. **Each PR was reviewed + guardrailed before the next.**

### The thesis (why these PRs, in this order)
The keystone was the **frozen wire `result = {pins, total}`** — a list of opaque PINs with no
attributes, no map, no export. Everything downstream (scannable list, map, CSV, teaser) was
blocked by it. So PR1 broke that contract first; the rest layer on top.

### The PRs
| PR | What | Key contract/decision |
|---|---|---|
| **PR1** | `result.rows` wire keystone | `SearchResult{pins,total}` → `{rows,total,nextOffset}`; `SearchRequest +limit/offset`. `evaluate()` UNTOUCHED — still returns the full ordered pin list; the API slices the window and hydrates rows from the same snapshot. Extracted **`_resolve(req)`** = the single parse→merge→evaluate path so `/search`, `/search/pins`, `/search/export` can't drift by construction. |
| **PR1-fix** | 0/exempt sort reconcile | The locked "null sort input, no evaluator change" was *unrealizable* (the comparator reads the snapshot). Reconciled: keep `total_assessed_value` real (filter + display honest), add a **sort-only field `total_assessed_value_sortkey`** (null for exempt/$0); the `assessed_value` SORT key points at it, the FILTER stays on the real field. Comparator's existing missing-last path does the rest. Stated plainly: this is an evaluator-**input** change, not "no evaluator change." Filter stays **inclusive** of exempt/$0 (Jack's call). |
| **PR2** | Registry metadata + content | `RangeMeta{domain,step,boundMode,display,presets}` + `requires`/`label`/`help`/`enumLabels` (presentation only; evaluator never reads them). Hand-authored labels for all **32 filters** (kills `humanize()` display). **3 new derived filters** (`value_percentile`, `upside_score`, `is_teardown_candidate` — nullable until PR-INDEX). New sortKeys; **6 prospecting recipes** in `topics`; `defaultSort → assessed_value asc`. |
| **PR4** | Coverage + populatedFields | `registry.coverage{mode,liveAreas,asOf}` + `populatedFields[]`, **injected by `/registry` from index `meta`** (cached artifact stays pure via `model_copy`). Coverage is a standalone banner sourced ONLY from `registry.coverage` — **never enters the CQS/chips** (tested). `populatedFields` drives BOTH consumers (panel "coming" disable + recipe badges). **Critical safe default: missing meta → coverage "none" + empty populatedFields** (dormant), never "all available". |
| **PR5** | Results surface | Address-first row-cards (PIN demoted, active sort bolded); infinite scroll over `nextOffset` (append + dedupe by pin; list never the map's source); **three-way zero state** from PR4 selectors (NULL-backed field / non-live area / too-tight); `caName()` region fix ("West Town" not "neighborhood 24") in chips + summary. CSV deferred to PR7. |
| **PR6** | Map split + `/search/pins` | Reuses Explore's deck.gl `ScatterplotLayer` + `useMapboxOverlay`. `/search/pins` shares `_resolve`/`_pin_lookup` → **pin-SEQUENCE identity** with `/search` (tested under a non-default sort). Returns the FULL ordered coord set (pin+lat/lon+upside+landUse), capped 5000 + `truncated`. **Null upside → a DISTINCT no-data swatch**, never the low end. Bidirectional row↔dot hover sync. |
| **PR7** | `/search/export` CSV | Streams ALL `result.total` rows (no limit/offset) via `_resolve`; **premium-gated** (`require_tier("premium")` → free 403). Human headers from registry labels; exempt/$0 keep TRUE value; filename from canonical-CQS slug. |
| **PR8** | Recipe shelf + query-first IA | Recipe click = `expandTopic` → fold presets into panel as USER filters (editable), apply sort, send `topicId` as **telemetry only** (backend never re-expands; cleared on edit). Honest LIVE/NEEDS-DATA badges from `missingFieldsFor`. NL box promoted; 6 filter categories collapse into a refinement drawer. |
| **PR9** | Free teaser + gate | **Jack's calls, server-enforced:** free = top **10** rows (`FREE_ROW_CAP`, server-capped off the auth dependency, true total + `gated` flag, no paging past), **upside shown** on free rows, **all map dots** but **land-use colored + view-only** (Pro = upside-colored + interactive), **Export shown but locked** → upgrade. Query-aware teaser wall from `summarize()`. Replaced the hard pre-search wall — free users now run a search and hit the teaser. i18n keys (`discovery.*`, en+es). |
| **PR10** | Mobile + a11y | Below md: single column, sticky `[List\|Map]` toggle (map stays MOUNTED — GL context preserved), "Edit filters" bottom sheet, scroll-snap recipe row. a11y: `aria-pressed` flag/enum pills, `role=radiogroup`+`aria-checked` preset chips, labeled min/max inputs, `<label htmlFor>` select. |

### Structural guarantees worth remembering
- **Single resolver.** All three search endpoints go through `_resolve(req)`. Tests assert
  pin-SEQUENCE (not just total) parity, because a dropped sort/scope/topic arg desyncs ORDER
  while total-parity still passes — the exact bug class we grounded on.
- **Coverage is presentational only.** It was *almost* injected into the CQS as a default
  filter; that was retracted as not invariant-safe (precedence + cleared-field would corrupt
  it, and `compile_merge` has no default-precedence layer for filters anyway). It lives only on
  the registry response → a banner outside `response.cqs`.
- **`evaluate()` is still the sole result producer (INV-1).** PR1 pagination/hydration and the
  PR9 tier cap all live in `api.py`, consuming the evaluator's output; the pure leaf is unchanged
  except the PR1-fix sort-key field (an input change, declared as such).

### Deferred from Wave 2 (stated, not hidden)
- **Continuous slider control + `aria-valuetext`** — only preset chips + min/max inputs are
  built; the non-preset ranges (e.g. `improvement_ratio`) keep min/max boxes. A slider is a
  small dedicated follow-up.
- **Map-dot keyboard navigation** — the result list is the accessible path to every parcel.
- **Whole-page i18n** — only the PR9 teaser/export strings are keyed; the rest of the discovery
  surface is still hardcoded English (a known gap from the original review).
- **O(N) pin lookup** — `_pin_lookup` rebuilds a `{pin:parcel}` dict per request over the whole
  snapshot. Fine while dark/small; memoize before the full-city (~1.8M) index goes live.

---

## What was built (by layer)

### Backend — `backend/discovery/`
| File | Step | Role |
|---|---|---|
| `registry.json` + `registry.py` | 1 | The single static artifact (**29 filters**) + Pydantic load/validate/accessors; raises on bad artifact |
| `cqs.py` | 2 | CQS + discriminated-union `Predicate` models; `predicate_is_valid` (R1/R6); `canonical_key`/`cqs_equal`; `CqsFragment`; `DroppedInvalid` |
| `parcel.py` | 2 | `Parcel` protocol, `DictParcel` (test fake), `ParcelSource` (dataVersion-keyed snapshot registry) + `default_source` |
| `predicates.py` | 2 | `satisfies(pred, parcel, field, unknown_policy)` + `within_scope` |
| `evaluator.py` | 3 | `evaluate(cqs, data_version) -> OrderedResult` — the single path (INV-1), leaf module |
| `diagnostics.py` | 4 | `build(...)` — broad/conflicts/droppedInvalid/excludedUnknown/mostRestrictive |
| `compile_text.py` | 5 | Deterministic rule-based `parse(text) -> CqsFragment` + residual |
| `compile_merge.py` | 6 | `merge(...)` — the only writer of canonical CQS; precedence + validity + validation drops |
| `parcel_index.py` | index | `IndexedParcel` (concrete Parcel) + SQLite read/write of the prospecting index |
| `index_build.py` | index | Offline builder CLI (`--community-areas` / `--all`): spine → batch joins → local spatial pass → assemble → upsert |
| `parcel_source.py` | 7/index | Production snapshot seam + current-dataVersion pointer + **`current_meta()`** (coverage/populatedFields source); `ensure_loaded()` loads `discovery_index.db` + `read_meta` else empty fallback |
| `parcel_index.py` | index | `IndexedParcel` + SQLite r/w; **`IndexMeta`/`read_meta`** (PR4); **`derive_sort_fields`** (PR1-fix sort-only key); `write_index` `populated_fields` column |
| `api.py` | 7 / Wave 2 | `GET /api/discovery/registry` (injects coverage+populatedFields), `POST /api/discovery/search` (rows window + free-tier cap + `gated`), **`POST /api/discovery/search/pins`** (full coord set, PR6), **`POST /api/discovery/search/export`** (premium CSV, PR7). **`_resolve(req)`** = the shared parse→merge→evaluate path; `_pin_lookup`, `_hydrate_window`, `ResultRow`/`PinPoint`/`Coverage` models, `FREE_ROW_CAP`/`MAX_MAP_POINTS`. |

Mounted in `backend/main.py` (router include + `ensure_loaded()` in `@app.on_event("startup")`).

### Frontend — `frontend/src/discovery/`
**Wave 1:** `types.ts` (wire mirrors) · `registryClient.ts` · pure `uiCompiler.ts` /
`topicCompiler.ts` (now also `panelFromCqs`) / `summary.ts` · `searchClient.ts` (now `runPins`/
`exportCsv`) · `chips.tsx` (INV-4) · `DiscoveryFilterPanel.tsx` / `DiscoveryResults.tsx` /
`DiscoveryPage.tsx` · `communityAreas.ts`.
**Wave 2 additions:** `coverage.ts` (coverage/populatedFields selectors, safe defaults) ·
`CoverageBanner.tsx` · `DiscoveryMap.tsx` (deck.gl, colorBy upside/land_use, view-only when
free) · `upsideColor.ts` (upside ramp + no-data swatch + land-use ramp/legends) ·
`RecipeShelf.tsx`. Wire calls `discoverySearch`/`discoverySearchPins`/`discoveryExportCsv`/
`fetchDiscoveryRegistry` in `lib/api.ts`. Vitest setup (`src/test-setup.ts` inits i18n) in
`vitest.config.ts`; **48 tests**.

---

## Decisions made during implementation (not fully pinned by 00–09)

These are the judgment calls. Each is mechanical/deterministic and was chosen to keep the
invariants literally true. **Revisit here first** if behavior surprises you later.

1. **29 filters, not 30.** The six categories in `03` sum to 4+6+5+4+5+5 = **29**. (An early
   plan said 30 — arithmetic slip. The registry matches the spec table.)

2. **`flag` × missing value.** Reconciles `03`'s flag row ("value=false → absent/false") with
   `unknownPolicy`: a *genuinely missing* field follows `unknownPolicy` (default `exclude` →
   dropped, both polarities); a *present* field uses polarity (`true`↔truthy, `false`↔falsy).
   In practice the app's flag fields default to `False` (not `None`), so `value=false` matches
   them via the present-falsy path. Keeps "apply unknownPolicy uniformly, no other branching"
   literally true. *To flip to table-literal (value=false always matches missing): one branch
   in `predicates.py`.*

3. **Inverted range (`min>max`) × missing.** A *present* value never matches (R6); a *missing*
   value follows `unknownPolicy`. Inverted ranges are **valid** predicates (kept by merge),
   honestly unsatisfiable.

4. **`satisfies` takes `field` explicitly.** Doc `09`'s shorthand
   `satisfies(pred, parcel, unknownPolicy)` omits the attribute name, which enum/range/flag
   structurally need. Signature is `satisfies(predicate, parcel, field, unknown_policy)`; the
   `region` kind ignores `field` and uses `Parcel.in_region`.

5. **`evaluate` purity vs. parcel data.** Kept the exact 2-arg `evaluate(cqs, data_version)`
   (INV checklist) by reading the immutable snapshot bound to `data_version` from
   `parcel.default_source` — a content-addressed registry, not mutable global/clock/RNG. This
   is the sanctioned "parcel collection bound to dataVersion" (05).

6. **Canonical form sorts OR-set arrays.** `canonical_key` sorts `enum.values` /
   `region.regions` / `scope.regions` so order-insensitive sets compare equal (a safe superset
   of `02`'s "sorted object keys"; makes equality + caching semantic).

7. **`region` excluded from D4 `excludedUnknown`.** Region membership is a computed
   determination, never a NULL scalar, so it can't be "dropped solely for a missing field."
   Only exclude-policy `enum`/`range`/`flag` filters contribute. D4 also **reads parcels
   directly** (via the shared `satisfies`/`within_scope`) because the black-box evaluator
   can't reveal *which* candidates miss a field — this is the one diagnostics piece that
   inspects parcels; it does not re-implement filtering.

8. **`diagnostics.build` signature extras.** Beyond `09`'s shorthand it accepts `result=`
   (pass the already-computed `OrderedResult` to avoid a redundant eval) and `dropped=` (the
   merge's `DroppedInvalid` list, since D3 is produced upstream). `mostRestrictive` uses the
   black-box `evaluate(CQS \ f)` only when `resultCount == 0`.

9. **`merge` guards + `topic_id`.** Beyond R1 validity drops, merge also drops **unknown
   filter ids** and **predicate/registry kind mismatches** (R2), recording each. It accepts
   `topic_id` (telemetry → `meta.topicId`); it never re-expands topics (cleared-field rule).
   `density_band` without `zoning_group` is dropped + recorded.

10. **Text compiler is an intentionally small, unambiguous seed.** Rule/grammar-based, never
    the LLM (would break INV-2). Lexicon choices: `vacant`/`vacancy` → the **vacancy flag**
    (not `land_use=vacant`); `zoning_group` only via a **"zoned X"** qualifier (bare
    "residential" is ambiguous → residual); range grammar covers year_built / units / lot_size
    (sqft-qualified). Everything unmatched → `meta.textResidual` (never constrains). Lexicon is
    plain data, extensible without touching the evaluator.

### Index decisions
11. **Scope = MVP + free byproducts.** Populated: land_use/vacancy (class code), lot/building
    size, year_built, units (Characteristics), assessed value (Assessments), last sale +
    recency (Sales), price/sf + improvement_ratio (computed), TIF/EZ flags (local
    point-in-polygon), zoning_group + density/FAR (zoning polygons + `zoning_definitions`),
    `neighborhood:<ca>` region. **Deferred (stay NULL → `unknownPolicy=exclude`, honest):**
    opportunity_zone, ward, overlay/adu/aro, floodplain, brownfield, transit_proximity,
    open_violations/f311_redflags/crime_index, sbif_nof. Follows the strategy doc's locked
    rollout (MVP six first).
12. **Storage:** dedicated SQLite `discovery_index.db` under `settings.data_dir`
    (`ingestion/data/`, gitignored), separate from `chicago.db`; PIN-keyed **incremental
    upsert**; `meta` row carries the `data_version` (`idx-<date>-<ts>-<n>p`).
13. **`IndexedParcel`:** static region handles precomputed into the row; `radius:<lat>,<lon>,
    <mi>` resolved by haversine **at query time** (matches `02` RegionRef: static precomputed,
    radius dynamic).
14. **Bounded + graceful.** Builder is bounded by community area (`--community-areas 24`) so
    it's runnable/testable; `--all` scales to ~1.8M. A transient layer/spine failure **warns +
    continues** (does not abort a 77-CA run).

### Frontend decisions
15. **Premium-gated** (matches `ExplorePage`; strategy framing as the paid competitive
    feature). Confirmed with Jack.
16. **List-first results.** The frozen wire `result = {pins, total}` has **no coordinates**, so
    results render as a PIN list → Scorecard handoff (`/scorecard?pin=` with dashes stripped).
    **Map markers deferred** — they need a versioned `result.rows` (pin+lat/lon) extension.
    Confirmed with Jack.
17. **One-tap re-issue folds the evaluated CQS back into the panel.** Removing a chip /
    relaxing a `mostRestrictive` filter rebuilds `panelState` from `response.cqs.filters` minus
    that id (and clears `text`), so **text-derived** chips are handled correctly and the panel
    stays the single source of `userFilters` (cleared-field rule). Every result the user sees
    is a plain search of some envelope (evaluator never auto-relaxes).
18. **Tooling:** added vitest (esbuild **automatic** JSX runtime in `vitest.config.ts`; the
    `@vitejs/plugin-react` path left the classic runtime expecting React in scope). Test files
    excluded from `tsconfig.app.json` so the prod build never depends on test-only type deps.

19. **API mounted at `/api/discovery/*`, not `/discovery/*`** (caught at first deploy). The
    spec (03/07) wrote `/discovery/registry` + `/discovery/search`, but the production nginx
    only proxies `/api/`, `/chat`, `/health`, `/autocomplete`, `/section/` to the backend — so
    `/discovery/*` fell through to the SPA fallback (returned `index.html`, not JSON) and never
    reached FastAPI. The bare `/discovery` route is also the **frontend page**, so the `/api`
    prefix avoids that collision too. Fixed: router prefix + `api.ts` URLs + spec docs now use
    `/api/discovery/*`. Lesson: **put new endpoints under `/api/`** (or add an nginx `location`
    in both `nginx.conf` + `nginx.prod.conf`), and verify a deploy by asserting the response is
    **JSON**, not just HTTP 200 (a 200 can be the SPA fallback).

---

## What remains

The frontend + wire are **feature-complete and dark**. The launch gate is now entirely about
**data + de-dormancy**, in this order (all blocked by the 2026-06-13 Socrata 503 outage):

**PR-INDEX (blocked) — build the prod index so there's anything to show.**
The offline builder (`index_build.py`) must compute + write the Wave-2 derived fields and the
`meta` that drives coverage/populatedFields. Specifically it needs to:
- Populate the MVP fields (land_use/vacancy, lot/building size, year_built, units, assessed
  value, sale + recency, price/sf, improvement_ratio, TIF/EZ, zoning_group + density, the
  `neighborhood:<ca>` region) **plus `transit_proximity`** (promoted into MVP — cheap station
  haversine, needed by recipe `vacant_mf_transit`).
- Compute the **3 derived fields** the registry now exposes: `value_percentile` (percentile of
  $/sqft within community-area × land_use; precise basis/min-N rules in the conversation
  record), `upside_score` (0.6·FAR-headroom + 0.4·land-share, 0–100), `is_teardown_candidate`
  (improvement_ratio ≤ 0.25). All offline, deterministic, a `data_version` bump — **no evaluator
  change** (the point of the registry/index split).
- Write `meta.populated_fields` = the filter ids actually populated, and the `community_areas`
  set (drives `coverage`). Until then `read_meta` → None → coverage "none" + empty
  populatedFields (the safe dormant default).
- Run on prod: SSH `178.105.184.66` (`/opt/urbanlayer`), `python -m
  backend.discovery.index_build --community-areas 24` (or `--all`), restart backend so
  `ensure_loaded()` picks it up.

**PR-VAL (blocked, code can be written now) — validate the derived metrics before they sort.**
Non-blocking telemetry harnesses (warn, never refuse to publish fresh parcel data): for
`value_percentile`, assert min-N≥30 peer sets + monotonic percentile→$/sqft + plausible
p10/p50/p90 vs known comps; for `upside_score`, label-vs-AUC against actual redevelopment
outcomes derived from demolition + new-construction permits (`buildings.py`). The 0.6/0.4
weighting is a v1 heuristic to tune from that label set (a `data_version` recompute, no code).

**PR-LIVE (blocked on the above) — de-dormancy.** Nav-link Discovery in `PageHeader`; the
coverage banner flips from "being prepared" to "live in West Town"; recipes/filters light up as
their fields populate. The free teaser becomes meaningful (real totals behind the wall).

**Smaller follow-ups (not launch-blocking):**
- Continuous **slider** control + `aria-valuetext` (non-preset ranges keep min/max boxes today).
- **Whole-page i18n** (only PR9 teaser/export strings are keyed).
- Memoize `_pin_lookup` before the full-city index.
- Saved searches; the remaining deferred index fields (OZ tracts, ward polygons, overlay/adu/aro
  layers, floodplain, brownfield, the per-PIN rollups open_violations/f311/crime, sbif_nof) —
  each a `data_version` bump.

---

## Product direction — Discovery supersedes Explore (decided 2026-06-13)

**Discovery is what the Site Explorer (`/explore`) was meant to be.** Its 29-filter CQS engine
is a strict superset of Explore's two filters (`land_use` ⊃ class, `neighborhood` ⊃ community
area). The intent: Discovery converges with and **eventually retires Explore.**

**Wave 2 closed the map gap.** Discovery now has the deck.gl map (`DiscoveryMap.tsx`, reusing
Explore's `ScatterplotLayer` + `useMapboxOverlay`) fed by `/search/pins`, so it is now a strict
superset of Explore (filters ⊃ Explore's two, **plus** a map, plus recipes/export/teaser). The
only thing left before Explore is redundant is **real data**.

Updated sequence: ✅ (map + `result.rows`/`/search/pins` built, Wave 2) → **build the prod
index (PR-INDEX)** → nav-link Discovery (PR-LIVE) → **redirect/retire `/explore`** (drop the
page + `/api/explore*` once nothing references them). Don't delete Explore before Discovery has
real data — it's the only working parcel-browser until the index lands.

---

## Verification quick-reference
```bash
# backend
source .venv/bin/activate
python -m pytest backend/tests/test_discovery_*.py -q          # 166 tests
python -m pytest backend/tests/ -q -m "not integration"       # 782 unit (the 8 full-suite
                                                              # failures are live-API only)
# frontend
cd frontend && npx tsc --noEmit && npm test                    # 48 vitest

# live wire (backend running on :8001) — registry now carries coverage + populatedFields
curl -s localhost:8001/api/discovery/registry | jq '.version, (.filters|length), .coverage, .populatedFields'
# search returns rows + gated; pins returns the full coord set; export is premium-only (403 free)
curl -s -X POST localhost:8001/api/discovery/search -H 'content-type: application/json' \
  -d '{"userFilters":{"tif":{"kind":"flag","value":true}},"text":"vacant"}' \
  | jq '.result.total, .result.gated, (.result.rows|length), (.cqs.filters|keys)'
curl -s -X POST localhost:8001/api/discovery/search/pins -H 'content-type: application/json' \
  -d '{}' | jq '.total, .truncated, (.points|length)'
```
