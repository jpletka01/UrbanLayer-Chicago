# Profile latency: local-2026-11-07-tif-cache

- When: 2026-11-07T19:04:06+00:00 · host: Darwin arm64, py3.11.9 (MacBook Pro, home network) · git 627bdb7
- Mode: in-process · rounds: 3 · measured runs: 12 (n per mode = parcels x rounds)

| Parcel | Query | Why | cold p50 | warm p50 |
|---|---|---|---|---|
| downtown | 233 S Wacker Dr | budget: downtown tower (DX, many PINs) | 26.41 s | 39 ms |
| fresh_west | 3300 W Armitage Ave | fresh: Logan Square mixed street | 33.55 s | 432 ms |

**Whole response:** cold p50 33.05 s / p95 35.89 s (n=6); warm p50 39 ms / p95 497 ms (n=6).
First Profile after process start (round 0, not in the percentiles): 37.79 s.
If only `first_content` were awaited (resolution, zoning, property.parcel_by_pin, property.parcel_by_point, property.geometry): cold p50 2.55 s / p95 11.89 s; warm p50 17 ms / p95 20 ms.
If only `overview` were awaited (resolution, zoning, property.parcel_by_pin, property.parcel_by_point, property.geometry, property.characteristics, property.assessments, property.sales, property.tax, property.building_facts, regulatory.overlays, neighborhood.walkscore, block_face): cold p50 15.78 s / p95 27.35 s; warm p50 20 ms / p95 23 ms.
If only `overview_unblocked` were awaited (resolution, zoning, property.parcel_by_pin, property.parcel_by_point, property.geometry, property.characteristics, property.assessments, property.sales, property.tax, regulatory.overlays, neighborhood.walkscore): cold p50 3.92 s / p95 13.75 s; warm p50 20 ms / p95 23 ms.

**Critical path** (the fetch task that finished last): cold {'property': 3, 'incentives': 2, 'crime_yoy': 1}; warm {'property': 6}.

