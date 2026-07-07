# Data & Calculation Integrity Audit — 2026-07-07

Full-pipeline audit of every fact/figure the Property Profile asserts, on `feat/property-profile`
(includes all of main + the new v2 backend: `area_stats.py`, `/api/parcel-map`, `zoning_polygons_near`).
Empirical basis: a fresh `eval/lot_coverage.py` run over the fixed 100-address panel (results in this
session's scratchpad; compare `eval/lot_coverage_report.md` 2026-07-03 baseline) + live spot-verification
of profile figures against CCAO Socrata datasets and the local ptaxsim DB + live probes of candidate
data sources.

## Verified correct (spot-checked against sources)

- **Identity**: 97/100 authoritative resolution; the 3 misses trace to *corrupt source rows* in Address
  Points (one Pilsen building whose rows carry a 15-digit PIN and no coordinates) — the pipeline degraded
  honestly (PIN withheld, `nearest_parcel_unverified=true`).
- **Assessed value** (642 W Belden, `14331030110000`): matches `uzyt-m557` board values exactly, including
  the 2024 appeal reduction (mailed 135,000 → board 114,600 — we correctly show 114,600). Valueless
  in-progress 2026 row correctly excluded from history.
- **Tax bill**: 23,024.01 matches ptaxsim `pin.tax_bill_total` to the cent; effective rate is same-year
  (`av_clerk`): 23,024.01 ÷ (114,600/0.10) = 2.01% ✓.
- **Class-aware level** (4520 N Clark, class 517): level 0.25, eff rate 5.15% ✓ — the 2026-07-06 fixes hold.
- **Zoning standards**: `test_zoning_ordinance_parity.py` + zone-definition contract tests green.
- **Retrieval consistency**: 0 fetch errors, 0 transient misses across 100 addresses (first-hit ==
  persistent coverage on every field); p50 2.6s / p90 5.0s.

## Correctness defects found

### D1 — Corrupt Address Points PINs pass through as authoritative identity (LIVE, reproduced)
`address_to_pin()` (`retrieval/property/address_points.py`) normalizes PINs with
`.replace("-","").zfill(14)` but never validates **exactly 14 digits**. Address Points has 7 Chicago rows
with malformed PINs; two have coordinates, so the path completes:
`/api/scorecard?address=1620 N Orchard St` → `resolved_pin: "01433314059000"` (left-padded 13-digit →
nonexistent township 01) with `resolved_confidence: "authoritative"`, while `property.pin14` is the real
`14333140590000`. Violates INV-1 (one PIN per artifact); the hero "PIN↗" county link points at a
nonexistent parcel. Also reachable at 841 W Lawrence Ave.
**Fix**: reject non-14-digit PINs in `address_to_pin` (fall through to step 3.5/4); add an INV-1 guard in
`/api/scorecard` — when confidence is `authoritative` but `property.pin14` disagrees with `resolved_pin`,
reconcile or downgrade instead of shipping two identities.

### D2 — Address Points query has no municipality filter
`address_to_pin`'s `$where` matches number+direction+street across **all of Cook County**. Suburban rows
collide with Chicago addresses (e.g. "1401 W 19th St" matches Maywood/Berwyn parcels too): today that
causes false multi-matches (→ lost authoritative resolutions); worse, an address present *only* in a
suburb resolves to a unique **suburban parcel** asserted as authoritative. **Fix**: add
`inc_muni='Chicago'` to the `$where` (the column is confirmed live).

### D3 — KPI "area median AV/ft²" benchmark is statistically broken (new v2 code)
Three compounding problems with `area_stats.py` + the ScorecardPage assessed-tile benchmark:
1. **~4% sample**: the Discovery index's `land_sqft` predates the ptaxsim-geometry land source, so the
   Uptown median rests on 189 of 4,905 parcels (nearly all residential) while the endpoint reports
   `n_parcels: 4905` and discloses no per-stat n.
2. **Cross-class inversion**: AV/ft² is not assessment-level-normalized. Live example: class-517 subject
   shows $25.3/ft² vs median $21.8/ft² ("above median") — in market-value terms it's ~$101/ft² vs the
   residential median's ~$217/ft², i.e. *under half*. The comparison inverts the truth for any
   commercial/industrial subject.
3. **Condo junk**: a unit's AV ÷ whole-lot land_sqft reads as far "below median".
**Fix (pick one)**: normalize per-parcel to MV/ft² (AV ÷ class assessment level — index has `class`) and
benchmark subject MV/ft² against it; or benchmark only within the subject's class group (`by_land_use`
already exists but is starved by the same land_sqft sparsity). Either way: emit per-stat `n`, have the FE
suppress the line below a floor (e.g. n<50), and suppress for condo classes / unit PINs. Longer-term:
rebuild the index with geometry land (`data_version` bump) — also benefits Discovery filters.

