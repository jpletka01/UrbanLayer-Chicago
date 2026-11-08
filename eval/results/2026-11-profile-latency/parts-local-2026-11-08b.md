# Profile in parts: parts-local-2026-11-08b

- When: 2026-11-08T11:33:38+00:00 · host: Darwin arm64, py3.11.9 · git c43f864
- Mode: parts in-process · rounds: 5 · measured visits: 110
- Parcels: twoflat, milwaukee, downtown, pin1, fresh_south, fresh_west, fresh_north, p4_uptown, p4_westtown, p4_woodlawn, p4_bridgeport

## cold

| | n | p50 | p95 | max |
|---|---|---|---|---|
| first screen | 55 | 3.58 s | 10.11 s | 12.15 s |
| Overview, exact parcels | 45 | 4.13 s | 10.73 s | 19.98 s |
| Overview, approximate parcels | 10 | 16.68 s | 17.47 s | 17.47 s |
| whole Profile (every part) | 55 | 41.50 s | 66.03 s | 70.72 s |
| part activity (own time) | 55 | 34.59 s | 49.91 s | 51.49 s |
| part activity (from visit start) | 55 | 40.37 s | 66.03 s | 70.72 s |
| part block_face (own time) | 5 | 29.93 s | 39.50 s | 39.50 s |
| part block_face (from visit start) | 5 | 34.36 s | 43.93 s | 43.93 s |
| part building (own time) | 40 | 11.36 s | 20.05 s | 20.07 s |
| part building (from visit start) | 40 | 20.05 s | 33.66 s | 37.53 s |
| part history (own time) | 55 | 12.28 s | 20.07 s | 20.29 s |
| part history (from visit start) | 55 | 17.67 s | 36.19 s | 40.04 s |
| part incentives (own time) | 55 | 15.32 s | 20.07 s | 20.28 s |
| part incentives (from visit start) | 55 | 22.52 s | 37.01 s | 40.05 s |
| part money (own time) | 55 | 3.20 s | 11.82 s | 17.68 s |
| part money (from visit start) | 55 | 7.87 s | 26.86 s | 34.23 s |
| part neighborhood (own time) | 55 | 14.33 s | 24.93 s | 29.67 s |
| part neighborhood (from visit start) | 55 | 20.07 s | 43.09 s | 46.63 s |

Sources past the late deadline: {'incentives': 18, 'address_311': 13, 'crime': 7, 'neighborhood': 7, 'property': 5, 'crime_yoy': 5, 'property_history': 5, 'aro_housing': 2} (of 55 visits). Failed parts: none.

## warm

| | n | p50 | p95 | max |
|---|---|---|---|---|
| first screen | 55 | 18 ms | 1.54 s | 2.46 s |
| Overview, exact parcels | 45 | 31 ms | 1.56 s | 2.47 s |
| Overview, approximate parcels | 10 | 1.71 s | 7.37 s | 7.37 s |
| whole Profile (every part) | 55 | 2.60 s | 20.06 s | 20.10 s |
| part activity (own time) | 55 | 503 ms | 20.02 s | 20.05 s |
| part activity (from visit start) | 55 | 2.21 s | 20.04 s | 20.08 s |
| part block_face (own time) | 5 | 445 ms | 543 ms | 543 ms |
| part block_face (from visit start) | 5 | 476 ms | 566 ms | 566 ms |
| part building (own time) | 40 | 469 ms | 8.47 s | 20.07 s |
| part building (from visit start) | 40 | 514 ms | 8.84 s | 20.10 s |
| part history (own time) | 55 | 246 ms | 540 ms | 711 ms |
| part history (from visit start) | 55 | 518 ms | 2.70 s | 7.85 s |
| part incentives (own time) | 55 | 252 ms | 2.45 s | 20.07 s |
| part incentives (from visit start) | 55 | 520 ms | 7.86 s | 20.10 s |
| part money (own time) | 55 | 247 ms | 534 ms | 737 ms |
| part money (from visit start) | 55 | 516 ms | 2.69 s | 7.85 s |
| part neighborhood (own time) | 55 | 393 ms | 8.52 s | 12.27 s |
| part neighborhood (from visit start) | 55 | 535 ms | 8.55 s | 13.69 s |

Sources past the late deadline: {'address_311': 2, 'property': 1, 'incentives': 1, 'crime_yoy': 1} (of 55 visits). Failed parts: none.

First visit after process start (round 0, not in the percentiles): Overview 4.24 s, whole Profile 30.81 s.