| Task | cold p50 | cold p95 | cold max | warm p50 | warm p95 | queue wait p95 (cold) | failed |
|---|---|---|---|---|---|---|---|
| resolution | 436 ms | 2.10 s | 2.10 s | 0 ms | 0 ms | – |  |
| property | 14.18 s | 25.30 s | 25.30 s | 20 ms | 23 ms | – |  |
| regulatory | 2.21 s | 2.49 s | 2.49 s | 13 ms | 15 ms | – |  |
| zoning | 578 ms | 2.09 s | 2.09 s | 0 ms | 0 ms | – |  |
| incentives | 16.05 s | 28.41 s | 28.41 s | 10 ms | 12 ms | – |  |
| neighborhood | 7.31 s | 16.02 s | 16.02 s | 6 ms | 6 ms | – |  |
| aro_housing | 1.59 s | 15.32 s | 15.32 s | 0 ms | 0 ms | – |  |
| crime | 8.89 s | 16.26 s | 16.26 s | 0 ms | 0 ms | – |  |
| crime_yoy | 6.51 s | 20.90 s | 20.90 s | 0 ms | 0 ms | – |  |
| violations | 5.99 s | 19.15 s | 19.15 s | 0 ms | 0 ms | 580 ms |  |
| address_311 | 4.99 s | 15.89 s | 15.89 s | 0 ms | 0 ms | 2.31 s |  |
| assemble | 1 ms | 1 ms | 1 ms | 0 ms | 0 ms | – |  |
| comparables.sales | 4.95 s | 7.58 s | 7.58 s | 0 ms | 0 ms | – |  |
| comparables.far | 2.17 s | 2.55 s | 2.55 s | 6 ms | 10 ms | – |  |
| identity.address_round_trip | 372 ms | 424 ms | 424 ms | 375 ms | 436 ms | – |  |
| upcoming_zoning | 11 ms | 18 ms | 18 ms | 7 ms | 18 ms | – |  |
| candidates.wait | 0 ms | 0 ms | 0 ms | 0 ms | 0 ms | – |  |
| provenance | 2 ms | 2 ms | 2 ms | 1 ms | 3 ms | – |  |
| upcoming_zoning.text_impacts | 2 ms | 2 ms | 2 ms | 1 ms | 2 ms | – |  |
| serialize | 2 ms | 2 ms | 2 ms | 2 ms | 2 ms | – |  |
| &nbsp;&nbsp;candidates.address_points | 375 ms | 1.42 s | 1.42 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;candidates.assessor | 1.39 s | 2.94 s | 2.94 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;incentives.ez | 0 ms | 0 ms | 0 ms | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;incentives.financials | 4.69 s | 10.17 s | 10.17 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;incentives.fund_analysis | 1.39 s | 12.18 s | 12.18 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;incentives.grants | 5.95 s | 22.01 s | 22.01 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;incentives.nmtc | 917 ms | 1.58 s | 1.58 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;incentives.oz | 1.07 s | 1.21 s | 1.21 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;incentives.qct | 344 ms | 1.59 s | 1.59 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;incentives.tif | 0 ms | 0 ms | 0 ms | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;incentives.tract | 1.37 s | 1.63 s | 1.63 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;neighborhood.census_tract | 2.35 s | 2.44 s | 2.44 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;neighborhood.divvy | 7.30 s | 15.45 s | 15.45 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;neighborhood.stations | 0 ms | 0 ms | 0 ms | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;neighborhood.tod | 1.97 s | 2.35 s | 2.35 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;neighborhood.traffic | 2.12 s | 10.31 s | 10.31 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;neighborhood.walkscore | 1.64 s | 2.55 s | 2.55 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.appeals | 1.96 s | 3.99 s | 3.99 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.assessments | 1.42 s | 1.87 s | 1.87 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.assessor_permits | 1.62 s | 1.74 s | 1.74 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.building_facts | 1.43 s | 8.62 s | 8.62 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.building_facts.commercial | 1.43 s | 1.55 s | 1.55 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.building_facts.condo | 413 ms | 1.42 s | 1.42 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.building_facts.energy | 443 ms | 8.62 s | 8.62 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.building_facts.footprint | 1.37 s | 6.17 s | 6.17 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.characteristics | 383 ms | 476 ms | 476 ms | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.flags | 7.25 s | 12.33 s | 12.33 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.geometry | 9 ms | 10 ms | 10 ms | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.parcel_by_pin | 1.42 s | 1.76 s | 1.76 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.parcel_by_point | 9.60 s | 9.76 s | 9.76 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.sales | 1.54 s | 1.97 s | 1.97 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;property.tax | 9 ms | 10 ms | 10 ms | 3 ms | 3 ms | – |  |
| &nbsp;&nbsp;regulatory.brownfield | 1.38 s | 1.57 s | 1.57 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;regulatory.flood | 1.27 s | 1.46 s | 1.46 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;regulatory.overlays | 2.19 s | 2.47 s | 2.47 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;resolution.address_points | 369 ms | 436 ms | 436 ms | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;resolution.assessor_addresses | 367 ms | 386 ms | 386 ms | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;resolution.geocode | 1.34 s | 1.34 s | 1.34 s | 0 ms | 0 ms | – |  |
| &nbsp;&nbsp;socrata.22u3-xenr | 5.99 s | 19.15 s | 19.15 s | – | – | – |  |
| &nbsp;&nbsp;socrata.3723-97qp | 1.73 s | 2.94 s | 2.94 s | – | – | – |  |
| &nbsp;&nbsp;socrata.3r7i-mrz4 | 413 ms | 1.42 s | 1.42 s | – | – | – |  |
| &nbsp;&nbsp;socrata.55ju-2fs9 | 1.63 s | 2.95 s | 2.95 s | – | – | – |  |
| &nbsp;&nbsp;socrata.6yjf-dfxs | 1.62 s | 1.74 s | 1.74 s | – | – | – |  |
| &nbsp;&nbsp;socrata.72uz-ikdv | 4.69 s | 10.17 s | 10.17 s | – | – | – |  |
| &nbsp;&nbsp;socrata.78yw-iddh | 1.10 s | 1.85 s | 1.85 s | 375 ms | 436 ms | – |  |
| &nbsp;&nbsp;socrata.7bzs-jsyj | 1.64 s | 12.33 s | 12.33 s | – | – | – |  |
| &nbsp;&nbsp;socrata.7pny-nedm | 3.41 s | 5.62 s | 5.62 s | – | – | – |  |
| &nbsp;&nbsp;socrata.aksk-kvfp | 1.64 s | 7.80 s | 7.80 s | – | – | – |  |
| &nbsp;&nbsp;socrata.bbyy-e7gq | 7.30 s | 15.45 s | 15.45 s | – | – | – |  |
| &nbsp;&nbsp;socrata.crg5-4zyp | 1.41 s | 4.15 s | 4.15 s | – | – | – |  |
| &nbsp;&nbsp;socrata.csik-bsws | 1.43 s | 1.55 s | 1.55 s | – | – | – |  |
| &nbsp;&nbsp;socrata.etqr-sz5x | 1.81 s | 21.50 s | 21.50 s | – | – | – | 1 |
| &nbsp;&nbsp;socrata.gc7y-n4xa | 2.12 s | 10.31 s | 10.31 s | – | – | – |  |
| &nbsp;&nbsp;socrata.ijzp-q8t2 | 24.52 s | 64.40 s | 64.40 s | – | – | – |  |
| &nbsp;&nbsp;socrata.j7ew-b73u | 2.06 s | 8.98 s | 8.98 s | – | – | – |  |
| &nbsp;&nbsp;socrata.pabr-t5kh | 3.78 s | 4.06 s | 4.06 s | – | – | – |  |
| &nbsp;&nbsp;socrata.qm7s-3ctt | 1.39 s | 12.18 s | 12.18 s | – | – | – |  |
| &nbsp;&nbsp;socrata.rym7-49n8 | 1.64 s | 3.79 s | 3.79 s | – | – | – |  |
| &nbsp;&nbsp;socrata.s6ha-ppgi | 1.59 s | 15.32 s | 15.32 s | – | – | – |  |
| &nbsp;&nbsp;socrata.syp8-uezg | 1.37 s | 6.17 s | 6.17 s | – | – | – |  |
| &nbsp;&nbsp;socrata.uzyt-m557 | 1.42 s | 1.87 s | 1.87 s | – | – | – |  |
| &nbsp;&nbsp;socrata.v6vf-nfxy | 4.99 s | 15.89 s | 15.89 s | – | – | – |  |
| &nbsp;&nbsp;socrata.wvhk-k5uv | 2.86 s | 3.26 s | 3.26 s | – | – | – |  |
| &nbsp;&nbsp;socrata.x54s-btds | 2.69 s | 5.57 s | 5.57 s | – | – | – |  |
| &nbsp;&nbsp;socrata.xq83-jr8c | 443 ms | 8.62 s | 8.62 s | – | – | – |  |
| &nbsp;&nbsp;socrata.y282-6ig3 | 1.66 s | 1.92 s | 1.92 s | – | – | – |  |
| &nbsp;&nbsp;socrata.ydgz-vkrp | 1.69 s | 1.95 s | 1.95 s | – | – | – |  |
