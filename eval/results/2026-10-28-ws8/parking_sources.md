# WS8 Phase 0 slice 4: can surface parking be identified from an official source?

Probed 2026-10-28. Read-only: catalog searches and one aggregate query. No file was downloaded.

## Answer

**Not from anything found. Surface parking stays out of Phase 1.** This is a bounded search, not a proof that
no source exists; the open items below say what would reopen it.

## What was checked

| Source | Result |
|---|---|
| Cook County Assessor class codes (`class` on Parcel Universe and the Discovery index) | Classes name garages (for example 5-01 a garage used with a commercial improvement, 5-22 a one-story public garage) but the April 2018 Assessor definitions list (a secondary copy; the current official list was not read) shows no surface-parking-lot class. So no class was found that separates a lot in use as parking from other vacant or commercial land. |
| Assessor Commercial Valuation (`csik-bsws`), `property_type_use` | A free-text label with spellings such as `parking`, `Parking Garage`, `ParkingGarage`, `Industrial-Truck Parking`; the labels containing "park" total a few dozen rows (the query output was truncated, so the exact count was not taken). It describes valued commercial buildings, not lots, and is far too small to be a coverage source. |
| City of Chicago data portal catalog (queries: parking, off-street parking, surface parking, land use, garage) | Only unrelated datasets: Parking Permit Zones, Winter Overnight Parking Restrictions, City-Owned Land Inventory (city-owned parcels only). No parking-lot or land-use layer. |
| Cook County data catalog (same queries) | No parking or land-use layer. Parcel Universe, Commercial Valuation and the building footprints (2008 archive) are the only parcel-adjacent sets. |
| CMAP Land Use Inventory (2018 and 2020, parcel-based, 57 categories) | The Field Guide's commercial series says parking is part of the parcel's primary use (for example a mall "and associated parking"); the pages read showed no separate parking category. The vacant/construction series (4000) and the classification schema file were not read. |

## What would reopen it

1. CMAP's Land Use Inventory classification schema (a download; needs Jack's permission each time) turning out to carry a parking category for Chicago parcels, and its vintage being recent enough to state.
2. Reading the 4000 series of the CMAP Field Guide.
3. An imagery-derived layer is not an official source under `source-confidence.md` and is out of scope for Phase 0.

## Consequence for the truth contract

A parking lot may appear in this index as `vacant_land` (class 1-00), as `unknown_gfa`, or as a small building on a
mostly paved lot; nothing here distinguishes it. None of these states may be labeled "surface parking". The map's
legend must not use the term in Phase 1.
