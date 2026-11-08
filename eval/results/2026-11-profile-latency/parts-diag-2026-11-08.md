# Profile in parts: parts-diag-2026-11-08

- When: 2026-11-08T10:13:06+00:00 · host: Darwin arm64, py3.11.9 · git 7c80eea
- Mode: parts in-process · rounds: 2 · measured visits: 44
- Parcels: twoflat, milwaukee, downtown, pin1, fresh_south, fresh_west, fresh_north, p4_uptown, p4_westtown, p4_woodlawn, p4_bridgeport

## cold

| | n | p50 | p95 | max |
|---|---|---|---|---|
| first screen | 22 | 3.55 s | 8.79 s | 9.43 s |
| Overview, exact parcels | 18 | 7.05 s | 26.18 s | 26.18 s |
| Overview, approximate parcels | 4 | 19.34 s | 49.26 s | 49.26 s |
| whole Profile (every part) | 22 | 30.00 s | 46.23 s | 69.28 s |
| part activity (own time) | 22 | 20.02 s | 20.05 s | 20.29 s |
| part activity (from visit start) | 22 | 30.00 s | 46.23 s | 69.28 s |
| part block_face (own time) | 2 | 12.85 s | 16.01 s | 16.01 s |
| part block_face (from visit start) | 2 | 16.77 s | 25.98 s | 25.98 s |
| part history (own time) | 22 | 7.52 s | 19.11 s | 20.05 s |
| part history (from visit start) | 22 | 20.90 s | 46.23 s | 56.47 s |
| part incentives (own time) | 22 | 13.28 s | 20.05 s | 20.28 s |
| part incentives (from visit start) | 22 | 25.59 s | 45.22 s | 68.12 s |
| part money (own time) | 22 | 3.53 s | 6.55 s | 12.14 s |
| part money (from visit start) | 22 | 13.74 s | 31.80 s | 54.91 s |
| part neighborhood (own time) | 22 | 9.44 s | 17.02 s | 19.63 s |
| part neighborhood (from visit start) | 22 | 22.22 s | 38.52 s | 56.69 s |

Sources past the late deadline: {'address_311': 13, 'crime': 8, 'crime_yoy': 6, 'incentives': 5, 'violations': 4, 'property_history': 1} (of 22 visits). Failed parts: none.

## warm

| | n | p50 | p95 | max |
|---|---|---|---|---|
| first screen | 22 | 17 ms | 1.69 s | 2.09 s |
| Overview, exact parcels | 18 | 31 ms | 2.10 s | 2.10 s |
| Overview, approximate parcels | 4 | 1.44 s | 1.64 s | 1.64 s |
| whole Profile (every part) | 22 | 3.76 s | 18.88 s | 19.54 s |
| part activity (own time) | 22 | 2.31 s | 17.48 s | 19.51 s |
| part activity (from visit start) | 22 | 3.52 s | 18.88 s | 19.54 s |
| part block_face (own time) | 2 | 107 ms | 492 ms | 492 ms |
| part block_face (from visit start) | 2 | 139 ms | 523 ms | 523 ms |
| part history (own time) | 22 | 109 ms | 4.86 s | 5.11 s |
| part history (from visit start) | 22 | 142 ms | 5.14 s | 6.46 s |
| part incentives (own time) | 22 | 150 ms | 4.72 s | 6.42 s |
| part incentives (from visit start) | 22 | 528 ms | 4.74 s | 8.02 s |
| part money (own time) | 22 | 107 ms | 490 ms | 5.11 s |
| part money (from visit start) | 22 | 140 ms | 2.34 s | 6.72 s |
| part neighborhood (own time) | 22 | 110 ms | 496 ms | 5.11 s |
| part neighborhood (from visit start) | 22 | 142 ms | 2.34 s | 6.71 s |

Sources past the late deadline: none (of 22 visits). Failed parts: none.

First visit after process start (round 0, not in the percentiles): Overview 9.39 s, whole Profile 29.44 s.
