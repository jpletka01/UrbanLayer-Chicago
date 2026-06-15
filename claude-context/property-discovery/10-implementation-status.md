# 10 — Implementation Status & Decisions Record

**Status: LIVE ON PRODUCTION (2026-06-14) — three waves; no longer dormant.**
- **Wave 1 (2026-06-13, `f192d57`)** — the invariant core, compilers, evaluator, diagnostics,
  offline index builder, list-first frontend.
- **Wave 2 (2026-06-14, merge `8c279c6`)** — the **result.rows workbench (PR1–PR10)**: the
  goal-first, map-backed prospecting workbench (shipped dark — no index yet).
- **Wave 3 (2026-06-14, merges `78294d8` + `8d3ae07` + `731aca6`)** — **PR-INDEX → live launch.**
  Built the prod index for real, caught + fixed a launch-blocking assessment bug, added
  recipe-count honesty + 3-tier addresses + index persistence + a self-activating nav link +
  follow-ups (perf, PR-VAL, periodic rebuild), then expanded coverage to **25 community areas
  (~482k parcels)**. Full record in the **"Wave 3"** section below.

**LIVE on prod as of 2026-06-14:** `/api/discovery/registry` → coverage `partial`, **25
liveAreas**, 19 `populatedFields`, `recipeCounts` serving; Discovery is **nav-linked** (the PR-LIVE
conditional link self-activated when coverage flipped off "none"). Backend runtime ~1.86 GB with
the 482k-parcel index loaded; box has ~4.4 GB free. Monthly rebuild timer installed (next
2026-07-01). The index persists on the `backend/data` volume across deploys.

This doc records **what was actually built, the decisions made during implementation that were not
fully pinned by the spec (00–09), and what remains.** The spec docs 00–09 stay the normative design.

Tests: backend **190 discovery tests** (full **unit** suite 806, no regressions — only live-API
integration tests fail offline); frontend **51 vitest**; `tsc --noEmit` clean.

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
  *(Done in Wave 3 — see below.)*

---

## Wave 3 — PR-INDEX → live launch (2026-06-14, merges `78294d8` + `8d3ae07` + `731aca6`)

The 2026-06-13 Socrata 503 cleared, so this session built the index for real and took the page from
dormant to LIVE. **This session was the implementer directly** (no separate session). The single
most important working lesson, and the source of every real bug below: **build the index, run it,
and LOOK at the actual output before trusting it. Every launch-blocking bug this session was caught
by eyeballing a real build, not by tests.** Validate locally before prod.

### PR-INDEX — derived fields + the field-readiness manifest (`d89d845`)
`index_build.py` now computes, per parcel:
- `is_teardown_candidate` (flag): building ≤25% of total value (`imp_share ≤ 0.25`) AND a real
  structure (bldg_sqft>0, year_built present); else NULL.
- `upside_score` (0–100): `round(100·(0.6·FAR_headroom + 0.4·land_share))`, NULL kept **DISTINCT
  from a low score** when zoning/sizes/assessment are missing (the map's no-data swatch depends on
  it). **Decision: `land_share` is derived from a clean `land/total`, NOT `1 − improvement_ratio`** —
  the shipped `improvement_ratio` is building-to-land and can exceed 1, which would make `1 − ir`
  negative. The shipped field is left untouched.
- `cta_rail_distance_mi`: nearest CTA rail haversine (stations loaded once from
  `transit_stations.json`, passed into `assemble_parcel` to keep it a pure function).
