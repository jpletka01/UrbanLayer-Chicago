# Discovery latency: after-cache

Measured 2026-10-29T02:11:01+00:00 against http://localhost:8003 (macOS-15.6.1-arm64-arm-64bit). **Local idle machine, not production.** 5 runs per cell; sort `lot_size desc`.

Backend RSS: 1803.4 MB before, 1937.3 MB after.

| Query | Matches | /search first | /search median | /search p95 | /pins first | /pins median | /pins p95 | List=map parity |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| recipe (4 filters) | 5,005 | 487 | 2 | 487 | 26 | 11 | 26 | ok (200 rows) |
| 3 filters (no lot size) | 7,531 | 337 | 1 | 337 | 11 | 10 | 12 | ok (200 rows) |
| 1 filter (zoning: residential) | 599,804 | 618 | 1 | 618 | 12 | 11 | 12 | ok (200 rows) |
| no filters | 949,014 | 505 | 2 | 505 | 10 | 11 | 938 | ok (200 rows) |
| recipe again (repeat) | 5,005 | 2 | 1 | 2 | 11 | 11 | 11 | ok (200 rows) |

Times in milliseconds. 'first' is the first run of the cell, 'median'/'p95' are over all runs of the cell.
