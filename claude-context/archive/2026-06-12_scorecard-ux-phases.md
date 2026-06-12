# Scorecard UX Overhaul (Phases 1–4 from the 2026-06-12 UX Audit)

**Completed**: 2026-06-12
**Status**: Shipped to production (`e00ba93..88e9bf4`, deploy verified live via API ~3 min after push)

## What Was Built

A four-phase improvement pass over `/scorecard`, driven by a full production UX audit (screenshot-verified against local + prod). The page went from "data inventory with a warning badge on top" to: map thumbnail + confident identity strip + facts-only verdict line + zoning envelope on the free tier + balanced grid + an inspectable sample report behind the $25 CTA.

## Implementation Details

**Phase 1 — Trust & quality (`e8e1677`)**
- Pin-keyed entries showed **"Unknown Address" beside "✓ Exact parcel match"**. Root cause: Parcel Universe (`pabr-t5kh`) has **no address column**; the PIN branch of `_resolve_location` selected only `lat,lon`. Fix: new `pin_to_address()` in `retrieval/property/address_points.py` — reverse lookup on Address Points (`78yw-iddh`, `cmpaddabrv` column, `$order=addrnocom` for determinism), display-only, runs in parallel with the coordinate query, never mutates fallback semantics (locked by tests). Bonus: the PDF report header inherited the fix on pin-only requests.
- Confidence badges i18n'd + tooltip explanations; softer copy ("Area data — exact parcel not confirmed").
- Bare "—" hero metrics → muted "n/a" + explanation tooltip; assessor placeholder zeroes (Stories: 0, "/ 0H") suppressed.
- Crime YoY rows show prior-year base ("209 vs 54 +287%"); `humanizeShoutyCase()` added to `lib/format.ts` (acronym/run-aware ALL-CAPS re-casing).
- RegulatoryCard de-dupe (overlay name/description dropped when restating layer type; STATUS pills that mirror listed overlays removed).
- Sticky report bar no longer covers the last card (`pb-24`); logo unified to `/logo.jpg` on Scorecard/Explore/Pricing; subtitle dropped internal "no AI cost" phrasing; CTA card stacks on mobile.

**Phase 2 — Information hierarchy (`ca67852`)**
- Long tails behind expanders: Incentives recent grant projects, ARO nearby-projects list, census-tract detail section (it restated area stats), age-distribution chart no longer defaultOpen. Summary totals stay visible.
- Neighborhood (deepest card) moved last in the grid — killed the ~1,300px dead zones from row-height mismatch.
- One investigate ask per card (Incentives picks TIF question when in a TIF; Regulatory merges overlays+flood); links muted-with-accent-hover so **solid accent = purchase only**; raw lat/lon line removed.
- Page height 3,129 → 2,507px desktop with no data removed.

**Phase 3 — Synthesis, all deterministic (`20108bd`)**
- `/api/scorecard` returns `zone_definition`: `zoning_definitions.py` (Title-17 table, previously report-only) via `dataclasses.asdict`. Contract test: `test_zone_definition_contract.py`. Fallback chain exact → PD/PMD → prefix → unknown verified live (C1-2 full standards, PD 447 advisory).
- Page-local **ZoningCard** after Comparables: name, max FAR, max height, lot coverage, uses, code section, zoning-map link, report teaser.
- **Facts-only verdict line** under the address (zone name · TIF · OZ · TOD · ADU · ARO · flood) — every clause restates a flag already rendered below; computed client-side; no scoring by design.
- **Mapbox Static Images thumbnail** in the identity band (dark-v11, accent pin). Pin-only by design (parcel polygons depend on flaky county GIS); lazy, hidden on failure.

**Phase 4 — Conversion (`88e9bf4`)**
- Real-data sample report for 642 W Belden (`14331030110000`) at `frontend/public/sample-report.pdf` + first-page thumbnail (`sips`-rendered) beside the purchase CTA; "View a sample report" links in CTA (thumbnail + mobile link) and purchase modal.
- CTA bullets rewritten plain-English to actual V5/V6 contents; free/paid **boundary line** ("free page shows the public zoning table — the report computes envelope, tax projection, approval pathway").
- `sample_report_click` event (backend `_VALID_EVENT_NAMES` + 3 placements, verified into the events table).

## Key Decisions

- **Rejected**: letter-grade "scores" (a wrong grade is a liability; verdict stays facts-only), question-based card *merging* (shared sidebar components, high regression surface — reorder+collapse got most of the value), live GL map thumbnail (static image suffices).
- **Masonry: initially rejected, then adopted as CSS multicol** (`967d283`, same day). The collapse pass shrank card-height variance but the 2-col grid still row-snapped, leaving gaps Jack flagged on the live page. Final layout: `columns-1 md:columns-2` + `break-inside-avoid mb-4` per card block — columns flow independently, reading order is column-major (Property→Comps→Zoning→Incentives left; Regulatory→Violations→Crime→311→Neighborhood right). Known trade-off: expanding a section can reflow a card across columns.
- Coordinates for pin resolution stay Parcel Universe (truth-model §5 / INV-2); Address Points is display-only.
- The free zoning table deliberately shows *published* Title-17 values; the report keeps interpretation (envelope math, setbacks, parking, approval pathway). Validate in Phase-2 interviews whether the free table cannibalizes purchases.

## Post-Ship Watch Items

- `investigate_click` volume on the admin dashboard — links were consolidated ~11 → ~8 and muted; success criterion: no >40% drop.
- `sample_report_click` → `report_cta_click` → purchase funnel as the conversion baseline for Phase-2 customer interviews.

## Files Changed

Backend: `main.py` (`_resolve_location` backfill, `zone_definition`, event allowlist), `retrieval/property/address_points.py` (+`pin_to_address`, `_format_display_address`), tests (`test_address_points.py`, `test_resolve_location.py`, +`test_zone_definition_contract.py`).
Frontend: `ScorecardPage.tsx` (major), `ReportCTACard.tsx`, `ReportPurchasePrompt.tsx`, `InvestigateButton.tsx`, `ExplorePage.tsx`, `PricingPage.tsx`, `sidebar/{Property,Comparables,Regulatory,Incentives,Neighborhood}Card.tsx`, `lib/format.ts`, `lib/api.ts`, locales `{en,es}/{pages,data}.json`, `public/sample-report{.pdf,-thumb.png}`.
