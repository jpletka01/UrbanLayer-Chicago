# Lot-Info Robustness Arc — Benchmark, Fixes, New Facts

**Completed**: 2026-07-03
**Status**: Shipped to production (`main` 9b97444..936c912, 8 commits, ff-merge; CI-deployed; prod-verified via live API on 3 parcel archetypes). Prod ptaxsim.db seeded interactively the same night.

## What Was Built

A one-day arc from founder hunch ("lots of addresses seem to be missing tax rate / built sqft") to
measured fix: a **frozen-panel coverage benchmark** (`eval/lot_coverage.py`) that quantified the gaps,
a **root-cause diagnosis** (one deploy gap, one structural data gap, two column-mapping bugs, one
silent-failure bug), and **seven waves of fixes** that took every critical lot fact from ~20–100% to
≥85% (most 100%) on the same 100-address panel — plus four new fact families the product never had
(exemptions, appeals history, ward/alderman, distress/opportunity flags).

## Before → After (same frozen panel, 2026-07-02 morning → 2026-07-03)

| Field | Before | After | Fix |
|---|---:|---:|---|
| tax bill / rate / breakdown (PROD) | **0% since launch** | 100% | ptaxsim.db was never seeded on the box (ops, no code) |
| land_sqft | 21% | **100%** | computed on-demand from ptaxsim `pin_geometry_raw` polygons |
| bldg_sqft | 20% | **85%** | condo chars → commercial valuation → footprints fallback chain |
| year_built | 20% | 47% | condo chars + footprints (no source publishes it for most commercial/EX) |
| stories | 1% | 46% | `char_ncu` bug fix (`char_type_resd` decode) + footprints |
| units | 0% | 20% | `char_apts` word decode + single-family⇒1 |
| zoning_class first-hit | 96% | 100% | failures now RAISE → partial_failures/retry instead of silent blank |
| zoning_far | 83% | 98.9% | PD/PMD = "Set by PD ordinance" + ordinance № (expected-absent, not blank) |
| pin resolution | 97% | 97% | unchanged (bounded by Address Points coverage, by design) |

## The Benchmark (the arc's regression gate — keep running it)

`PYTHONPATH=. python -m eval.lot_coverage --full http://localhost:8001`

- **Frozen panel** `eval/lot_panel.json`: 100 addresses from Cook County Address Points, stratified
  across the 7 Chicago township PIN prefixes, seeded-random 4-digit sub-prefix scatter (seed
  20260702). Committed so runs are longitudinal. **Don't regenerate casually.** Known skew:
  low-PIN-in-bucket sampling over-represents commercial corner lots (48%) — read the by-class
  matrix, not the topline.
- Field checks classify PRESENT / MISSING_PERSISTENT / MISSING_TRANSIENT / EXPECTED_ABSENT.
  Legitimate absences (vacant land → no building; exempt → no tax; PD → no table FAR) are excluded
  from the coverage base — the benchmark measures *gaps*, not *nulls*.
- **Verify pass**: every address with a raw miss is re-fetched once, sequentially. Miss-then-present
  = MISSING_TRANSIENT (retrieval flakiness), giving two numbers per field: **first-hit coverage**
  (one page load) vs **persistent coverage** (best the data supports). This split is what separated
  the silent-ArcGIS-failure bug from true data gaps.
- Results: `eval/lot_coverage_results{,_post}.json` + `_report{,_post}.md` (pre/post committed).

## Root Causes Found (and their fixes)

1. **Deploy gap — prod served zero tax data since launch.** ptaxsim.db is optional-by-design;
   `estimate_tax` degrades to None; nothing surfaced its absence. Fix: seed the DB (runbook
   `guides/ptaxsim-prod-seeding.md`) + `/health` reports `ptaxsim: true|false` (informational,
   non-gating) + startup WARNING. *Seeding gotchas, both hit live:* CCAO's bz2 is **multi-stream**
   (parallel bzip2 — raw `BZ2Decompressor` raises EOFError; `bz2.open` chains streams), and
   `/opt/urbanlayer/backend/data` is the git tree, NOT the container mount — `/app/backend/data`
   is the **named volume `backend_data`**, so the DB must be `docker compose cp`'d in.
