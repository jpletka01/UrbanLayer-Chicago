# Calculation-correctness audit + remediation (2026-07-06) — SHIPPED (`main` 04d2234..91cd301)

External-style audit of every number the app computes (tax, zoning standards, comps/land value, verdict,
report synthesis, stats), verified against sources — including diffing the hand-typed zoning table against
the **ingested ordinance text already in the repo**. Five fix commits, 1,057 BE + 171 FE tests green,
prod-verified live.

**What was wrong (headline items):** `zoning_definitions.py` carried fabricated values presented as Title-17
standards — RM-4.5/5.5 heights wrong, RM-6/6.5 and all M districts given numeric caps the ordinance doesn't
have, R-district "lot coverage 50–60%" that appears nowhere in Title 17 — and the cache builder's
"authoritative merge" stamped them **high confidence** into the committed artifact. The report's "implied
land value" divided *improved*-sale prices by land sqft; effective tax rate mixed a 2024 bill with a 2025
AV (the same-year `av_clerk` was fetched and discarded); AV preferred pre-appeal `mailed` over `board`;
the verdict could read a built condo tower as "vacant_or_teardown" (unit sqft ÷ whole-lot land); MoM trends
were computed over row-capped fetches; the class-aware tax fix (62fe4cc) left "high tax" thresholds
calibrated for the old wrong rates, flagging every commercial parcel.

**Design decisions worth keeping:**
- **Table authority is applied on every cache READ** (`apply_table_authority` in `zoning_extract.py`), not
  only at build time — `config_version` fingerprints extraction inputs, not the reference table, so
  build-time-only application let table corrections silently desync from the committed cache.
- **`test_zoning_ordinance_parity.py`** parses the bulk tables from `ingestion/data/sections/` and diffs
  both `ZONE_CLASS_DATA` and the served cache — hand-typed reference data is regression-tested against the
  machine-readable source in the same repo, forever.
- Honesty conventions: undefined percentage (prior=0) renders "new", never "+100%"; unknown building sqft is
  a third state, never "LAND"; land value only from confirmed vacant-land comps or not at all; disclosed
  radii/"n=" must match what was actually queried/counted.
- `min_lot_area_per_unit` now covers B/C + D dash tables (verified from corpus) → unit yield beyond R.

**Reusable lessons:** (1) a deterministic "authoritative" merge *launders* upstream errors into high
confidence — put authority at serve time and test it against source; (2) when a displayed number is fixed
(class-aware rates), re-audit every **threshold** calibrated against the old wrong values; (3) `.replace(year=…)`
is a leap-day crash; (4) tallies over `$limit`-capped, date-ordered rows are not area totals — aggregate
server-side. Full narrative: About page → audit section / git messages on the five commits. Historical marker.
