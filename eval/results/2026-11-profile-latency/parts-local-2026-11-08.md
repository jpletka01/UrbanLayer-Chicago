# Profile in parts: parts-local-2026-11-08

- When: 2026-11-08T09:00:00+00:00 · host: Darwin arm64, py3.11.9 · git 7c80eea
- Mode: parts in-process · rounds: 5 · measured visits: 110
- Parcels: twoflat, milwaukee, downtown, pin1, fresh_south, fresh_west, fresh_north, p4_uptown, p4_westtown, p4_woodlawn, p4_bridgeport

## cold

| | n | p50 | p95 | max |
|---|---|---|---|---|
| first screen | 55 | 3.49 s | 5.77 s | 14.16 s |
| Overview, exact parcels | 45 | 5.99 s | 17.40 s | 32.19 s |
| Overview, approximate parcels | 10 | 17.87 s | 32.85 s | 32.85 s |
| whole Profile (every part) | 55 | 26.46 s | 45.44 s | 52.87 s |
| part activity (own time) | 55 | 19.66 s | 20.05 s | 20.06 s |
| part activity (from visit start) | 55 | 25.25 s | 45.44 s | 51.85 s |
| part block_face (own time) | 5 | 17.63 s | 20.05 s | 20.05 s |
| part block_face (from visit start) | 5 | 21.21 s | 24.40 s | 24.40 s |
| part history (own time) | 55 | 7.43 s | 20.02 s | 20.06 s |
| part history (from visit start) | 55 | 19.58 s | 34.92 s | 52.87 s |
| part incentives (own time) | 55 | 10.02 s | 20.05 s | 20.05 s |
| part incentives (from visit start) | 55 | 18.90 s | 39.12 s | 52.52 s |
| part money (own time) | 55 | 3.62 s | 6.27 s | 8.05 s |
| part money (from visit start) | 55 | 13.51 s | 29.03 s | 37.38 s |
| part neighborhood (own time) | 55 | 5.05 s | 20.05 s | 20.06 s |
| part neighborhood (from visit start) | 55 | 17.15 s | 36.75 s | 42.21 s |

Sources past the late deadline: {'address_311': 17, 'crime_yoy': 10, 'incentives': 5, 'violations': 4, 'neighborhood': 4, 'property_history': 3, 'crime': 2, 'block_face': 2, 'aro_housing': 1} (of 55 visits). Failed parts: none.

## warm

| | n | p50 | p95 | max |
|---|---|---|---|---|
| first screen | 55 | 17 ms | 1.93 s | 3.94 s |
| Overview, exact parcels | 45 | 31 ms | 1.94 s | 3.95 s |
| Overview, approximate parcels | 10 | 1.38 s | 1.84 s | 1.84 s |
| whole Profile (every part) | 55 | 2.09 s | 18.66 s | 21.31 s |
| part activity (own time) | 55 | 274 ms | 18.63 s | 20.03 s |
| part activity (from visit start) | 55 | 1.76 s | 18.66 s | 21.31 s |
| part block_face (own time) | 5 | 495 ms | 7.50 s | 7.50 s |
| part block_face (from visit start) | 5 | 527 ms | 7.52 s | 7.52 s |
| part history (own time) | 55 | 226 ms | 2.25 s | 5.44 s |
| part history (from visit start) | 55 | 275 ms | 3.89 s | 6.72 s |
| part incentives (own time) | 55 | 226 ms | 5.84 s | 9.71 s |
| part incentives (from visit start) | 55 | 280 ms | 7.25 s | 11.07 s |
| part money (own time) | 55 | 130 ms | 269 ms | 484 ms |
| part money (from visit start) | 55 | 278 ms | 2.22 s | 4.18 s |
| part neighborhood (own time) | 55 | 225 ms | 488 ms | 5.40 s |
| part neighborhood (from visit start) | 55 | 286 ms | 2.47 s | 6.69 s |

Sources past the late deadline: {'crime_yoy': 2} (of 55 visits). Failed parts: none.

First visit after process start (round 0, not in the percentiles): Overview 24.78 s, whole Profile 44.81 s.
