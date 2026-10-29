# Discovery latency: final

Measured 2026-10-29T02:19:41+00:00 against http://localhost:8003 (macOS-15.6.1-arm64-arm-64bit). **Local idle machine, not production.** 7 runs per cell; sort `lot_size desc`.

Backend RSS: 1793.0 MB before, 1913.2 MB after.

| Query | Matches | /search first | /search median | /search p95 | /pins first | /pins median | /pins p95 | combined first | combined median | List=map parity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| recipe (4 filters) | 5,005 | 495 | 1 | 495 | 26 | 11 | 26 | 10 | 11 | ok (200 rows) |
| 3 filters (no lot size) | 7,531 | 338 | 1 | 338 | 11 | 11 | 937 | 12 | 10 | ok (200 rows) |
| 1 filter (zoning: residential) | 599,804 | 634 | 2 | 634 | 12 | 10 | 12 | 11 | 11 | ok (200 rows) |
| no filters | 949,014 | 504 | 1 | 504 | 11 | 10 | 11 | 10 | 10 | ok (200 rows) |
| recipe again (repeat) | 5,005 | 1 | 1 | 1 | 11 | 11 | 12 | 11 | 11 | ok (200 rows) |

Times in milliseconds. 'first' is the first run of the cell, 'median'/'p95' are over all runs of the cell.