2. **Structural data gap — sqft/year-built were residential-only.** The only populated source was
   CCAO x54s-btds (2xx regression classes); the authoritative PIN-keyed parcel path hard-coded
   `bldg_sqft/land_sqft = None`; Parcel Universe has no sqft columns. → geometry + fallback chain
   (below).
3. **Column-mapping bugs** — `stories` read `char_ncu` (= number of COMMERCIAL units) and `units`
   read `char_apts` as an int (the dataset ships **decoded words**: "Two".."Six"; `char_type_resd`
   ships "1 Story"/"1.5 Story"/"2 Story"/"3 Story +"/"Split Level"). Fix: word/label decodes,
   `float` stories (1.5 is real), `char_ncu` surfaced honestly as new `commercial_units`,
   None-over-wrong for Split Level.
4. **Silent zoning failure** — `lookup_zoning` swallowed exceptions and returned None, so a
   transient ArcGIS outage rendered as "no zoning" with no caveat (4/100 first-hit misses).
   Fix: transport/HTTP/ArcGIS-error-body failures now RAISE; every caller already ran it in a
   `gather(return_exceptions=True)` that maps exceptions to the "parcel zoning" partial-failure.
   Only a definitive no-features response is negatively cached.

## Key Design Decisions

- **ptaxsim.db is a parcel-geometry source, not just tax.** `pin_geometry_raw` (WKT per pin10,
  PRIMARY KEY (pin10, start_year) → ~ms indexed lookups through a view) made the planned offline
  GIS bulk-snapshot builder unnecessary: land area is computed **on-demand at request time**
  (`parcel_geometry.py`, cos-latitude planar scaling, no pyproj, ~±0.1%; observed −1.6% vs GIS's
  official LandSqft — vintage + deed-vs-polygon differences). Also restores the parcel outline on
  the PIN path (report envelope map).
- **Fill-only merge with per-field provenance.** Fallbacks never override assessor data. Precedence:
  CCAO chars → condo unit chars (`3r7i-mrz4`) → Commercial Valuation (`csik-bsws`) → footprints
  (`syp8-uezg`) → GIS attrs / geometry. `PropertySummary.{land_sqft,bldg_sqft,year_built,stories}_source`
  carries `assessor|gis|geometry|condo_unit|commercial_valuation|footprint`; the Scorecard renders a
  muted suffix for non-assessor values ("(from parcel geometry)"). Honest > complete.
- **Conditional phase-2 fetches.** Building fallbacks only fire when x54s left gaps (and never for
  vacant 1xx) — residential traffic pays zero extra calls.
- **Commercial valuation semantics**: one row PER BUILDING per keypin per year → **sum the latest
  year**; match `keypin='...' OR pins like '%...%'` (economic units span PINs); the number describes
  the economic unit, provenance says so. ~92% of Chicago 2024 rows carry bldgsf.
- **Condo unit sqft, not building sqft**: the parcel IS the unit; `char_building_sf` deliberately
  not surfaced as the unit's bldg_sqft.
- **Historic ≠ current distress**: Treasurer tax-sale datasets end ~2014 — always rendered WITH the
  years ("appeared in the 2013 annual tax sale (historic)"), never as a bare distress flag.
- **City-owned = current ownership only** (`property_status='Owned by City'`) — the inventory keeps
  disposed rows; a "Sold" parcel flagged as city-owned in live testing before the filter.
- **PD honesty over PD coverage**: PDs have no table FAR by nature; the zoning card states "Set by
  PD ordinance" + ordinance № (from `parcel_zoning.ordinance_num`, already fetched), and the
  benchmark counts PD FAR as expected-absent.
- **Exemptions are EAV deductions, not dollars** — presented as "reduces taxable value", with the
  buyer caveat (owner-occupancy exemptions don't transfer → listed bill understates a buyer's bill).
