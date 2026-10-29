# Discovery latency: baseline

Measured 2026-10-29T02:00:42+00:00 against http://localhost:8003 (macOS-15.6.1-arm64-arm-64bit). **Local idle machine, not production.** 5 runs per cell; sort `lot_size desc`.

Backend RSS: 862.4 MB before, 1932.8 MB after.

| Query | Matches | /search first | /search median | /search p95 | /pins first | /pins median | /pins p95 | List=map parity |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| recipe (4 filters) | 5,005 | 1142 | 876 | 1142 | 409 | 408 | 409 | ok (200 rows) |
| 3 filters (no lot size) | 7,531 | 675 | 675 | 684 | 410 | 409 | 410 | ok (200 rows) |
| 1 filter (zoning: residential) | 599,804 | 2303 | 3221 | 3259 | 3175 | 3177 | 3191 | ok (200 rows) |
| no filters | 949,014 | 4963 | 4017 | 4963 | 4980 | 4113 | 4987 | ok (200 rows) |
| recipe again (repeat) | 5,005 | 860 | 864 | 866 | 402 | 402 | 1310 | ok (200 rows) |

Times in milliseconds. 'first' is the first run of the cell, 'median'/'p95' are over all runs of the cell.
