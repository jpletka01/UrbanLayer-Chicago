# 10 — Implementation Status & Decisions Record

**Status:** Built end-to-end, **not yet deployed.** All of build-plan `08` (steps 1–10) plus
the offline prospecting index (`strategy/property-discovery-filters.md` Part B) and the
frontend are implemented on branch **`feat/discovery-evaluator-core`** (8 commits, **not
pushed** — push = deploy, needs approval). Built 2026-06-13.

This doc records **what was actually built, the decisions made during implementation that
were not fully pinned by the spec (00–09), and what remains.** The spec docs 00–09 stay the
normative design; this is the reality + rationale log for future sessions.

Tests: backend **131 discovery tests** (full backend unit suite 747, no regressions);
frontend **17 tests** (new vitest runner). `tsc --noEmit` clean; production build OK.

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
| `parcel_source.py` | 7/index | Production snapshot seam + current-dataVersion pointer; `ensure_loaded()` loads `discovery_index.db` else empty fallback |
| `api.py` | 7 | `GET /api/discovery/registry`, `POST /api/discovery/search` — wires parse→merge→evaluate→build |

Mounted in `backend/main.py` (router include + `ensure_loaded()` in `@app.on_event("startup")`).

### Frontend — `frontend/src/discovery/`
`types.ts` (wire mirrors) · `registryClient.ts` (cache + staleness) · pure `uiCompiler.ts` /
`topicCompiler.ts` / `summary.ts` · `searchClient.ts` · `chips.tsx` (renders from
`response.cqs`, INV-4) · `DiscoveryFilterPanel.tsx` / `DiscoveryResults.tsx` /
`DiscoveryPage.tsx` · `communityAreas.ts`. Route `/discovery` in `main.tsx`; wire calls
`fetchDiscoveryRegistry`/`discoverySearch` in `lib/api.ts`. Added **vitest + jsdom +
@testing-library/react** (no FE unit runner existed before; `vitest.config.ts`, `npm test`).

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

**Operational (no code):**
- ✅ **Shipped to production 2026-06-13** (merge `a15ce81` + path hotfix `f192d57`; deploy
  verified via live JSON). Feature is LIVE but **dormant**: premium-gated, **not nav-linked**,
  empty-index fallback until an index is built on prod.
- **Run the live index build ON THE PROD SERVER** once the city/county Socrata portals recover
  (they returned **503** across the board on 2026-06-13). SSH to `178.105.184.66`
  (`/opt/urbanlayer`), `python -m backend.discovery.index_build --community-areas 24` (or
  `--all`), restart backend so `ensure_loaded()` picks it up. Until then
  `/api/discovery/search` correctly returns the empty-index fallback (`dataVersion
  discovery-empty-0`, total 0).
- (Optional) add a nav link in `PageHeader` — admin-only while data-less, public once real.

**Deferred features (later index version / PR):**
- **Map markers** for results — requires the versioned `result.rows` coords extension to the
  frozen `SearchResponse` (a reviewed contract change).
- **Index fields:** opportunity_zone (needs OZ tract polygons), ward (ward polygons),
  overlay/adu/aro (overlay layers), floodplain, brownfield, transit_proximity (cheap — station
  distance), and the expensive per-PIN rollups (open_violations, f311_redflags, crime_index),
  sbif_nof. Each is a `data_version` bump + new `meta`, **no evaluator change** (that's the
  point of the registry/index split).
- **Topics:** `registry.topics` is `[]` today; the topic compiler machinery exists. Adding
  topic presets is a registry edit (e.g. a "vacant multifamily incentive" preset).
- **Free-teaser gating** variant; saved searches; the full 77-CA build run.

---

## Product direction — Discovery supersedes Explore (decided 2026-06-13)

**Discovery is what the Site Explorer (`/explore`) was meant to be.** Its 29-filter CQS engine
is a strict superset of Explore's two filters (`land_use` ⊃ class, `neighborhood` ⊃ community
area). The intent: Discovery converges with and **eventually retires Explore.**

The deliberate gap today is the **map** — Discovery is list-first by design while the index
is empty. The plan: once there's real data, add a map to Discovery that **looks like Explore's**
(reuse Explore's deck.gl `ScatterplotLayer` + `useMapboxOverlay` + `classColor` from
`frontend/src/components/ExplorePage.tsx`). That requires the deferred `result.rows`
(pin + lat/lon [+ a few display fields]) extension to `SearchResponse` (a reviewed contract
change, 07). At that point Explore is redundant → **retire `/explore`** (redirect to
`/discovery`, drop the page + `/api/explore*` once nothing references them).

Sequence: (1) build the prod index → real results; (2) `result.rows` coords extension + port
Explore's map into `DiscoveryResults`; (3) nav-link Discovery; (4) redirect/retire Explore.
Until (2), the two coexist on purpose. Don't delete Explore before Discovery has the map +
real data — Explore is the only working parcel-browser in the meantime.

---

## Verification quick-reference
```bash
# backend
source .venv/bin/activate
python -m pytest backend/tests/test_discovery_*.py -q          # 131 tests
# frontend
cd frontend && npx tsc --noEmit && npm test                    # 17 tests
# live wire (backend running on :8001)
curl -s localhost:8001/api/discovery/registry | jq '.version, (.filters|length)'
curl -s -X POST localhost:8001/api/discovery/search -H 'content-type: application/json' \
  -d '{"userFilters":{"tif":{"kind":"flag","value":true}},"text":"vacant"}' | jq '.result.total, (.cqs.filters|keys)'
```
