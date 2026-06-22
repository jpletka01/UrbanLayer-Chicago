# Cook County GIS Parcel Resolution — Closable Coverage Gap + Geometry Restore

**Date:** 2026-06-22 · **Status:** Investigation + **Layer 1 IMPLEMENTED behind a flag** (`assessor_address_resolution_enabled`, default OFF; not yet committed/deployed). Live-verified end-to-end (481 W Deming → authoritative; 2400 N Milwaukee stays approximate; 642 W Belden control). 888 non-integration tests pass. Layer 2 (geometry/PIP) deferred. **To enable:** spot-check ~10 recovered PINs vs. the county parcel viewer, then flip the flag True.
**Follow-up to:** `2026-06-21_resolver-investigation.md` (Finding #1) and `archive/2026-06-21_pin-resolution-seam.md` (the seam fix that made the failure *safe*).
**Verdict in one line:** The remaining "approximate / nearest-parcel-unverified" degradation is a **data-coverage gap, not a logic bug**, and it is **closable** — a *second* authoritative address→PIN source (`3723-97qp`) resolves the very addresses `78yw-iddh` misses, and a working parcel-polygon source (`77tz-riq7`) can restore geometry + true point-in-polygon without the broken GIS MapServer.

---

## 1. Root-cause recap (where we are today)

Cook County GIS MapServer layer 44 — the authoritative **coordinate→parcel** spatial lookup — has a broken spatial index and is effectively down (`parcels.py:_lookup_parcel_gis`, bounded to 8s, almost always returns nothing). R7 routed around it with Cook County **Address Points `78yw-iddh`** for **address→PIN** (`address_points.py:address_to_pin`), which is authoritative and GIS-independent.

The 2026-06-21 seam fix made the *failure* mode safe: when an address is **absent from `78yw-iddh`**, `_resolve_location` (`main.py:1284`) degrades to geocode→nearest-centroid (`parcels.py:_lookup_parcel_socrata`), which can land on a **neighbor** parcel — so `/api/scorecard` now withholds the PIN (`resolved_pin=null`, `confidence="approximate"`) and flags `nearest_parcel_unverified` so the UI caveats the property/tax/comps cards.

**What was left open:** real, authoritatively-addressed parcels that simply aren't in `78yw-iddh` still resolve as "approximate" — a correct-but-degraded experience. Recommendation #3 of the 2026-06-21 investigation explicitly flagged this as a coverage problem to solve. This write-up solves it.

---

## 2. The resolver chain (current) and the single fix site

`_resolve_location` (`main.py:1284`), strict precedence:
1. explicit lat/lon → authoritative
2. supplied PIN → authoritative centroid (via `pabr-t5kh` `lat`,`lon`)
3. address → PIN via Address Points `78yw-iddh` (`address_to_pin`) → authoritative
4. **degraded**: geocode only → `pin=None`, `confidence="approximate"`
5. 422

All surfaces funnel through this one function — scorecard (`main.py:1538`), report (`main.py:4420`, `4611`), pin handoffs (`main.py:1031`, `4589`) — and the property/tax/comps cards key off `rl.pin` via `lookup_parcel_by_pin` (`retrieval/property/__init__.py:44`). **One authoritative fallback added between steps 3 and 4 fixes every surface at once.**

---

## 3. Finding A — a second authoritative address→PIN source closes the gap

**`3723-97qp` — Assessor *Parcel Addresses*** (Cook County Socrata; ~1.86M rows, current to year **2026**). Columns: `pin`, `pin10`, `year`, `prop_address_full`, plus mailing/owner address fields. No coordinates.

Live proof points (`https://datacatalog.cookcountyil.gov/resource/3723-97qp.json`, year=2026):

| address | `78yw-iddh` (Address Points) | `3723-97qp` (Assessor Addresses) | reality |
|---|---|---|---|
| **481 W DEMING PL** | **0 rows** → degrades to approximate today | **unique `14283190070000`** | the documented ground-truth EX parcel ✅ gap closed |
| 642 W BELDEN | unique `14331030110000` | unique `14331030110000` | control — both agree ✅ |
| 1601 N MILWAUKEE | authoritative (flagship demo) | **3 distinct PINs** (multi-parcel bldg) → reject | already resolved by `78yw-iddh`; assessor correctly falls through |
| 333 W WACKER | — | **2 distinct PINs** → reject | large multi-parcel building; reject is correct |
| **2400 N MILWAUKEE** | 0 rows | **0 rows** | genuine non-address (parcel addressed off a cross street); "approximate" is *correct* — demo swap to 1601 was right |

**Coordinate backfill** for the resolved PIN uses the existing path — `pabr-t5kh` exposes `lat`,`lon` (verified `14283190070000` → `41.9287358532, -87.641452815`, class `EX`), the same source `_resolve_location` step 2 and `lookup_parcel_by_pin` already use.

### Recommended Layer 1 (the core "solid fix")
- New resolver `assessor_address_to_pin(address)` mirroring `address_to_pin` (in `address_points.py` or a sibling `parcel_addresses.py`):
  1. `parse_chicago_address(address)` → number / direction / name.
  2. Query `3723-97qp` (latest `year`) with `prop_address_full like '<num> <dir> <name>%'`.
  3. **Re-parse each returned `prop_address_full` and keep only exact number+direction+name matches.** This is required — a raw `like '481 W DEMING%'` also matches `4810 W DEMING` and unit-suffixed variants. Re-parsing each row is the robust guard.
  4. Require a **single distinct PIN** (same confident-unique-match contract as `address_to_pin`; multi/zero → `None`).
- Wire into `_resolve_location` as **step 3.5** — after the `78yw-iddh` miss, before the degraded geocode path. On a confident PIN, reuse the PIN→centroid logic (`pabr-t5kh` lat/lon) and return `confidence="authoritative"`.
- Gate behind a config flag `assessor_address_resolution_enabled` (mirror `address_point_resolution_enabled`, `config.py:77`) for safe rollout.
- Keep `parcel_address_matches` (`address_points.py:192`) as defense-in-depth on the degraded path.

**Outcome:** 481 W Deming (and its coverage-gap cousins) resolve authoritatively — correct PIN + correct property/tax/comps via `lookup_parcel_by_pin`. Only genuine non-addresses (2400 N Milwaukee) remain approximate, which is correct.

---

## 4. Finding B — a working parcel-polygon source restores geometry + true containment

**`77tz-riq7` — ccgisdata Parcel 2021** (Cook County Socrata; ~1.43M parcels). Carries **`the_geom` MultiPolygon** for every parcel plus `pin10`, `latitude`, `longitude`, `assessorbldgclass`, etc.

Spatial-query behavior (verified live):
- `within_circle(the_geom, lat, lon, <meters>)` **works** — querying the 481 W Deming geocode `(41.92886, -87.64159)` at 60 m returned the true parcel `1428319007` among the candidates.
- Server-side `intersects(the_geom, 'POINT(lon lat)')` is **NOT served** on this dataset — it returned empty even for a polygon's own centroid. So point-in-polygon must be done **locally** (shapely) over `within_circle` candidates, not via SoQL `intersects`.

**Vintage caveat:** 2021 geometry. Parcel boundaries are highly stable (splits/consolidations are rare), and identity still comes from the address/PIN sources in Layer 1 — so stale geometry can never produce a *wrong identity*, only a slightly stale *shape*. `77tz-riq7` is the newest ccgisdata parcel layer on the portal (2020/2021 + historical years); a current-year polygon would require the Assessor's own ArcGIS feature service if freshness ever matters.

### Recommended Layer 2 (separable follow-up)
- `lookup_parcel_geometry(pin10)` from `77tz-riq7` → MultiPolygon for the scorecard map + report development envelope. **Retires the "Report envelope map depends on parcel geometry" known limitation** (which currently silently omits whenever GIS is down).
- Optionally upgrade the coordinate→parcel fallback in `parcels.py` from nearest-centroid to **local shapely point-in-polygon** over `within_circle` candidates → authoritative *containment* for explicit-lat/lon and any good-coordinate path (instead of nearest-by-distance). Note: PIP quality is bounded by input-coordinate quality — an interpolated Census geocode that lands on the ROW still won't fall inside any polygon, which is exactly why Layer 1 (authoritative address→PIN) is the primary fix and Layer 2 is the geometry/robustness layer.

---

## 4b. Real-data validation (2026-06-22, live APIs, production parser)

A harness reimplemented both resolvers faithfully (importing the production
`parse_chicago_address`) and ran them against the live Cook County Socrata APIs on random
city-wide samples. Two metrics:

**Safety — does the assessor source ever contradict the authoritative one?** Sampled 160
addresses from `78yw-iddh` (authoritative ground truth). Of the **55** where *both* sources
returned a unique PIN: **55 AGREE, 0 DISAGREE.** In **18** more, Address Points was unique
but the assessor source was multi/miss → it **conservatively falls through** (never
overrides). No case observed where the assessor source produced a *different* unique PIN.

**Impact + recovery — Chicago only** (filtered `prop_address_city_name='CHICAGO'`; 300
addresses, only 6 unparseable once suburban no-directional addresses are excluded):
- **~25% of real Chicago addresses currently hit the degraded path** — 222 resolve via
  Address Points, **72 miss/multi** (the gap).
- The assessor fallback **recovers 39 of those 72 (54%) as a unique PIN, all 39 correct**
  (PIN == the record's own); the other 33 are genuinely multi-PIN (condo/multi-parcel) and
  **correctly fall through** to approximate.
- Net authoritative coverage rises ~**75% → ~88%** on the sample, zero wrong identities.
- Example recovered gap addresses (ordinary South/SW-side residential, absent from Address
  Points): `3234 S Hamilton Ave`, `4300/4304 S St Louis Ave`, a run of `S Bensley Ave`,
  `6959 S Honore St`.

**End-to-end coordinate backfill:** all **10/10** sampled recovered PINs have `lat`/`lon` in
`pabr-t5kh`, so the full chain (assessor address→PIN → PIN→centroid) yields a complete
authoritative resolution that drives `lookup_parcel_by_pin`.

*Honesty caveat:* the gap-recovery "correct" check is partly self-referential (recovered PIN
== the same assessor record's PIN). The *independent* safety check is the agreement test
above (vs. the separate `78yw-iddh` source), which showed 0 disagreements — together they
are strong evidence the fallback adds coverage without adding wrong identities. A pre-ship
step should still spot-check a handful of recovered PINs against the county parcel viewer.

## 5. Suggested implementation order

1. **Layer 1** — highest leverage, lowest risk, directly closes the documented gap. ~1 new resolver module + `_resolve_location` wiring + config flag + tests (unit fixtures for 481 W Deming hit, 2400 N Milwaukee miss-in-both, 1601 N Milwaukee multi-match reject, 642 W Belden control; one `@pytest.mark.integration` live check).
2. **Layer 2** — geometry restore + true containment; also retires an envelope-map known limitation. Larger, touches `parcels.py` + the report envelope path.

Both layers keep Address Points authoritative-primary and the seam fix's withhold-don't-guess bias intact; they only *add* authoritative coverage and *upgrade* the degraded path.

---

## 6. Datasets referenced (Cook County Socrata, base `https://datacatalog.cookcountyil.gov/resource`)

| id | name | use | key fields |
|---|---|---|---|
| `78yw-iddh` | Address Points | address→PIN (primary, has coords) | `add_number`, `st_predir`, `st_name`, `pin`, `lat`, `long` |
| `3723-97qp` | Assessor - Parcel Addresses | **address→PIN gap-fill (NEW)** | `pin`, `pin10`, `year`, `prop_address_full` |
| `pabr-t5kh` | Assessor - Parcel Universe | PIN→centroid + enrichment | `pin`, `lat`, `lon`, `class`, `zip_code`, `township_name`, `nbhd_code`, `tax_code` |
| `77tz-riq7` | ccgisdata - Parcel 2021 | **geometry + within_circle PIP (NEW)** | `pin10`, `the_geom` (MultiPolygon), `latitude`, `longitude` |

*Read-only investigation. Only this findings file + a known-issues follow-up note were written. No product code, config, or tests touched.*