- `value_percentile` (a cross-parcel **2nd pass**, can't live in per-parcel assembly): SALE-based
  $/sqft percentile within `community_area × land_use`; N≥30 floor → citywide×use fallback → NULL.
  Deterministic (sorted + bisect, no clock/RNG). **Never blocks the publish** — a thin metric just
  nulls and drops out of `populated_fields`. **Decision: assessed-based $/sqft is NEVER pooled in**
  (the round-4 concern) — only sale-based; non-qualifying parcels get NULL, never an assessment
  backfill.
- `meta.populated_fields` is **derived from the attrs actually present** → a NULL-everywhere field
  is auto-omitted → its recipe shows NEEDS-DATA. This manifest is the switch that de-dormants the page.

### The assessment-join bug — the biggest catch, found by local validation (`e3147d5`)
First local build: `total_assessed_value` came back **0% populated**, silently killing
`assessed_value` / `improvement_ratio` / `upside_score` / `is_teardown_candidate` AND the default
`assessed_value asc` sort. Root cause: the builder ordered assessments `year DESC` and grabbed the
**in-progress year (2026)** whose value columns are still null — and **Socrata omits null fields
from JSON**, so the row returned valueless. Fix: AND `(mailed_tot OR certified_tot OR board_tot IS
NOT NULL)` so "latest" means the latest year that actually carries values (`_batch_latest` gained a
`where_extra` arg). **0% → 99%.** ⚠️ **CARRY-FORWARD LESSON: the latest CCAO assessment year is
valueless until mailed. Anything that takes "the latest CCAO assessment" must filter for a present
value — the same trap likely lurks in the scorecard/report assessment path (UNVERIFIED).**

### Recipe-count honesty — killing LIVE-but-empty (`02e5898`)
Field-level `populatedFields` can't tell that a recipe whose FIELDS are populated still returns 0
for its SUBSET: `value_percentile` is populated (by condos), but **0 multifamily had one**, so
`undervalued_mf` badged LIVE and returned nothing — the silent-zero trust failure again. Fix: the
builder evaluates each recipe against the just-built snapshot and writes `meta.recipe_counts`;
`get_registry` injects `recipeCounts`; `RecipeShelf` badge is now **3-state**: "Needs data" (a field
unpopulated) / "No matches yet" (fields ready, subset empty) / "Live · N". Meta schema-evolves via an
ALTER guard so an older index upgrades on the next build.

### Addresses 28% → 99% — what Jack pushed back on twice (`90bf8a8` + `62bbeb3` + `f582831`)
Row-cards are address-first but the index stored neither a street address nor the class code. The
parcels dataset (`pabr-t5kh`) has **no street address**; **Address Points (`78yw-iddh`) has
`cmpaddabrv`** ("1915 N KEDZIE AVE"). A direct PIN join resolved only **28%** (condo unit-PINs have
no address point of their own). Jack rejected 28% as too low for the map. **3-tier resolver
`_address_for`:** own Address Point → **building base PIN** (10-digit prefix + 0000 → recovers
condos → 70%) → **nearest Address Point** via a per-CA shapely `STRtree`, marked approximate with a
`~` prefix and rendered "near 1915 N Kedzie Ave" (recovers vacant lots → **99%**). Vacant lots
matter most for a development tool and their nearest address point is ~30 ft away (adjacent
frontage), so approximate-but-marked beats a bare PIN. Class stored as "2-11". ⚠️ **CARRY-FORWARD
LESSON: a sampled coverage % misleads — a 300-row sample read 74%, the full set was 28%. Measure the
full set AND the subsets that matter (recipe results), not the global number.**

### Index persistence — caught before the first prod build (`8d3ae07`)
The index wrote to `ingestion/data`, which is **not a mounted volume** — a prod-built index would be
wiped on the next image rebuild (every deploy would silently re-dormant the page). Caught by checking
the compose volume config *before* SSH-ing to build. Fix: `settings.discovery_index_path` points the
index at `backend/data` (the persistent `backend_data` volume, alongside `chicago.db`). `--all` will
make this file large — watch disk.

### PR-LIVE — conditional, self-activating nav-link (`fa100da`)
Discovery is added to `PageHeader` nav **only when `coverage.mode != "none"`** (read via the cached
`registryClient`, so it's one shared fetch). Merging the code (dark) + later building the prod index
makes the link appear automatically — no second deploy. While dormant it stays unlinked.

### Follow-ups (`731aca6`)
- **Perf:** `parcel_source.pin_lookup` memoizes the `{pin:parcel}` map per dataVersion (was O(N),
  rebuilt every request) — invalidated when the snapshot changes. Prereq for scale.
- **PR-VAL:** `index_validate.py` — a NON-BLOCKING CLI (`python -m backend.discovery.index_validate`)
  that reports the upside / value_percentile distributions (degeneracy guard) + a DIRECTIONAL
  redev-permit cross-check (do parcels with a recent new-construction/demo permit skew high on
  upside?). Permits join via the **10-digit parcel key** (permits carry 10-digit PINs in `pin_list`,
  the index has 14-digit unit-PINs — same condo-prefix idea as the address fallback). First read:
  upside distribution healthy; cross-check **median 54.7 pctile → weak**. BUT it's confounded +
  pessimistic (a parcel redeveloped a year+ ago now shows its built-out low-upside state, dragging
  the median down). ⚠️ **DECISION: `upside_score` is a PLAUSIBLE v1, NOT validated. The 0.6/0.4
  weighting stays a documented v1 heuristic — deliberately NOT tuned against this noisy signal (that
  would fit noise). Don't oversell upside in UI copy.** A rigorous validation needs pre-redevelopment
  (temporal) state the index doesn't hold.
- **Periodic rebuild:** `index_build --refresh` rebuilds whatever CAs are already in the index (reads
  `meta.community_areas`), so a scheduled rebuild auto-follows coverage with no hardcoded CA list.
  `deploy/discovery-index-rebuild.{service,timer}` (monthly, 1st @ 04:17 UTC) installed on prod; next
  run **2026-07-01**. Install steps in `deploy/README.md`.

### The launch + coverage expansion
Sequence executed: dark-merge Wave-3 code → deploy the persistence fix → **build prod index (5 CAs)**
→ restart → verified live (coverage `partial`, recipe counts **EXACTLY matching local** — no env
drift) → then expanded to **25 CAs (~482k parcels)**. Live `recipeCounts`: teardown 902,
vacant_mf_transit 548, fresh_comps 197, underused_commercial_tif 153, undervalued_mf 31, adu_2flats 0
(honest NEEDS-DATA — `adu_eligible` is deferred).

### ⚠️ Known problems / limitations discovered (carry forward)
- **~~`--all` build OOM~~ → FIXED, and FULL CITY now LIVE (2026-06-15).** The build is memory-safe
  (per-CA ingest + streaming finalize, off-box `run --rm`) and the coupled meta-clobber bug is fixed
  (meta recomputed cumulatively). Part C expanded to **all 77 CAs / 949k parcels at 2.98 GB RSS (39% of
  the box)** via measured batches — the runtime full-index-in-RAM model fit comfortably. **The "~1.8M /
  won't fit" worry was a unit error: that's Cook County WITH suburbs; Chicago = ~949k parcels.** Slope
  ~2.37 KB/parcel. No box bump needed.
- **`undervalued_mf` is structurally thin (~29–31 across 25 CAs) — NOT a bug.** `value_percentile`
  needs a recent (≤36mo) arm's-length sale and multifamily trades slowly: of 9,047 multifamily
  parcels only **108 (~1.2%) sold in 3 years**; a quarter of those is the recipe. Arguably a feature
  (a high-signal small list). The one tuning knob is the 36-month sale window. Sale-comp-free recipes
  (teardown, vacant_mf_transit) are fat by contrast.
- **Characteristics are condo-sparse** — building sizes/year only ~28% in these condo-heavy
  north-side CAs, which gates `upside_score`/teardown coverage (denser in low-rise neighborhoods).
- **`units` is dormant** — `char_apts` is empty across these CAs, so the `units` filter + `adu_2flats`
  recipe stay honest NEEDS-DATA.
- **bbox spillover** — a CA build by bounding box also indexes some neighbor-CA parcels (tagged to
  their true CA), so `coverage.liveAreas` under-claims (safe under-claim). The `data_version` string
  counts pre-dedup rows (cosmetic; e.g. "584602p" for 481,873 unique).

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

The launch is **done** — PR-INDEX, PR-VAL, and PR-LIVE all shipped (Wave 3), and coverage is live
for 25 community areas. What's left is expansion + polish.

**Coverage / scale:**
- ✅ **Build is memory-safe now (2026-06-14, robust refactor).** The OOM was coupled to a meta bug:
  `write_index` held all rows in one process AND clobbered `meta` to the last batch (so coverage
  could only grow by rebuilding everything at once). Refactored: per-CA `_assemble_ca`→`upsert_parcels`
  ingest (peak = one CA) + a streaming `finalize_index` (value_percentile float-maps, chunked
  `evaluate()` recipe counts, stream-union populated_fields) that recomputes meta **cumulatively**
  (CAs unioned). `write_index` is now a thin wrapper. `--community-areas <batch>` correctly *adds*;
  `--all`/`--refresh` are safe at any size. Run **off-box**: `docker compose run --rm --no-deps
  backend python -m backend.discovery.index_build --community-areas <batch>`. Locked by an
  incremental-vs-combined equivalence test + finalize-parity + chunk-invariance tests.
- ✅ **FULL CITYWIDE COVERAGE LIVE (2026-06-15) — all 77 CAs / 948,991 parcels.** Part C ran as
  measured off-box batches (25→37→57→77), restarting + measuring backend RSS after each. The curve was
  dead-linear at **~2.37 KB/parcel**: 25 CA=1.86 GB, 37=2.20, 57=2.49, **77=2.98 GB (39% of the 8 GB
  box)** — a full 2.5 GB under the ≈5.5 GB stop line. Registry now reports **`coverage: "all"`, 77
  liveAreas**; citywide recipe counts: vacant_mf_transit 1418, teardown 1191, fresh_comps 316,
  underused_commercial_tif 226, undervalued_mf 42, adu_2flats 0. ⚠️ **CORRECTION: the old "~1.8M
  parcels / won't fit on 8 GB" assumption was WRONG — that was Cook County INCLUDING suburbs. Chicago's
  77 community areas total ~949k parcels (~3.0 GB RSS), comfortable on the box.** The runtime
  full-index-in-RAM model never needed re-architecting and the box never needed a bump. The monthly
  `--refresh` timer (now `run --rm`, off-box) auto-follows all 77 CAs. Expand/rebuild steps in
  `deploy/README.md`.
- ✅ **`/explore` RETIRED (2026-06-14).** Discovery is a strict superset with real data, so `/explore`
  now redirects to `/discovery`; `ExplorePage.tsx`, the `/api/explore*` endpoints, `retrieval/explore.py`,
  the `fetchExplore*` client fns, and the `explore.*` i18n blocks are deleted. The one survivor,
  `_format_pin`, moved to `retrieval/utils.py` as `format_pin` (the Discovery index builder still uses it).
  Nav: Discovery took Explore's old slot (after Scorecard). Verified: backend 807 unit, tsc, 51 vitest.

**Data quality / metrics:**
- **Validate `upside_score` properly** when temporal (pre-redevelopment) data is available — PR-VAL's
  permit cross-check is confounded by post-redevelopment state (median 54.7, weak). Until then 0.6/0.4
  is documented v1; **don't oversell upside in copy.**
- **`undervalued_mf` thinness** is structural (recent-multifamily-sale gating) — if more inventory is
  wanted, the only lever is the 36-month sale window (staler comps). Default stays 36mo.
- **Deferred index fields** (each a `data_version` bump, no evaluator change): OZ tracts, ward
  polygons, overlay/adu/aro layers, floodplain, brownfield, per-PIN rollups
  (open_violations/f311/crime), sbif_nof, and `units` (needs a real unit-count source — `char_apts`
  is empty).

**FE polish (from Wave 2, still open):**
- Continuous **slider** control + `aria-valuetext` (non-preset ranges keep min/max boxes).
- **Whole-page i18n** (only the PR9 teaser/export strings are keyed).
- Saved searches.

**Ops:**
- Monthly rebuild timer is live (next **2026-07-01**); confirm the first automated run succeeds.
- ✅ **Scorecard/report assessment path VERIFIED SAFE (2026-06-14)** — it does NOT hit the CCAO
  valueless-latest-year trap. Unlike the index builder (which grabbed the raw first `year DESC` row),
  `_build_summary` (`retrieval/property/__init__.py`) iterates and takes the first row with a non-null
  total, so the headline value, trend, and tax derivation all correctly skip the in-progress
  valueless year. Confirmed against live `uzyt-m557` data. Locked with a regression test
  (`test_build_summary_skips_valueless_latest_year`) + a guard that drops the phantom valueless
  current-year record from `assessment_history` (it had been polluting the synthesizer context).

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
# tests
source .venv/bin/activate
python -m pytest backend/tests/ -k discovery -q               # 190 discovery
python -m pytest backend/tests/ -q -m "not integration"      # 806 unit (live-API tests fail offline)
cd frontend && npx tsc --noEmit && npm test                   # 51 vitest

# LIVE PROD — registry carries coverage + populatedFields + recipeCounts (GET, no CSRF)
curl -s https://urbanlayerchicago.com/api/discovery/registry \
  | python3 -c "import sys,json;r=json.load(sys.stdin);print(r['coverage'],len(r['populatedFields']),r['recipeCounts'])"
# /search + /search/export are CSRF-protected POSTs → raw curl returns 403 (= backend reached, OK).
# The FE (authFetch w/ CSRF) exercises them.

# Validate a built index (non-blocking; run locally or on prod)
python -m backend.discovery.index_validate                    # upside/value_pctile dist + redev cross-check

# REBUILD / EXPAND COVERAGE ON PROD (ssh root@178.105.184.66)
cd /opt/urbanlayer
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -d backend \
  python -m backend.discovery.index_build --community-areas <set>   # or --refresh (current CAs)
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend   # load it
# monthly auto-rebuild: systemctl status discovery-index-rebuild.timer
```

> **Live as of 2026-06-14:** coverage `partial`, 25 liveAreas, recipeCounts
> {teardown 902, vacant_mf_transit 548, fresh_comps 197, underused_commercial_tif 153,
> undervalued_mf 31, adu_2flats 0}. Index at `backend/data/discovery_index.db` (persistent volume).
