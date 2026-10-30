# Discovery index builder: engineering decisions

Fixes to the offline Property Discovery index builder (`backend/discovery/index_build.py`) found while measuring it. Format: see `README.md` in this folder.

---

## Item 1: drop parcels outside every community-area polygon (2026-10-28)

**Decision:** `_assemble_ca` drops a spine point that lies in no community-area polygon instead of tagging it to the community area whose bounding box fetched it. The old line was `community_area_by_point(lat, lon) or ca`.

- **Filter before the joins.** `_split_by_community_area` runs right after the spine fetch, so a dropped PIN never costs a characteristics, assessment, sales or address query. *Alternative:* drop inside the row loop (same result, but pays for ~7% wasted joins).
- **`assemble_parcel` stays pure.** It still takes `neighborhood_ca` as given; the exclusion lives in the caller. *Alternative:* make `neighborhood_ca=None` mean "skip", which would hide a data-quality rule in a row-assembly function and let a row with no area into the index.
- **Prune old rows.** `_assemble_ca` returns the dropped PINs and `build_index` deletes them from an existing index (`parcel_index.delete_parcels`). `upsert_parcels` is `INSERT OR REPLACE` and never deletes, so without this a monthly `--refresh` would keep the ~66.7k suburban rows until someone rebuilt from an empty file. A PIN is dropped by every community area that fetches it (point-in-polygon is deterministic), so the prune cannot remove a row another area is about to upsert. *Alternative:* document "delete the file and rebuild"; rejected because the monthly timer would silently never fix it.
- **No `data_version` bump.** The `meta` contract is the string `idx-<date>-<built_at>-<n>p`, which is new on every build, and no field was added or renamed. The next rebuild carries the fix and changes the row count.
- **Not a tolerance.** `geo.is_within_chicago` allows ~200 m outside the polygons for address lookups. The index does not: a parcel that is not in a polygon has no honest area to be filed under. A parcel on the city line that the polygons clip is a boundary-data question, not this fix.

