# Lot-Info Robustness Plan (2026-07-02)

**Companion to** `claude-context/audits/2026-07-02_lot-coverage-benchmark.md` (findings).
Goal of the arc: the lot facts customers pay for (sqft, tax, zoning envelope, building
basics) are present, provenance-labeled, and honestly caveated when truly absent —
measured by `eval/lot_coverage.py` against the frozen panel after every phase.

## Feasibility verdict

Everything is fixable to a strong level, and **no paid/new vendors are needed** — every
missing fact has a verified free source on portals we already integrate (Cook County
Socrata, Chicago Socrata, Cook GIS used *offline*). Verified 2026-07-02 by live probes:

| Gap (from benchmark) | Source that closes it | Verified evidence |
|---|---|---|
| tax bill/rate = 0% on prod | ptaxsim.db we already have (never seeded on prod) | prod returns None; local 100% |
| land_sqft 0% non-residential | Cook GIS layer 44 `LandSqft` — populated for ALL classes | 741 W 79Th (class 517) → LandSqft 7501; layer supportsPagination, maxRecordCount 2000 → bulk-snapshotable |
| bldg_sqft commercial (5xx) | `csik-bsws` Assessor Commercial Valuation `bldgsf`, keyed by `keypin` (+`pins` fan-out) | 30,165/32,930 Chicago 2024 rows have bldgsf (~92%) |
| bldg_sqft/year_built/land for condos | `3r7i-mrz4` Residential Condominium Unit Characteristics (`char_building_sf`, `char_land_sf`, `char_yrblt`) | probed, populated |
| stories/year_built/bldg_sqft everything else | `syp8-uezg` Chicago Building Footprints (`stories`, `year_built`, `bldg_sq_fo`, `no_of_unit`) | probed, populated |
| stories/units ~0% everywhere | code bug — wrong x54s-btds columns | `char_ncu` = commercial-unit count, not stories; `char_apts` is categorical |
| zoning first-hit misses | code bug — `lookup_zoning` swallows failures | 4/100 recovered on retry, never hit `partial_failures` |

**Residual, not fully fixable (accept + present honestly):**
- Building facts for some exempt/institutional parcels (no CCAO valuation row, patchy
  footprints) — expect ~10–20% residual on those classes → needs a "no building on
  record" terminal state, distinct from "data unavailable".
- `pin_resolved` 97% — bounded by Address Points coverage (new construction); already
  degrades to flagged-approximate by design.
- Sales/comparables sparsity for exempt/industrial — market reality; messaging fix only.
- Footprints freshness varies (city updates irregularly) — provenance labels cover this.

## Architecture decision

One new **offline-built parcel-facts snapshot** (SQLite on the `backend/data` volume,
PIN14-keyed), merging GIS LandSqft + commercial valuation + condo chars + footprints with
**per-field provenance**, refreshed monthly off-box. This is the third instance of the
proven pattern (zoning_cache, discovery_index): flaky/slow live source → precomputed
artifact → live path reads locally, live APIs demoted to freshness fallback. It both
fills the non-residential holes *and* removes the flaky Cook GIS call from the live path.

Merge precedence per field: CCAO chars (x54s) → commercial valuation (csik) → condo
chars (3r7i) → footprints (syp8) → GIS attrs; record which source won.

## Phases

**Phase 0 — Ship tax data to prod (ops, ~1 hr, zero code risk).**
Check disk headroom on the box (9.4 GB + ~1 GB compressed during download), run
`scripts/download_ptaxsim.py` server-side onto the `backend/data` volume, verify via
live `/api/scorecard` (tax_breakdown populated). Add a loud signal: `/health` gains a
`ptaxsim` flag + startup log so a missing DB can never be silent again. Optional
hardening: scorecard-level effective-rate fallback labeled "estimated" (the report
already has `report_fallback_tax_rate`) so the tax row is never all-or-nothing.
*Needs Jack (prod access + deploy confirmation).*

**Phase 1 — Quick code fixes (~1 day).**
(a) Stop mapping `char_ncu`→stories / raw `char_apts`→units; decode `char_apts`
categories to counts (verify CCAO codebook values first), derive residential stories
from `char_type_resd`, leave None over wrong. (b) `lookup_zoning` failure →
`partial_failures` (and audit the same swallow-pattern in siblings) so the UI caveats
a failed lookup instead of rendering absence. (c) PD parcels: render "Planned
Development — standards set by ordinance" + ordinance link instead of a blank FAR.
Regression tests for all three.

**Phase 2 — Parcel-facts snapshot: land_sqft (~2–3 days).**
Offline builder (paged GIS layer-44 pull, Chicago PIN prefixes ≈ 950k parcels ≈ ~475
pages, resumable with retry/backoff, run off-box like the discovery builder) → snapshot
artifact; merge condo `char_land_sf`. Property orchestrator reads the snapshot for
land/bldg sqft; live GIS becomes fallback-only. Monthly refresh timer alongside
discovery `--refresh`. Target: land_sqft 21% → ≥95%.

**Phase 3 — Building facts for non-residential (~2–3 days).**
Join commercial valuation (`keypin` fan-out over `pins`, latest city vintage), condo
chars, and footprints (address-points or spatial join) into the snapshot. Target:
bldg_sqft 20% → ~75–85%, year_built similar, stories 1% → ~70%; residual becomes the
explicit "no building on record" state.

**Phase 4 — Honest degradation + measurement loop.**
UI distinguishes "no building on record" vs "data unavailable" (from provenance).
Re-run `eval.lot_coverage` after each phase (and against prod post-deploy — the panel
is ~200 polite requests); keep results as the longitudinal record. Tighten the
verify-pass retry trigger to critical fields (currently any raw miss → retries ~all).

## Sequencing rationale

Phase 0 first: biggest customer-visible win, zero code. Phase 1 next: small diffs,
kills the "wrong number" class (worse than missing). Phases 2–3 are the structural
work and reuse each other's builder. Measurement (Phase 4) brackets everything —
the benchmark is the regression gate for the arc.
