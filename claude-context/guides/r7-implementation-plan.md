# R7 — Implementation Plan (address→PIN resolution)

**Status:** IMPLEMENTATION PLAN (2026-06-11). Implements, without redesigning,
`parcel-resolution-truth-model.md` (DESIGN OF RECORD). Scope is **R7 only**.

**Frozen inputs (do not revisit):** PIN is the primary key (§1). Strict-precedence
resolver, no voting (§5). Resolution order: `pin` → deliberate `lat/lon` PIP →
`address→78yw-iddh PIN` → degraded geocode+nearest-centroid → 422 (§5). Invariants
INV-1…INV-6. This plan only specifies *how* to land that design as the smallest safe diff.

**Confirmed `78yw-iddh` schema** (queried live): `pin`, `add_number`, `st_predir`,
`st_name`, `lat`, `long` (note: `long`, not `lon`). Direction/name/number map 1:1 to
`parse_chicago_address()`'s `{direction, name, number}`.

---

## 0. Strategy decisions (locked for this patch)

- **Return shape of `_resolve_location`:** change from a 3-tuple to a 5-field
  `typing.NamedTuple` `ResolvedLocation(lat, lon, address, pin, confidence)`.
  Rationale: the design (§6) requires the resolver to return a **PIN + confidence**;
  a NamedTuple gives named access while keeping the call sites a single-line change.
  All callers and the existing test unpack a 3-tuple, so they change regardless of
  tuple-vs-dataclass — NamedTuple is the smallest correct change.
