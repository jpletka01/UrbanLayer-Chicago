# Discovery index builder: engineering decisions

Fixes to the offline Property Discovery index builder (`backend/discovery/index_build.py`) found while measuring it. Format: see `README.md` in this folder.

---

## Item 1: drop parcels outside every community-area polygon (2026-10-28)

**Decision:** `_assemble_ca` drops a spine point that lies in no community-area polygon instead of tagging it to the community area whose bounding box fetched it. The old line was `community_area_by_point(lat, lon) or ca`.

- **Filter before the joins.** `_split_by_community_area` runs right after the spine fetch, so a dropped PIN never costs a characteristics, assessment, sales or address query. *Alternative:* drop inside the row loop (same result, but pays for ~7% wasted joins).
- **`assemble_parcel` stays pure.** It still takes `neighborhood_ca` as given; the exclusion lives in the caller. *Alternative:* make `neighborhood_ca=None` mean "skip", which would hide a data-quality rule in a row-assembly function and let a row with no area into the index.
- **Prune old rows.** `_assemble_ca` returns the dropped PINs and `build_index` deletes them from an existing index (`parcel_index.delete_parcels`). `upsert_parcels` is `INSERT OR REPLACE` and never deletes, so without this a monthly `--refresh` would keep the 66k suburban rows until someone rebuilt from an empty file. A PIN is dropped by every community area that fetches it (point-in-polygon is deterministic), so the prune cannot remove a row another area is about to upsert. *Alternative:* document "delete the file and rebuild"; rejected because the monthly timer would silently never fix it.
- **No `data_version` bump.** The `meta` contract is the string `idx-<date>-<built_at>-<n>p`, which is new on every build, and no field was added or renamed. The next rebuild carries the fix and changes the row count.
- **Not a tolerance.** `geo.is_within_chicago` allows ~200 m outside the polygons for address lookups. The index does not: a parcel that is not in a polygon has no honest area to be filed under. A parcel on the city line that the polygons clip is a boundary-data question, not this fix.

**Why (evidence).** Read-only audit of a copy of the production index built 2026-10-01 (WS8 Phase 0, run by the audit session, not this one): 949,014 rows, 66,658 (7.0%) outside every polygon. A random sample of zoned rows had 1 outside in 26,420, so nearly all outside rows lack a zoning district (they are not in the City's zoning layer either). They sat under Austin (CA 25), O'Hare (76), Mount Greenwood (74) and Forest Glen (12), mostly with PIN prefixes 16, 12, 24, 10, 09 and 15. Each prefix spans Chicago and suburban townships, so a prefix does not identify the suburb; Forest Park was confirmed in a sample. Effects: Discovery results and per-area counts included non-Chicago parcels, and area-level coverage and `/api/area-stats` benchmarks were diluted. Per-prefix and per-area numbers: `eval/results/2026-10-28-ws8/index_census.json`, key `outside_city`, on branch `codex/ws8-phase0-coverage-audit`.

**Revisit if:**
- A rebuilt index shows a visible gap along the city line (parcels the polygons clip but that are Chicago's). Then add a small distance tolerance, measured against the audit's `outside_city` list first.
- `community_areas.geojson` is replaced by a source with coarser edges.
- The product decides to show suburban parcels as a separate "outside city" group rather than hide them.

**Numbers**
- **Before** (2026-10-01 production index copy, measured by the audit session): 66,658 of 949,014 rows (7.0%) outside every polygon.
- **After:** not measured. This item changes only the builder; the production index has not been rebuilt, and rebuilding it needs a separate production approval. Expected: roughly 882k rows, with the outside count 0.
- **Tests:** `test_split_by_community_area_drops_points_outside_every_polygon`, `test_assemble_ca_excludes_outside_points_and_keeps_polygon_area` (also asserts the dropped PIN reaches no join query), `test_build_index_prunes_stale_outside_rows_on_refresh`, `test_delete_parcels_removes_only_named_pins`. Backend unit suite 2,427 passed, `ruff check .` clean (2026-10-28).
- **Reproduce:** `python -m pytest backend/tests/test_discovery_index_build.py backend/tests/test_discovery_parcel_index.py -q`
- **Not measured:** the real post-fix row count and per-area counts; how many community-line parcels the polygons clip; effect on `recipeCounts` and area benchmarks (should shift slightly, since suburban rows carried few attributes); rebuild time.
