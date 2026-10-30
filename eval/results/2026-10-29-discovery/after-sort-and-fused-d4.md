# Discovery latency: after-sort-and-fused-d4

Measured 2026-10-29T02:08:57+00:00 against http://localhost:8003 (macOS-15.6.1-arm64-arm-64bit). **Local idle machine, not production.** 5 runs per cell; sort `lot_size desc`.

Backend RSS: 1795.6 MB before, 1992.2 MB after.

| Query | Matches | /search first | /search median | /search p95 | /pins first | /pins median | /pins p95 | List=map parity |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| recipe (4 filters) | 5,005 | 499 | 343 | 499 | 370 | 354 | 370 | ok (200 rows) |
| 3 filters (no lot size) | 7,531 | 345 | 343 | 345 | 354 | 354 | 358 | ok (200 rows) |
| 1 filter (zoning: residential) | 599,804 | 628 | 616 | 628 | 636 | 639 | 643 | ok (200 rows) |
| no filters | 949,014 | 499 | 496 | 508 | 530 | 527 | 1465 | ok (200 rows) |
| recipe again (repeat) | 5,005 | 351 | 350 | 351 | 360 | 359 | 360 | ok (200 rows) |

Times in milliseconds. 'first' is the first run of the cell, 'median'/'p95' are over all runs of the cell.