- **`confidence` values:** the string literals `"authoritative"` and `"approximate"`
  (matches the design's two tiers in §5). No enum — minimal surface.
- **PIN threading is by identity only.** Only the **property/parcel identity** path
  becomes PIN-keyed (`property_domain` → `lookup_parcel`). Every other domain
  (regulatory, zoning, incentives, neighborhood, crime, comps) stays coordinate-driven
  and is *unchanged*. It simply receives a better point: the parcel's authoritative
  `lat/long` from `78yw-iddh` instead of a street-interpolated geocode. This is the
  minimal patch that satisfies INV-2 (pipeline keyed by PIN "whenever a PIN is
  available") without touching seven orchestrators.
- **No new infra.** One additional Socrata dataset on the existing Cook County portal,
  existing `socrata_get`, existing `TTLCache`. Steps 1–3 stay GIS-independent.

---

## 1. Step-by-step implementation

### Step 1 — New address→PIN resolver (Design §5 step 3, §6 bullet 2)

New file `backend/retrieval/property/address_points.py`:

```python
async def address_to_pin(address: str, *, client=None) -> dict | None:
    """Authoritative address→PIN via Cook County Address Points (78yw-iddh).

    Returns {"pin14", "lat", "lon", "address"} on a UNIQUE confident match,
    else None (no match OR multi-match — never an arbitrary pick). GIS-independent.
    """
```

Behavior (strict-precedence safe):
- `parse_chicago_address(address)` → `{number, direction, name}`; `None` → return `None`.
- Query `78yw-iddh` on the Cook County portal via `socrata_get`:
  `$where = add_number='<number>' AND upper(st_predir)='<DIR>' AND upper(st_name)='<NAME>'`,
  `$select = pin, lat, long`, `$limit = 2`.
- **0 rows → None** (fall through to step 4). **≥2 distinct PINs → None** (multi-match is
  *not* confident per §5 fallback rule; never pick arbitrarily). **Exactly 1 distinct
  PIN → match.**
- Normalize: `pin14 = str(pin).replace("-", "").zfill(14)`; `lat=float(lat)`,
  `lon=float(long)`.
- Wrap external call in try/except → `None` on error (module pattern: return `None` on
  failure). Module-level `TTLCache(ttl_seconds=86400, maxsize=2048, name="address_points")`
  keyed on the normalized parsed tuple.
- Accept optional `client` param for tests (module pattern).

This file is **purely additive** — nothing imports it yet until Step 3.

### Step 2 — Resolve a parcel *by PIN* (Design §6 bullet 3; backbone "A")

In `backend/retrieval/property/parcels.py`, add:

```python
async def lookup_parcel_by_pin(pin14: str, *, client=None) -> dict | None:
    """Resolve the full parcel dict from a known PIN (no coordinate round-trip)."""
```

- Query `pabr-t5kh` (`settings.dataset_ccao_parcels`) with
  `$where=pin='<pin14>'`, `$select=pin,pin10,class,lat,lon,zip_code,township_name,nbhd_code,tax_code`,
  `$limit=1`, `base_url=settings.cook_county_socrata_base`,
  `app_token=settings.cook_county_socrata_token or None`.
- Return the **same dict shape** `_lookup_parcel_socrata` already returns
  (`pin14, bldg_class, bldg_sqft=None, land_sqft=None, total_value=None, address=None,
  geometry=None, zip_code, township_name, nbhd_code, tax_code`). Identical shape ⇒ zero
  changes in `_build_summary`.
- `None` on no row / error. Reuse `_cache`? No — key by PIN in its own small cache or
  reuse `_cache` with a `pin:` prefix. Use `_cache` with key `f"parcel_pin:{pin14}"`.

> Geometry is `None` here (Parcel Universe has no polygon; the GIS layer is down). This
> matches today's degraded behavior for the Socrata fallback — the report's geometry/map
> code already tolerates `parcel_geometry=None`. No new gap introduced.

### Step 3 — `property_domain` accepts an optional PIN (INV-2)

In `backend/retrieval/property/__init__.py`, change the signature to:

```python
async def property_domain(lat, lon, *, pin: str | None = None, workflow="general", client=None):
```

Single change in the body (the only edit):

```python
parcel = (await lookup_parcel_by_pin(pin, client=client)) if pin else \
         (await lookup_parcel(lat, lon, client=client))
if parcel is None and pin:                 # PIN row vanished → degrade to coord path
    parcel = await lookup_parcel(lat, lon, client=client)
if parcel is None:
    log.info("No parcel found at (%s, %s) pin=%s", lat, lon, pin)
    return None
```

Everything downstream (`pin14 = parcel["pin14"]`, characteristics/assessments/sales/tax,
`_build_summary`) is unchanged — it is already PIN-keyed from `parcel["pin14"]`.

### Step 4 — Rewrite `_resolve_location` as the strict-precedence resolver (Design §5)

In `backend/main.py`, replace the body. **Preserve R6** (PIN > co-supplied address) and
the explicit-lat/lon override (INV-4/INV-6 already encoded). New precedence:

```
ResolvedLocation = NamedTuple(lat, lon, address, pin, confidence)

1. explicit lat+lon supplied → (lat, lon, address, pin=None, "authoritative")
     # deliberate point (map/Explorer click) — unchanged; PIP-by-click is future work.
2. pin supplied → existing pabr-t5kh lat/lon lookup → (lat, lon, address, pin, "authoritative")
3. address supplied (and no pin coords yet) →
     hit = await address_to_pin(address)
     if hit: → (hit.lat, hit.lon, address, hit.pin, "authoritative")
4. degraded fallback (no confident PIN above): geocode_address(address) →
     (lat, lon, address, pin=None, "approximate")   # current path, now flagged
5. nothing resolvable → HTTPException 422  (unchanged message)
```

Notes:
- Step 2 keeps the *exact* existing PIN→`pabr-t5kh` block (returns coords + carries the
  PIN forward instead of discarding it). When the PIN row has null coords, fall through
  to address (step 3) then geocode (step 4) exactly as today.
- Step 3 is the **only new branch**; it sits *ahead* of the geocode fallback — this single
  insertion is the §4-Q3 "minimal change that eliminates the 77% failure."
- Step 4 returns `confidence="approximate"` and `pin=None`. That flag drives INV-5.

### Step 5 — Thread PIN + confidence through the data fetchers (INV-1, INV-2, INV-5)

`_fetch_scorecard_data(lat, lon, address, *, pin=None)`:
- Only change: `property_domain(resolved_lat, resolved_lon, pin=pin, workflow=wf)`.
- Add `resolved_pin` / `resolved_confidence` into the returned dict (additive keys).
- The `dummy_plan.location` already carries lat/lon; no other change.

`_fetch_report_data(lat, lon, address, *, pin=None, confidence=None)`:
- Pass `pin=pin` into the `_fetch_scorecard_data` call (line ~2050).
- Carry `confidence` onto `ReportData` (new field, Step 7) for the cover disclosure.
- All address-keyed sub-queries (`address_specific_permits/violations`,
  `parse_chicago_address`) are **unchanged** — they key off the typed address string,
  which is unaffected.

### Step 6 — Update the three call sites in `main.py`

All three currently destructure a 3-tuple. Change to NamedTuple field access:

- `scorecard` (~1325): `rl = await _resolve_location(address, lat, lon, pin)` then call
  `_fetch_scorecard_data(rl.lat, rl.lon, rl.address, pin=rl.pin)`; stamp
  `data["resolved_pin"]=rl.pin`, `data["resolved_confidence"]=rl.confidence`.
- `report` (~4233): `rl = await _resolve_location(...)`; gate purchase on `rl.lat,rl.lon`
  (unchanged semantics); call `_fetch_report_data(rl.lat, rl.lon, rl.address, pin=rl.pin,
  confidence=rl.confidence)`.
- `report/access` (~4379): `rl = await _resolve_location(...)`; use `rl.lat, rl.lon`.

API request/response contracts are **unchanged** for callers (same query params; scorecard
gains two additive response keys — backward compatible).

### Step 7 — INV-5 disclosure (degraded resolution is surfaced, not silent)

- `backend/models.py` `ReportData`: add `resolved_pin: str | None = None` and
  `resolved_confidence: str | None = None` (both optional → backward compatible).
- Report PDF template: when `resolved_confidence == "approximate"`, render one cover line
  near the address: *"Approximate parcel match — verify PIN/address."* When
  `"authoritative"`, optionally show the resolved PIN (already an INV-1 win). This is the
  **only** template touch; no frontend code change is required (scorecard's new keys are
  optional and ignored by the current UI).

### Step 8 — Observability for the degraded path (Design §5 step 4: "logged/counted")

- In `_resolve_location` step 4, `log.warning("R7 degraded resolution (approximate
  parcel) for address=%r", address)`. No new metrics infra — log line is sufficient and
  greppable, matching existing diagnostic style.

---

## 2. File-by-file checklist

| File | Change | Risk |
|------|--------|------|
| `backend/retrieval/property/address_points.py` | **NEW.** `address_to_pin()` over `78yw-iddh`; parse → unique-PIN → `{pin14,lat,lon,address}` or `None`; TTLCache. | Additive; isolated |
| `backend/retrieval/property/parcels.py` | **ADD** `lookup_parcel_by_pin(pin14)` returning the existing parcel dict shape from `pabr-t5kh`. | Additive |
| `backend/retrieval/property/__init__.py` | `property_domain(..., *, pin=None)`; pick `lookup_parcel_by_pin` when `pin`, else `lookup_parcel`; fall back to coord lookup if PIN row missing. | 1 branch; shape identical → `_build_summary` untouched |
| `backend/config.py` | **ADD** `dataset_address_points: str = "78yw-iddh"` (+ optional `limit_address_points: int = 2`). | Additive |
| `backend/main.py` `_resolve_location` | Return `ResolvedLocation` NamedTuple; insert address→PIN step ahead of geocode; set confidence; preserve R6 + explicit-latlon. | Core change; covered by tests |
| `backend/main.py` `_fetch_scorecard_data` | `*, pin=None`; pass to `property_domain`; emit `resolved_pin`/`resolved_confidence`. | Additive params |
| `backend/main.py` `_fetch_report_data` | `*, pin=None, confidence=None`; thread to scorecard + `ReportData`. | Additive params |
| `backend/main.py` 3 call sites | Destructure → NamedTuple field access; pass `pin`/`confidence`. | Mechanical |
| `backend/models.py` `ReportData` | `resolved_pin`, `resolved_confidence` optional fields. | Additive |
| report PDF template (`backend/templates/…report…`) | Conditional INV-5 disclosure line; optional PIN display. | Cosmetic |
| `backend/tests/test_resolve_location.py` | Update unpacking to NamedTuple; add new-branch tests (below). | Test-only |
| `backend/tests/test_address_points.py` | **NEW** unit tests. | Test-only |
| `backend/tests/test_property_domain_pin.py` | **NEW** PIN-path test. | Test-only |
| `claude-context/guides/report-status.md` | Move R7 from OPEN → SHIPPED after deploy. | Docs |

> Confirm `backend/templates` path during implementation (`grep -rln "report" backend/templates`).

---

## 3. Data-flow change (before → after)

```
BEFORE (coordinate-driven, identity re-derived):
  _resolve_location(address) → (lat,lon)            # PIN discarded
    → _fetch_*_data(lat,lon) → property_domain(lat,lon)
      → lookup_parcel(lat,lon) → GIS down → nearest centroid → WRONG PIN

AFTER (PIN-keyed identity, threaded):
  _resolve_location(address)
     ├ pin?      → pabr-t5kh coords         → pin, "authoritative"
     ├ address?  → 78yw-iddh address→PIN    → pin, "authoritative"   ← new, kills 77%
     └ else      → geocode (nearest-centroid) → pin=None, "approximate" (flagged)
    → _fetch_*_data(lat,lon, pin=pin) → property_domain(lat,lon, pin=pin)
      → pin ? lookup_parcel_by_pin(pin)  : lookup_parcel(lat,lon)
```

PIN threading is one-directional and additive: `pin` flows down as a keyword; the lat/lon
continues to flow for the (unchanged) coordinate-driven domains, now sourced from the
authoritative parcel point when address→PIN succeeds.

---

## 4. Required tests

### Unit — `test_address_points.py` (mock `socrata_get`)
- Unique match → `{pin14,lat,lon}` correct; `long`→`lon` mapping verified.
- Unparseable address → `None` (no query issued).
- Zero rows → `None`.
- Two distinct PINs → `None` (multi-match is not confident — INV-3/§5 fallback rule).
- Two rows, same PIN (dup point) → treated as single confident match.
- PIN normalized to 14 digits (strip dashes, zfill).
- Socrata raises → `None` (degrades, never throws).

### Unit — `test_resolve_location.py` (extend existing; keep all current cases green)
- Update every unpack to NamedTuple (`rl = await ...; rl.lat`).
- **New:** address-only, address-point hit → uses `78yw-iddh` coords, `pin` set,
  `confidence=="authoritative"`, geocode **not** called.
- **New:** address-only, address-point miss → falls to geocode, `pin is None`,
  `confidence=="approximate"`.
- **Preserve R6:** `pin` + `address` → PIN coords win, `confidence=="authoritative"`,
  `address_to_pin` not consulted.
- **Preserve:** explicit lat/lon wins over everything, `confidence=="authoritative"`.
- **Preserve:** nothing → 422.

### Unit — `test_property_domain_pin.py` (mock `lookup_parcel*`)
- `pin` supplied → `lookup_parcel_by_pin` used, `lookup_parcel` **not** called; summary
  carries that PIN.
- `pin` supplied but PIN row missing → falls back to `lookup_parcel(lat,lon)`.
- No `pin` → existing coordinate path unchanged (regression guard).

### Integration — `@pytest.mark.integration` (real Cook County portal)
- `address_to_pin("443 W Wrightwood Ave, Chicago, IL")` returns the **control** parcel
  `14331030110000` (the QA control).
- `address_to_pin` for the **EX** subject address → `14283190070000`.
- End-to-end `_resolve_location` for those addresses returns those PINs with
  `confidence=="authoritative"` — proving the wrong-neighbor bug is gone for the QA pair.

### Acceptance gate (Design §6) — held-out audit
- Reuse the R7 audit method (`report-status.md` §R7): held-out, **user-formatted** address
  sample; ground truth = `78yw-iddh`. Run the production path end-to-end; compare resolved
  PIN. **Target ≥90% exact-PIN.** Add the EX + control parcels. This is a scripted check
  (e.g. `eval/r7_audit.py`), not a pytest unit — gate **report** deploys on it.

---

## 5. Rollout plan

1. **Land behind tests, no flag.** The change is strictly safer: the new path only *wins*
   on a confident unique address→PIN match; every miss falls through to today's exact
   behavior. There is no regression surface that warrants a feature flag, but if desired,
   an optional `settings.address_point_resolution_enabled: bool = True` lets ops disable
   step 3 instantly (env var, no redeploy of code) — recommended as a cheap kill-switch.
2. **CI:** `python -m pytest backend/tests/ -q` (all green) + `cd frontend && npx tsc
   --noEmit` (no frontend code changed, but verify the optional response keys don't break
   types if the scorecard response is typed).
3. **Local verify:** run the acceptance audit against `localhost:8001` for the QA pair +
   held-out sample; confirm ≥90%.
4. **Deploy (requires Jack's confirmation — CLAUDE.md):** standard
   `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` on
   `178.105.184.66`. No migration, no schema change, no new env var required (kill-switch
   defaults on).
5. **Post-deploy smoke:** request a report/scorecard for the control address; confirm the
   resolved PIN on the artifact equals `14331030110000` and the cover shows the PIN
   (authoritative), not the approximate-match disclosure.

### Rollback
- **Code:** `git revert` the commit (single, self-contained) and redeploy — instant.
- **Operational (faster):** set `address_point_resolution_enabled=false` (if the
  kill-switch is included) → step 3 is skipped, resolver reverts to the exact
  pre-R7 geocode path. No data to undo (read-only feature, additive DB-less change).

---

## 6. Implementation-risk assessment (implementation only)

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `78yw-iddh` field/casing mismatch (`st_name` form, suffix handling) | Med | Confirmed schema live (`add_number/st_predir/st_name/lat/long`); `parse_chicago_address` already strips the suffix into `name`; integration test on the QA pair catches any mismatch before deploy. |
| Multi-match silently picks wrong PIN | Low | `$limit=2`; ≥2 distinct PINs → `None` (fall through). Unit-tested. Never an arbitrary pick (INV-3). |
| NamedTuple return breaks a missed caller | Low | Only 3 call sites + 1 test unpack the tuple (grep-verified); `mypy`/pytest catch any miss; field access is explicit. |
| Parcel dict shape drift between `lookup_parcel_by_pin` and `_lookup_parcel_socrata` | Low | New fn returns the identical key set; `_build_summary` is shape-driven and untested-path-free. Unit test asserts shape parity. |
| Address-point coverage gap (new construction, e.g. "2400 N Milwaukee") | Known/bounded | Miss → `confidence="approximate"` fallback (today's behavior) + INV-5 disclosure; never worse than status quo. |
| Extra Socrata call adds latency | Low | One cached GET on the existing portal/client; TTLCache 24h; on the resolution critical path but parallel to nothing it blocks. |
| Confidence field unused by frontend → confusion | Low | Additive optional fields; UI ignores them; only the PDF template reads `resolved_confidence`. |

**Out of scope (deferred per design §6, do not implement):** cached-polygon PIP store
(Arch C), rooftop geocoder, multi-match disambiguation UI, map-click PIP-by-containment
(step 2 PIP leg stays as-is until GIS returns).

---

## 7. Execution order

1. `config.py` — add `dataset_address_points` (+ optional limit, optional kill-switch).
2. `address_points.py` — `address_to_pin()` + its unit tests (`test_address_points.py`). Green.
3. `parcels.py` — `lookup_parcel_by_pin()`. 
4. `property/__init__.py` — `property_domain(*, pin=None)` branch + `test_property_domain_pin.py`. Green.
5. `main.py` — `_resolve_location` → `ResolvedLocation` NamedTuple + step-3 insertion +
   degraded log; update `test_resolve_location.py`. Green.
6. `main.py` — thread `pin`/`confidence` through `_fetch_scorecard_data`,
   `_fetch_report_data`, and the 3 call sites.
7. `models.py` + report template — INV-5 disclosure / PIN display.
8. Full suite + `tsc --noEmit`. Then `eval/r7_audit.py` acceptance (≥90% + QA pair).
9. Commit (single self-contained change), push. **Ask Jack before deploy.**
10. Deploy → post-deploy smoke on the control address → flip R7 to SHIPPED in
    `report-status.md`.