**Why (evidence).** Read-only audit of a copy of the production index built 2026-10-01 (WS8 Phase 0, run by the audit session, not this one): 949,014 rows, 66,692 (7.03%) outside every polygon and 882,322 inside. A random sample of zoned rows had 1 outside in 26,420, so nearly all outside rows lack a zoning district (they are not in the City's zoning layer either). They sat under Austin (CA 25), O'Hare (76), Mount Greenwood (74) and Forest Glen (12), mostly with PIN prefixes 16, 12, 24, 10, 09 and 19 (each spans Chicago and suburban townships, so a prefix does not identify the suburb); Forest Park, prefix 15, was confirmed in a sample. Effects: Discovery results and per-area counts included non-Chicago parcels, and area-level coverage and `/api/area-stats` benchmarks were diluted. Per-prefix and per-area numbers: `eval/results/2026-10-28-ws8/index_census.json`, key `outside_city`, on branch `codex/ws8-phase0-coverage-audit`.

**Revisit if:**
- A rebuilt index shows a visible gap along the city line (parcels the polygons clip but that are Chicago's). Then add a small distance tolerance, measured against the audit's `outside_city` list first.
- `community_areas.geojson` is replaced by a source with coarser edges.
- The product decides to show suburban parcels as a separate "outside city" group rather than hide them.

**Numbers**
- **Before** (2026-10-01 production index copy, measured by the audit session): 66,692 of 949,014 rows (7.03%) outside every polygon (882,322 inside).
- **After:** not measured. This item changes only the builder; the production index has not been rebuilt, and rebuilding it needs a separate production approval. Expected: 882,322 rows (the audit's in-city count), with the outside count 0.
- **Tests:** `test_split_by_community_area_drops_points_outside_every_polygon`, `test_assemble_ca_excludes_outside_points_and_keeps_polygon_area` (also asserts the dropped PIN reaches no join query), `test_build_index_prunes_stale_outside_rows_on_refresh`, `test_delete_parcels_removes_only_named_pins`. Backend unit suite 2,427 passed, `ruff check .` clean (2026-10-28).
- **Reproduce:** `python -m pytest backend/tests/test_discovery_index_build.py backend/tests/test_discovery_parcel_index.py -q`
- **Not measured:** the real post-fix row count and per-area counts; how many community-line parcels the polygons clip; effect on `recipeCounts` and area benchmarks (should shift slightly, since suburban rows carried few attributes); rebuild time.

---

## Item 2: prune the dropped PINs in the form the index stores (2026-10-29)

**Decision:** `_split_by_community_area` returns the dropped parcels' `spine["pin"]` (dashed, `XX-XX-XXX-XXX-XXXX`), not `pin_digits` (14 digits). Item 1's prune handed the digits to `delete_parcels`, which runs `DELETE ... WHERE pin = ?` against the dashed key the index stores, so it matched nothing.

- **Fix where the value is made, not where it is used.** The dropped list exists only to be deleted, so it carries the stored key. *Alternative:* convert at the `delete_parcels` call (`format_pin(p)`), or make `delete_parcels` accept both forms; either leaves a list called "dropped PINs" that cannot be used as-is.
- **Fix the test shape, not just the assertion.** The existing tests built spine rows with `pin == pin_digits` (both 14 digits), unlike `_fetch_spine`, so the prune test stored an undashed stale row and passed against a bug production hit. `_spine_row` now builds `pin` with `format_pin`, as `_fetch_spine` does, and the stale row is stored dashed.

**Why (evidence).** The 2026-10-29 production refresh ran 4 h 33 min, exited 0 and logged "dropped N parcels outside every community area" for the areas whose boxes catch suburbs, but never logged a "pruned ... stale non-Chicago rows" line. A copy of the finished index (949,020 rows, `idx-20261029-...-949020p`) had the same 66,692 rows outside every polygon as the 2026-10-01 copy, with an identical PIN-prefix distribution. Direct probe: `delete_parcels` on a dashed row returns 0 for the 14-digit form and 1 for the dashed form. With the three affected tests updated to the production shape they fail on the Item 1 code and pass on this change.

**Revisit if:** a build shows a "pruned" line of zero for a refresh that logged drops (the prune and the stored key have drifted again), or the index key format changes.

**Numbers**
- **Before:** 66,692 of 949,020 rows (7.03%) outside every polygon after a full production refresh with Item 1's code.
- **After (the fix itself):** not measured on production. A rebuild would carry it; the existing file needs the one-off prune below.
- **One-off prune (`backend/discovery/index_prune.py`, `python -m backend.discovery.index_prune [--apply]`):** deletes the rows `community_area_by_point` places in no polygon (the builder's and the census's test), then re-runs `finalize_index`. Dry run by default; `--apply` first copies the file to `<index>.pre-prune` (SQLite online backup), refuses when more than `--max-share` (10%) of rows look outside or when the polygon file is missing, checks that it deleted exactly what it found, and re-counts afterwards. *Alternatives:* another ~4.5 h full refresh (works, but redoes 882k parcels of API joins to delete 7%); a raw `DELETE` in `sqlite3` (skips the finalize pass, so `recipe_counts`, `populated_fields` and `value_percentile` would describe rows that no longer exist).
- **Rehearsal on a scratch copy of the real 2026-10-29 production index (local, not production):** dry run 63 s and found 66,692 (matches the census). `--apply` took 134 s, 326 MB peak, and left 882,328 rows (the audit's 882,322 in-city rows plus the refresh's 6 new ones); an independent `eval.capacity_coverage` run on the result found 0 outside. Recipe counts moved because strays were in them: teardown 1,089 to 1,037, fresh_comps 383 to 362, undervalued_mf 47 to 46 (vacant_mf_transit 4,997, underused_commercial_tif 312, adu_2flats 0 unchanged). Community-area footprint and populated fields identical. The file keeps its size (SQLite does not shrink without `VACUUM`).
- **Tests:** `test_split_by_community_area_drops_points_outside_every_polygon`, `test_assemble_ca_excludes_outside_points_and_keeps_polygon_area`, `test_build_index_prunes_stale_outside_rows_on_refresh` (all three fail on the Item 1 code); `test_discovery_index_prune.py` (6: dry run writes nothing, apply removes only outside rows and keeps a backup, second run is a no-op, refuses over the share guard, refuses without polygons, rows with no coordinates are kept). `-k discovery` 205 passed; `ruff check` clean on the touched files.
- **Not measured:** the prune on the production box itself (disk headroom for the backup, timing on the busy 4 vCPU host); what the live Discovery page shows afterwards.

## Item 3: the production prune, and the docs that still said "pending" (2026-10-30)

**Decision:** record that the one-off prune ran on the production index on 2026-10-30, and rewrite the five living docs (`backend/CLAUDE.md`, `frontend/CLAUDE.md`, `core/known-issues.md`, `property-discovery/README.md` + `10-implementation-status.md`, the manifest) that still said production kept ~67k suburban rows "until the next off-box rebuild" and cited PR #128 as pending. Docs only; no code.

**Alternatives:** leave the 2026-10-28 wording and add a dated note under it. Rejected: those lines are read as current status by every session that loads the context, and two of them told the reader an approval was still outstanding.

**Why (evidence).** The 2026-10-30 session ran `python -m backend.discovery.index_prune --apply` on the box (Jack typed the sudo) after the Item 2 fix deployed; the production index went from 949,020 to 882,328 rows, the same count the local rehearsal produced. The backup `<index>.pre-prune` was left on the data volume for Jack to delete. The same session installed `deploy/discovery-index-rebuild.{service,timer}` (monthly, `OnCalendar=*-*-01 04:17:00`, `TimeoutStartSec=43200`), whose first run is 2026-11-01 04:17 UTC.

**Revisit if:** the 2026-11-01 rebuild's journal shows a non-zero "pruned" line (rows came back), or a capacity census of the prod file finds rows outside every polygon.

**Numbers**
- **Before → after (production, 2026-10-30, from that session's notes, not re-measured here):** 949,020 → 882,328 rows.
- **Reproduce:** on a copy of the prod index, `PYTHONPATH=. python -m eval.capacity_coverage --index <copy>` (expect 882,328 rows, 0 outside polygons).
- **Not measured:** the census on a copy of the pruned production file (needs a fresh copy off the box; on Jack's list); the first timer-driven rebuild.
