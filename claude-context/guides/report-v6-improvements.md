# Report V6 — Open Issues & Future Improvements

Session date: 2026-06-10. Generated from visual QA of the feasibility report for 443 W Wrightwood Ave (mock=true).

## Critical: Parcel Map Needs Real Geometry

**Status:** Blocked on data

The parcel map currently works when Cook County GIS returns polygon geometry, but GIS is intermittently down (known issue). When geometry is unavailable, mock mode fabricates a rectangle centered on the lat/lon — this is **actively misleading** because it doesn't match the actual lot shape, position, or orientation.

**Requirements for a useful lot map:**
- Must have exact vertex coordinates from Cook County GIS or an equivalent source
- Cannot approximate — a fabricated rectangle is worse than no map
- When real geometry is unavailable, show dimensions grid only (no map image)
- The mock override should NOT generate a fake parcel map

**Research needed:**
- Can we cache/pre-fetch parcel geometry for reliability? (GIS goes down for hours)
- Is parcel geometry available from Socrata Parcel Universe (`pabr-t5kh`)? Currently it only returns PIN/class/sqft — check if geometry columns exist
- Cook County GIS MapServer layers — which layer has the most reliable polygon data?
- Fallback: could we construct geometry from legal description + plat records?

## Year Built / Construction Year Not Available for Some PINs

**Status:** Code complete, data gap for some properties

CCAO Characteristics dataset (`x54s-btds`) has `char_yrblt` field. Extraction code is in `property/__init__.py`. For 443 W Wrightwood (PIN 14283190070000), the CCAO API returned a 400 error on the characteristics query, so `year_built` was null and the nonconformity analysis didn't trigger.

**Research needed:**
- Why does CCAO characteristics fail for some PINs? Is this a data issue or query format issue?
- Alternative sources for year built (e.g., City of Chicago building permits historical data)
- For the nonconformity analysis: should we fall back to `bldg_age` when `year_built` is null?

## Property Ownership — No Open Data Source

**Status:** Confirmed limitation, no action possible

Cook County does not expose taxpayer/owner names in bulk data exports (`x54s-btds` or `pabr-t5kh`). The assessor website shows it for individual PINs but uses dynamic rendering. Current "Ownership Intelligence" section (long-term hold, owner-occupied signals from tax exemptions) is the right design given constraints.

**Future options (if productizing):**
- Cook County Recorder of Deeds (no public bulk API)
- Third-party data provider (ATTOM, CoreLogic — paid, licensing)
- Scraping assessor website (fragile, ToS concerns)

## Comps Map — Works But Needs Real Coordinate Validation

**Status:** Code complete, needs real-data testing

`_generate_comps_map()` renders cyan diamond markers for comparable sales. Mock data now includes lat/lon coordinates. For real data, coordinates come from Parcel Universe via `pin_coords` in `nearby_comparable_sales()`. Need to verify that real comps queries return non-zero lat/lon values consistently.

## Items Shipped This Session

All code changes are in `backend/main.py`, `backend/templates/zoning_report.html`, `backend/models.py`, `backend/retrieval/property/__init__.py`, `backend/retrieval/property/sales.py`, `backend/retrieval/three11.py`, `backend/config.py`.

| # | Item | Type | Status |
|---|------|------|--------|
| 1 | Historic district / National Register conflict | Bug fix | Shipped — overlay type labels, National Register row, synthesis/approval/next-steps all updated |
| 2 | Year built + nonconformity analysis | Enhancement | Code shipped, data-dependent (see above) |
| 3 | 311 open-focused display | Enhancement | Shipped — open count leads, total as footnote |
| 4 | Parcel map + dimensions | Enhancement | Dimensions shipped; map needs real geometry (see above) |
| 5 | Construction radius → 0.5mi | Enhancement | Shipped — separate config, zoom 14 basemap |
| 6 | Regulatory overlay boundaries on zoning map | Enhancement | Shipped — dashed boundaries + legend for 7 overlay layers |
| 7 | Property ownership | Data limitation | Confirmed — no open data source for owner names |
| 8a | Transit station detail | Enhancement | Shipped — station names, lines, distances in two locations |
| 8b | Comparable sales map | Enhancement | Shipped — spatial map between chart and table |

## Design Decisions Made

- **Overlay type labels** (`[National Register Districts]`, `[Lakefront Protection District]`, etc.) disambiguate overlay names that sound like status flags
- **311 hierarchy:** open count + types prominent, total count as footnote context
- **Construction radius:** 0.5mi (0.00725 deg) as separate config from comps radius (0.004 deg / 0.25mi)
- **Zoning map overlays:** 7 layers rendered as dashed boundaries (PD, landmark district, historic district, landmark building, national register, special, SSA) with per-type colors
- **Scale bar on parcel map:** 50 ft reference using Mercator projection math
