# Lot-Information Coverage Benchmark — Findings (2026-07-02)

**Context.** Founder hunch: "a large percentage of searched addresses are missing critical
lot information — tax rate, built square footage." Built `eval/lot_coverage.py` (new benchmark)
+ `eval/lot_panel.json` (fixed 100-address panel) and measured. Hunch **confirmed, and
localized to three distinct causes** — a data gap, a code bug, and a deploy gap.
This doc anchors the "lot-info robustness" design arc.

## The benchmark

- `PYTHONPATH=. python -m eval.lot_coverage --full http://localhost:8001`
- Panel: 100 addresses sampled once from Cook County Address Points (78yw-iddh), stratified
  across the 7 Chicago township PIN prefixes, seeded scatter (seed committed) — then frozen in
  `eval/lot_panel.json` so successive runs measure the same parcels over time.
- Exercises the real `/api/scorecard` surface. Each lot fact classifies as
  PRESENT / MISSING_PERSISTENT / MISSING_TRANSIENT / EXPECTED_ABSENT (vacant land → no
  building sqft, exempt → no tax bill = legitimate absences, excluded from the coverage base).
- A sequential **verify pass** re-fetches every address with a raw miss: misses that recover
  on retry are MISSING_TRANSIENT (retrieval flakiness), the rest are true data gaps. This
  yields two numbers per field: **first-hit coverage** (what one page load shows) and
  **persistent coverage** (best the data can support).
- Outputs: `eval/lot_coverage_results.json` (per-address detail) +
  `eval/lot_coverage_report.md` (matrix by field and by property class).

**Panel caveat**: `$order=pin $limit=3` within each 4-digit bucket lands on low lot numbers →
arterial/corner parcels → the panel over-represents commercial (48%) vs the city's true class
mix. The by-class matrix normalizes for this; don't read the topline coverage % as a
user-traffic-weighted number. (Future: randomize within-bucket offsets, or weight by class.)

## Results (local backend, 2026-07-02; 0 fetch errors; p50 1.3s)

| Field | First-hit | Persistent | Where it's missing |
|---|---:|---:|---|
| pin resolution (authoritative + truth-match) | 97% | 97% | matches the R7 audit |
| bldg_class, assessment_history, assessed_value | 100% | 100% | — |
| tax_bill / tax_rate (**local**) | 100% | 100% | **but see prod finding** |
| zoning_class | 96% | **100%** | 4 transient ArcGIS failures |
| zoning_far | 83% | 87% | PDs + zones without a table FAR |
| **land_sqft** | **21%** | **21%** | 100% missing in every non-residential class |
| **bldg_sqft** | **20%** | **20%** | same |
| **year_built** | **20%** | **20%** | same |
| stories | 1% | 1% | see code bug below |
| units | 0% | 0% | no real source |
| sales_history | 76% | 76% | worst for exempt (67% missing) |
| comparables | 86% | 86% | industrial has no peers |

## The three causes

1. **Structural data gap — sqft/year-built are residential-only.** The only populated source
   for land_sqft/bldg_sqft/year_built is CCAO characteristics (`x54s-btds`), which covers
   regression-class residential (2xx) only. The PIN-keyed parcel path
   (`lookup_parcel_by_pin`, i.e. the *good*, authoritative path) **hard-codes
   `bldg_sqft: None, land_sqft: None`**; only the flaky Cook County GIS point-lookup ever
   returns parcel-level sqft (`LandSqft`/`BldgSqft` attrs), and it isn't used when we resolve
   by PIN. Parcel Universe (`pabr-t5kh`) carries no sqft columns. Discovery's index has the
   same residential-only shape. → For ~half the panel (commercial/multifamily/exempt/industrial)
   the paid product shows **no lot size at all** — on parcels where lot size and buildable
   envelope are exactly what the customer is buying.
   Candidate sources for the fix: Cook County GIS parcel layer (has both, flaky — could be
   bulk-snapshotted offline like the zoning cache), parcel polygon area via shapely (land sqft
   geometrically, when geometry is available), CCAO Commercial Valuation dataset (bldg sqft
   for 5xx), Chicago Building Footprints (footprint area + stories + year built).

2. **Deploy gap — prod has no tax data at all.** ptaxsim.db (9.4GB) is optional and must be
   manually seeded into the prod volume (`docker compose cp`, see docker-compose.yml comment);
   it never was. Verified live 2026-07-02: prod scorecard returns
   `estimated_annual_tax=None, tax_code=None, tax_breakdown=[]` for parcels where local
   returns a full bill + 11 agency line-items. **Local benchmark says tax=100%; every prod
   customer sees 0%.** The founder's "missing tax rate" experience was prod truth. Fix is
   ops, not code: seed the DB (+ a startup log/health flag so a missing ptaxsim.db is loud,
   + consider the report's documented 2.1% effective-rate fallback for the scorecard).

3. **Code bug — `stories` reads the wrong column.** `property/__init__.py:_build_summary`
   maps `stories = char_ncu`, but `char_ncu` is *number of commercial units* in x54s-btds;
   the dataset has no stories column (`char_type_resd` encodes 1/2-story categorically).
   Hence stories = 1% coverage even on clean residential. `units = char_apts` is also a
   categorical code, not a count (0% coverage). Both need remapping or a different source.

Also observed: **silent zoning degradation** — `lookup_zoning` swallows exceptions and
returns None, so a failed ArcGIS call never reaches `partial_failures` and the UI can't
caveat it (4/100 first-hit misses were this). Same swallow-pattern likely elsewhere.

## Suggested arc order

1. Seed ptaxsim.db on prod + loud health signal (ops; biggest customer-visible win, zero code risk).
2. Non-residential land_sqft: offline GIS bulk snapshot or polygon-area derivation (mirrors the
   zoning-cache pattern: flaky-live-source → precomputed artifact).
3. bldg_sqft/year_built for 3xx/5xx via Commercial Valuation + Building Footprints join.
4. Fix stories/units mapping.
5. Surface retrieval failures honestly (zoning → partial_failures) so the UI can caveat.
6. Re-run `eval.lot_coverage` after each step — it's the regression gate for the arc.
