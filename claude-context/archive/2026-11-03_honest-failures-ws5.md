# Honest failures + WS5 calculators (typical lot, block-face rule)

**Completed**: 2026-11-03
**Status**: Shipped to production (release PR #183, merge `440b448`)

## What Was Built
Wave A: 15 retrieval handlers that returned a checked "no" on failure now raise and cache nothing (TIF, HUD's OZ/QCT/NMTC layers that fail with HTTP 200 and an error body, the FCC tract lookup, Walk Score, Divvy, traffic, the Socrata parcel fallback, EPA brownfields, ARO housing, nearby construction). The orchestrators name each gap (`IncentivesSummary.unchecked`, `data_gaps` → `partial_failures`), so the Profile, chat and report say "Not checked". Opportunity Zones are checked by point (2010-tract designations vs 2020 FCC tracts). Wave B: the typical lot size for the parcel's district in its community area (one zoning-card row, n ≥ 50; empty until the Discovery index carries `zone_class`), and the RS-3 "60% of the block face" rule built from the code's own definition via the City's street centerlines (`pr57-gg9e`), every lot on the face in any district, feeding the same unit yield as the 606 district.

## Key Decisions
Decision Items 65-67 in `decisions/2026-10_build-queue.md`. Reusable lessons: a failed or empty source raises and the orchestrator names the gap (now a Patterns rule in `backend/CLAUDE.md`); ArcGIS reports a failed query as HTTP 200, so check for a feature list; read the code's definition before approximating it (the earlier block-face panel counted only RS-3 lots on a hundred block). Full stories: About page, "Engineering Challenges" → "An error that came back as a success" and "Reading 'block face' the way the code does".

## Open
The typical-lot row waits for the production index rebuild (Jack: the monthly timer). WS8 Phase 2 and WS4 PR5 were not started (HUD's FMR file could not be downloaded by script).
