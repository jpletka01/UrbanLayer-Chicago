# Lot-info robustness arc (2026-07-03) — SHIPPED (`main` 9b97444..936c912)

Benchmark → root causes → 7 fix waves, prod-verified. The frozen-panel coverage benchmark (`eval/lot_coverage.py`)
is the arc's **ongoing regression gate**. Four root causes: **prod served ZERO tax data since launch** (ptaxsim.db
never seeded); sqft/year-built residential-only; `char_ncu`/`char_apts` column bugs; silent zoning failures.
Before→after: land 21→100%, bldg 20→85–88%, zoning_far 83→98.9%, prod tax 0→100%.

**Design decisions worth keeping:** ptaxsim `pin_geometry` as an **on-demand** land-area source (no offline
builder); **fill-only merge with per-field provenance**; distress ≠ current (historic signals labeled as such);
EAV-not-dollars exemptions. New fact families: exemptions, appeals + nearby BOR stats, ward/alderman, distress/
opportunity flags. Seeding runbook is the **living** `guides/ptaxsim-prod-seeding.md`; current lot-fact behavior is
on the About page → **Lot Facts & Provenance**. **Deploy lesson:** a committed data artifact needs all three of
`.gitignore` + `.dockerignore` allowlist + Dockerfile `COPY` (all three bit). Historical marker.