- **Appeals as a money story**: both stages per PIN + a **neighbor aggregate** (BOR `centroid_geom`
  within_circle 250 m, last 3 tax years, subject PIN excluded) → "107 appeals within a block,
  38 won, median −16.9%".
- **Ward via startup preload** (50 polygons + offices, same pattern as TIF/EZ), pure in-memory PIP
  at request time; surfaces on the Scorecard identity line (aldermanic prerogative context).

## New Fact Families Shipped

`PropertySummary` gained: `commercial_units`, `tax_exemptions` (kind + EAV reduction),
`appeals` (records + nearby stats), `flags` (tax-sale years, city-owned + sales status +
ChiBlockBuilder URL, scofflaw, STR-prohibited), four `*_source` provenance fields;
`NeighborhoodSummary` gained `ward` (number, alderman, phone, email, website).
All flow to chat automatically via ContextObject serialization.

## Gotchas Worth Remembering (beyond the root causes)

- **Socrata URL columns are `{"url": ...}` objects, not strings** — an unnormalized `website` field
  failed WardInfo validation and silently sank the *entire* NeighborhoodSummary (found live).
- Footprints layer: the status column is truncated to `bldg_statu`; `bldg_sq_fo` is mostly 0 —
  stories/year_built are the reliable columns. Rank candidate rows by populated-fact count.
- STR "restricted residential zone" dataset (`8eww-pamb`) has **no geometry** (precinct numbers
  only) — deliberately not flagged.
- **Unit tests + the property orchestrator**: phase-2 lookups touch the network / the real 9.4 GB
  DB. `conftest.py` has an autouse fixture neutralizing them (same class as the documented
  `estimate_tax` gotcha). Without it the suite *appears* to hang.
- **Backgrounded pytest pileup**: ~23 orphaned pytest processes (background runs whose shell
  wrapper was killed but not the python child) made every subsequent run look hung. `pkill -f
  "python -m pytest"` and run one suite at a time; the suite itself takes ~6 s.
- Local ptaxsim.db predates CCAO's re-compression — that's why the multi-stream bug never bit
  locally.

## What Remains (task #14, not archived)

"No building on record" UI state (vs "data unavailable", from provenance); feeding flags/appeals
into the Verdict; appeals/exemptions section in the $25 report (the report path runs
`workflow=development_feasibility`, which skips the history fetches — appeals aren't fetched there);
year_built (47%) and units (20%) have no better public source found; Tier-2 expansion candidates
(energy benchmarking `xq83-jr8c` — also a bldg-sqft cross-check ≥50k sqft, traffic `gc7y-n4xa`
(live!), CPS school quality, CHRS orange/red demolition-risk (API-403; one-time manual KML artifact),
Divvy) — see `strategy/2026-07-02_data-expansion-candidates.md`. Watch prod retrieval latency for a
day (a few more parallel calls per cold parcel on the 4-vCPU box) and re-run the benchmark against
prod: `PYTHONPATH=. python -m eval.lot_coverage --full https://urbanlayerchicago.com`.

## Files

Benchmark: `eval/lot_coverage.py`, `eval/lot_panel.json`, `eval/lot_coverage_results{,_post}.json`.
Backend: `retrieval/property/{parcel_geometry,building_facts,appeals,parcel_flags}.py` (new),
`retrieval/neighborhood/wards.py` (new), `retrieval/property/{__init__,tax_estimate}.py`,
`retrieval/zoning.py`, `models.py`, `main.py` (health/startup), `report_i18n.py`, template.
Frontend: `scorecard/{ScorecardPropertyCard,ScorecardZoningCard}.tsx`, `ScorecardPage.tsx`,
`lib/types.ts`, locales en/es. Docs: `guides/ptaxsim-prod-seeding.md`,
`audits/2026-07-02_lot-coverage-benchmark.md` (findings),
`strategy/2026-07-02_lot-info-robustness-plan.md` (plan),
`strategy/2026-07-02_data-expansion-candidates.md` (survey). Tests: 5 new files; suite 940 + 140 FE.
