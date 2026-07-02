# Data Expansion Candidates (2026-07-02)

Survey of available-but-unintegrated data, ranked by customer value. All probed live
2026-07-02 (sample rows + join keys verified unless noted). Companion to
`2026-07-02_lot-info-robustness-plan.md` — items 1–2 directly feed that arc.

## Tier 0 — already on disk, just not surfaced (zero new sources)

1. **Per-PIN tax exemptions** — `ptaxsim.db` `pin` table carries `exe_homeowner`,
   `exe_senior`, `exe_freeze`, `exe_longtime_homeowner`, `exe_disabled`, vet columns, `exe_abate`.
   Customer story: "current bill reflects a senior freeze — expect a jump at sale."
   That's a buyer-decision fact the Scorecard/report can state deterministically. Effort S.
2. **Parcel polygons for every PIN10** — `ptaxsim.db` `pin_geometry` (26.8M rows,
   pin10×year through 2024, WKT `POLYGON`). Land area computable offline (project to
   EPSG:3435, shapely `.area`) → **simplifies robustness-plan Phase 2** (no GIS bulk pull
   needed for geometry-derived land_sqft; GIS `LandSqft` becomes cross-check, not source).
   Also restores the report envelope map + parcel outline without Cook GIS. Effort S–M.
3. **Derived from sources we already query**: wrecking/demolition permits (existing
   permits dataset, `permit_type` filter) = teardown-activity signal; "water in basement"
   311 codes = block-level flood-risk proxy. Effort S each.

## Tier 1 — high value, new datasets (all free, same two Socrata portals)

4. **Assessment appeals, both stages** — Assessor Appeals `y282-6ig3` (pin, year,
   mailed vs certified values, change, reason) + Board of Review Appeal Decision History
   `7pny-nedm` (pin, tax_year, assessor vs BOR values, `result`, lat/lon). Story: "this
   parcel (and N neighbors) appealed; median reduction X%" → direct dollars, strong $25-report
   content, and a post-purchase upsell hook. Effort M (two PIN-keyed joins, standard pattern).
5. **Ward + alderman** — Boundaries Wards 2023- `p293-wvbd` (polygon preload, like community
   areas) + Ward Offices `htai-wnw4` (alderman name/contact). Aldermanic prerogative makes
   this table-stakes context for any rezoning/variance/PD conversation. Effort S.
6. **Tax delinquency / tax sales** — Treasurer Annual Tax Sale `55ju-2fs9` (pin, year,
   amounts, `sold_at_sale`) + Scavenger Sale `ydgz-vkrp`. Distress flag on the parcel
   (title risk for buyers; leads for investors; Discovery filter candidate). Verify year
   coverage before wiring. Effort S–M.
7. **City-Owned Land Inventory** — `aksk-kvfp` (address, CA, acquisition/disposition dates,
   application status/URL/deadline). "The lot next door is city-owned and applications are
   open" (ChiBlockBuilder). Discovery recipe potential. Effort S.

## Tier 2 — medium value

8. **Building Code Scofflaw List** — `crg5-4zyp` (+ `rz4d-qp2m` current). Landlord-risk
   flag per address. Effort S.
9. **Chicago Energy Benchmarking** — `xq83-jr8c`: `gross_floor_area_buildings_sq_ft`
   (another bldg-sqft source for ≥50k-sqft buildings), energy star score, GHG intensity,
   lat/lon. CRE opex signal + sqft cross-check. Effort S–M.
10. **Short-term-rental eligibility** — House Share Prohibited Buildings `7bzs-jsyj` +
    Restricted Residential Zone Precincts `8eww-pamb`. Investor-relevant yes/no per address.
    Effort S.
11. **Traffic counts** — `gc7y-n4xa` is LIVE (latest timestamp 2026-07-01), segment-based
    ADT with coords. Retail/site-selection context; needs nearest-segment matching. Effort M.
12. **CPS school quality** — School Progress Reports SY2425 `twrw-chuq` + locations/
    boundaries. Residential-buyer lens. Effort M (boundary join).
13. **CHRS orange/red-rated buildings** — `ty7a-2bxt` returns **403 via API (asset-restricted)**;
    the survey is static (1996) → one-time manual KML/shapefile download committed as a local
    artifact. Value: orange/red rating triggers the 90-day demolition hold — real teardown-risk
    fact the zoning card should state. Effort M (manual fetch + point-in-polygon).
14. **Divvy stations** — `bbyy-e7gq`. Mobility amenity chip. Effort S.
15. **Liquor moratorium districts** — all variants labeled "Historical" on the portal;
    verify currency before use (tavern/packaged-goods feasibility). Effort S if a current
    source exists.
16. **Assessor Permits** — `6yjf-dfxs` (county-side permit history per PIN; complements the
    city permits feed, catches unincorporated-style records + assessor sqft-change notes). Effort S.

## Confirmed NOT available (extends the existing "not accessible" list)

- **City ZBA variance decisions** — no structured dataset on the city portal (catalog
  search returns nothing); agendas are PDF-only. (County ZBA `75xd-xajz` is unincorporated
  Cook — irrelevant to Chicago parcels.)
- Ownership names, PD applications, Clerk recordings — unchanged from data-sources.md.

## Suggested sequencing

Tier 0 items ride the robustness arc (exemptions land naturally with Phase 0 tax work;
pin_geometry replaces the Phase 2 GIS pull). Tier 1 items 4–5 are the highest
standalone wins (appeals = money story, ward = table-stakes context). Everything else
is opportunistic per-surface (Discovery filters, report sections) after the arc.