### D4 — Minor: failure caching in new endpoints
`/api/parcel-map` caches an all-None payload for 1h after a transient ArcGIS failure (maps blank for an
hour); `area_stats` caches `{}` for 24h if the index scan fails once. Cache failures briefly (or not at
all) and only cache payloads with ≥1 non-empty layer.

### D5 — Hardcoded `EFF_RATE_PER_ASSESSMENT_LEVEL = 0.21` (ScorecardPage.tsx)
The "typical for this class" line = level × 0.21 (≈ level × equalizer 3.0163 × ~7% composite rate).
Currently right for the 2024 city vintage; it drifts with equalizer/levy each year and nothing derives or
tests it. Document the derivation + revisit annually, or derive the city-median composite from ptaxsim.

## Completeness: what's commonly missing and how to close it

Benchmark (persistent coverage, 100-address panel — unchanged from 2026-07-03 baseline except
comparables 84→90%):

| Field | Coverage | Where it's missing | Closable? |
|---|---|---|---|
| year_built | **47%** | 58% of commercial, 91% multifamily, 72% exempt, 100% industrial | **YES — biggest win.** CCAO Commercial Valuation (`csik-bsws`), which `get_commercial_building_sqft` already queries, carries `yearbuilt` (+ `tot_units`, bedroom-mix cols) that we ignore. Live probe over the panel's misses: **38/53 recoverable** (→ ~85%+). Same fill-only merge + `commercial_valuation` provenance as bldgsf. |
| units | **20%** | 100% of commercial/multifamily/exempt | Partially — same dataset's `tot_units` recovers **13/80**, incl. every class-318 multifamily probed. ⚠️ economic-unit semantics: keypin rows describe the whole unit (623 **and** 625 W Madison both report Presidential Towers' 2,346 units) — only fill when the economic unit is a single PIN, or label it "economic-unit total". |
| stories | **46%** | 62% commercial, 91% multifamily | `csik-bsws.stories` is only ~6% populated — no. Building Footprints has stories >0 on 52% of 820k rows, but our `within_circle(…, 25m)` around the *Parcel Universe centroid* returns nothing on large parcels (probed: 0 hits at 25m for most misses; correct values appear at 60m — but 60m grabs neighbors on 7.6m lots). **Fix: match footprints by point-in-parcel-polygon** using the ptaxsim geometry we already fetch (`parcel_geometry.py`), falling back to the 25m circle when no polygon. |
| bldg_sqft | 88% | 61% of exempt (schools/churches — outside all assessor datasets) | Only via estimate: footprint polygon area × stories, labeled as an estimate — a product decision, not a bug fix. Otherwise honest absence. |
| sales_history | 76% | 67% exempt (rarely trade), ~17-19% commercial/residential | Mostly legitimately absent (no recorded arm's-length sale in the dataset window). Eval-semantics improvement, not a data gap. |
| zoning_far | 98.9% | the single miss is POS-3 (open space) — Title 17 defines no FAR for POS | Add POS/T to the eval's expected-absent rule (PD/PMD already are); UI could say "no FAR standard for open-space districts". |
| identity | 97% | corrupt Address Points rows (see D1) | D1+D2 fixes, **plus flip `assessor_address_resolution_enabled=True`** — step 3.5 is implemented, live-verified 2026-06-22, blocked only on the ~10-PIN spot-check noted in known-issues. |

## Prioritized remediation plan

1. **P0 — D1 PIN-shape validation + INV-1 guard** (small, kills a live wrong-identity assertion).
2. **P0 — D2 `inc_muni='Chicago'` filter** (one line, prevents wrong-city resolution).
3. **P1 — Commercial Valuation `yearbuilt`/`tot_units` merge** in `building_facts.py` (year_built 47→~85%,
   units 20→33%; the panel's #1 and #3 gaps). Extend `get_commercial_building_sqft` → `get_commercial_facts`
   returning {sqft, year_built, units}; same latest-year/economic-unit handling; fill-only with provenance.
4. **P1 — D3 KPI benchmark fix** (it ships user-visible inverted conclusions on the flagship new surface).
5. **P2 — Footprint point-in-parcel matching** (stories 46→~60-70%, some exempt bldg facts).
6. **P2 — Enable assessor address resolution** after the 10-PIN spot-check.
7. **P3 — D4 failure-caching, D5 constant derivation/doc, eval expected-absent for POS/T, index land
   rebuild** (data_version bump; also unblocks a real per-class benchmark).

Gate every wave with `eval/lot_coverage.py` (persistent coverage must not regress; year_built/units must
move as predicted) + the zoning parity and property test suites.

## Implemented same day (2026-07-07, second session — on `feat/property-profile`)

- **P0 D1**: 14-digit PIN validation in `address_to_pin` AND `assessor_address_to_pin` (never repair by
  padding); INV-1 guard in `/api/scorecard` (authoritative `resolved_pin` ≠ `property.pin14` ⇒
  `nearest_parcel_unverified`, fires on condo-stack pins absent from Parcel Universe, e.g. 7141 N Kedzie).
  1620 N Orchard live-verified: corrupt-PIN-as-authoritative fixed → now resolves authoritative via step 3.5.
- **P0 D2**: `inc_muni='Chicago'` (78yw-iddh) + `prop_address_city_name='CHICAGO'` (3723-97qp) scoping.
- **P2 assessor resolution ENABLED** (`assessor_address_resolution_enabled=True`) after geometric
  validation: 20 recovered PINs vs Census-geocode + ptaxsim parcel polygon; measured geocoder noise floor
  (p50 35m / p90 71m vs authoritative AP coords) explains every "fail" ≤85m; the 150–380m cases are one
  multi-parcel industrial campus with self-consistent county geometry. Zero wrong-parcel mappings. The
  per-year query now prefers the newest year with rows (hard `year=` missed 1425 N Wells, whose parcel was
  RETIRED after 2001 — redeveloped into the 1429 N Wells condos; it stays approximate honestly, and the
  Parcel Universe centroid requirement is the retired-PIN gate). In a random assessor-address sample,
  33/81 were Address Points misses and step 3.5 recovered ~80% of the tested ones — the AP-drawn eval
  panel structurally can't see this gain (it samples only AP-covered addresses).
- **P1 commercial facts**: `get_commercial_building_sqft` → `get_commercial_facts` (+`yearbuilt` from the
  principal building, +`tot_units` for single-PIN economic units only), merged with provenance
  `commercial_valuation` + new `units_source`; FE shows the source hint on Units.
- **P2 footprint point-in-parcel**: `get_footprint_facts` takes the ptaxsim `parcel_geojson`; footprints
  count only if their representative point is INSIDE the parcel (no neighbor grabs, no distance cap
  misses); legacy 25m circle only when no polygon exists. Recovered stories/year on large/exempt parcels
  (3101 W Touhy: 6 stories/1979; 5 S Austin: 3 stories).
- **Preset swap**: homepage example "1425 N Wells St" (permanently unconfirmable — retired parcel) →
  "1550 N Wells St" (authoritative, full facts) in en/es locales + chat suggestions.
- Gates: 1,074 backend tests green, 171 vitest green, `npm run build` green. **Final panel run
  (committed to `eval/lot_coverage_report.md`): year_built 47→88%, stories 46→69%, units 20→31%,
  bldg_sqft steady 88%** (the first cut of `get_commercial_facts` pinned every field to one latest
  vintage and LOST sqft on six class-318s whose newest year has NULL bldgsf — fixed with per-FIELD
  newest-year selection + regression test). Remaining year_built/bldg_sqft misses are almost entirely
  the exempt tail (schools/churches outside every assessor dataset). `comparables` wobbles 80–90%
  across runs (live sales data), unrelated to this work.

**D3 + D4 implemented (same day, follow-up commit)**: area-stats medians are now MARKET-VALUE per
land ft² (AV ÷ class assessment level; exempt excluded) with per-stat `n` (`n_assessed`,
`n_mv_psf`); the FE compares the subject's server-derived `implied_market_value`/land ft² against
it, suppresses under `MIN_BENCHMARK_N=50` and for condo units (299/399), and the tile copy/tooltips
say "market value" (key renamed `avBenchmark`→`mvBenchmark`, en+es). Verified live: Uptown median
$217.5/ft² at n=189 disclosed; the class-517 subject now reads ~$101/ft² vs $218 — direction
corrected. D4: `/api/parcel-map` caches only payloads with ≥1 non-empty layer; a failed area-stats
scan caches for 5 min instead of 24 h.

**Discovery-index land fill implemented (same day, third commit)**: `index_build.py` fills
`land_sqft` from ptaxsim `pin_geometry_raw` polygons (base parcels only — suffix-0000 — so condo
units never claim the whole lot). Validation rebuild of CA 3: parcels with AV+land 189 → 2,721;
per-land-use medians became viable (residential/commercial/multi_family/vacant). Prod picks it up
via one off-box `--refresh` (ptaxsim.db is on the same volume) or the monthly timer post-deploy.

**Still open from the plan**: D5 eff-rate constant derivation/doc, POS/T eval expected-absent,
exempt bldg_sqft estimate decision; nicety unlocked by the land fill — benchmark against the
subject's own land-use median (`by_land_use` now has real n) instead of the all-class median.
