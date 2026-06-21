# PIN-Resolver Disagreement — Investigation (read-only)

**Date:** 2026-06-21 · Follow-up to `2026-06-21_full-site-sweep.md` Finding #1 · **No code changed.**
**Verdict in one line:** The proposed quick fix ("promote `property.pin14` into `resolved_pin`") is **UNSAFE** — in both disputed cases the orchestrator's `pin14` is a **neighboring parcel**, and the top-level `null`/`approximate` is the **correct** answer. This is a real reconciliation task, not a 1-hour promotion. It also uncovered a **separate live bug** in the Socrata bbox fallback (dense-area truncation returns wrong parcels).

---

## 1. The two resolver paths (mapped)

### Path A — top-level `resolved_pin` (`/api/scorecard`)
`main.py:1539` → `_resolve_location()` (`main.py:1284`). Strict precedence:
1. explicit lat/lon → authoritative (`main.py:1306`)
2. supplied PIN → authoritative centroid (`main.py:1311`)
3. **address → PIN via Cook County Address Points `78yw-iddh`** (`address_to_pin`, `address_points.py:37`) → authoritative
4. **degraded fallback**: geocode only → `pin=None, confidence="approximate"` (`main.py:1356-1368`)

`address_to_pin` returns a PIN **only on a unique, confident match** and returns `None` on no-match, unparseable, **or multi-match (≥2 distinct PINs)** (`address_points.py:90-101`). `78yw-iddh` is the address→PIN system-of-record and is **independent of the broken GIS spatial index** — this is the R7 mechanism that fixed the ~77% wrong-parcel rate.

### Path B — `property.pin14` (property orchestrator)
`_fetch_scorecard_data` calls `property_domain(resolved_lat, resolved_lon, pin=rl.pin, …)` (`main.py:1391`). When `rl.pin` is `None` (the degraded case), the orchestrator resolves its own parcel from the point via `lookup_parcel(lat, lon)` (`parcels.py:45`):
1. `_lookup_parcel_gis` — ArcGIS point-in-polygon (`parcels.py:133`). **Authoritative when up**, but currently returns nothing (verified below).
2. `_lookup_parcel_socrata` — **bbox query on Parcel Universe `pabr-t5kh`, picks `min(distance²)` = nearest centroid** (`parcels.py:193`, selection at `parcels.py:227`). This is the *same* approximate nearest-centroid mechanism R7 replaced.

### Why they diverge — root cause
Path A asks "what PIN does this **address** map to?" (authoritative table). Path B asks "what parcel is **nearest to this point**?" (spatial). When the address is **absent from `78yw-iddh`**, Path A correctly degrades to `approximate`; Path B's nearest-centroid still returns *something* — and that something is frequently the wrong parcel.

The `null` is a **correct rejection**, not a dropped result. Confirmed live below.

---

## 2. Live verification against ground truth

GIS point-in-polygon at both disputed geocodes → **0 features** (GIS down) ⇒ the **Socrata nearest-centroid fallback is what produced every `property.pin14`** here.

```
GIS /MapServer/44/query @ (41.92886,-87.64159) [Deming]    → features: 0
GIS /MapServer/44/query @ (41.92477,-87.70051) [Milwaukee] → features: 0
```

### Forward lookups in Address Points `78yw-iddh` (what Path A sees)
| input | `78yw-iddh` rows | Path A result |
|-------|------------------|---------------|
| `2400 N MILWAUKEE` | **0** | None → approximate (correct) |
| `481 W DEMING` | **0** | None → approximate (correct) |
| `642 W BELDEN` | **1** → pin `14331030110000`, "642 WEST BELDEN", Chicago | authoritative ✓ |

### Reverse lookups (what the orchestrator's PIN actually *is*)
| orchestrator `pin14` | `78yw-iddh` address | `pabr-t5kh` class | reality |
|---|---|---|---|
| `13253220380000` (Milwaukee) | **2401 & 2403** N Milwaukee (odd side) | 597 (commercial) | input was **2400** (even) → **across-the-street parcel** |
| `14283180160000` (Deming) | **470** W Deming | 210 (residential) | input was **481** (odd) → **wrong-side / different parcel** |
| `14331030110000` (Belden) | 642 W Belden | — | matches input ✓ |

### Block context proves the wrong-side error
- **Deming:** even side = PIN group `1428318xxx` (470/472/474/476/480), odd side = `1428319xxx` (477→`…19002`). Input `481` is **odd** ⇒ true parcel is in the `…19` group. The **documented ground-truth `14283190070000` (`…19007`) is class `EX`** (the exempt subject from the report-verification parcels) at `(41.92874,-87.64145)`. The orchestrator returned `…18016` = 470 (even side, class 210). Different parcel, different class, wrong side.
- **Milwaukee:** Address Points around 2400 are `2401/2403→13253220380000`, `2405→…370000`, `2410→…260110000`. No `2400` exists in `78yw-iddh`; the orchestrator grabbed the 2401/2403 commercial parcel across the street.

### Distance — how the wrong parcel was chosen
The orchestrator's pick sits ~25–35 m from the geocoded fallback point — textbook nearest-centroid grabbing an adjacent lot:
```
2400 N Milwaukee: geocode (41.92477,-87.70051) → pick 13253220380000 @ 23 m  (2401/2403, across street)
481 W Deming:     geocode (41.92886,-87.64159) → pick 14283180160000 @ 29 m  (470, wrong side)
```

### The Deming case also exposes a **separate bug** (dense-area truncation)
Replaying `_lookup_parcel_socrata`'s bbox (`±0.002°` ≈ 220 m) against `pabr-t5kh`:
- **Deming bbox returned the full 2000-row cap** (`limit_ccao_parcels=2000`, `config.py:88`) and the query has **no `$order`** (`parcels.py:201-208`). The true-nearest parcel — documented `14283190070000`, only ~18 m away — was **truncated out of the candidate set entirely** (`documented … NOT in bbox candidate set`). So `min(distance²)` was taken over an *arbitrary* 2000 parcels that excluded the real one, and returned 470 (34 m) as "nearest."
- **Milwaukee bbox returned only 271 parcels** (not truncated); nearest-centroid legitimately picks the across-street 2401/2403 because no `2400` parcel point is nearer.

The code already *logs* this case (`parcels.py:222` "nearest parcel may be approximate (dense/condo area)") but **still returns the wrong parcel as a normal result**, with no signal propagated to the caller or user.

---

## 3. Per-address verdict

| address | `resolved_pin` (Path A) | `property.pin14` (Path B) | true parcel | evidence | failure class |
|---|---|---|---|---|---|
| 2400 N Milwaukee Ave | `None` / approximate ✅ correct | `13253220380000` ❌ = 2401/2403 N Milwaukee (across street, class 597) | ≠ Path B (no `2400` in `78yw-iddh`; true even-side parcel unconfirmed) | `78yw-iddh` 2400→0 rows; reverse 13253220380000→2401/2403; nearest-centroid 23 m across street | **(a)** orchestrator returns wrong neighbor; strict resolver correctly refuses |
| 481 W Deming Pl | `None` / approximate ✅ correct | `14283180160000` ❌ = 470 W Deming (class 210) | `14283190070000` (class EX, documented GT, ~18 m) | `78yw-iddh` 481→0 rows; reverse 14283180160000→470; **bbox truncated at 2000, true parcel dropped** | **(a)** orchestrator returns wrong neighbor via dense-bbox truncation; strict resolver correctly refuses |
| 642 W Belden Ave | `14331030110000` ✅ authoritative | `14331030110000` ✅ agree | `14331030110000` | `78yw-iddh` 642 W Belden→single clean PIN | **correct** — gold-standard round-trip |

**Failure class is (a) in both disputed cases:** the orchestrator returns a *wrong* (neighbor) PIN that the strict resolver correctly refuses. There is **no** instance here of class (b) (orchestrator right, top-level wrongly dropping it).

---

## 4. Recommended fix shape for Finding #1

**Do NOT promote `property.pin14` into `resolved_pin`.** It is produced by nearest-centroid (or a truncated nearest-centroid), the exact mechanism R7 replaced; promoting it converts a correct "approximate" disclosure into a confidently-wrong parcel identity on a due-diligence product — the worst outcome. Belden would round-trip fine, but Milwaukee and Deming would both ship a neighbor as "✓ Exact."

**Which resolver wins:** Address Points (`78yw-iddh`) stays authoritative. The orchestrator's spatial `pin14` is *approximate context only* and must never become confirmed identity without an **address round-trip check**.

Concretely, in priority order:

1. **Gate any promotion on a reverse address-match (the safe reconciliation).** Before trusting `property.pin14`, reverse-resolve it (`pin_to_address` / `78yw-iddh` by pin) and accept only if the resulting street number+direction+name (and **parity**) matches the input address. Milwaukee (2401/2403≠2400) and Deming (470≠481) both fail this and stay `approximate`; Belden (642=642) passes. This lets the rare correct case promote while blocking neighbors. **Confidence is downgraded, identity is not dropped:** keep `resolved_pin=null, confidence="approximate"`, and surface the orchestrator parcel only as an explicitly-labeled "nearest parcel (unverified)".

2. **Fix the dense-area truncation in `_lookup_parcel_socrata` (its own bug, see §5).** Until fixed, `pin14` in dense neighborhoods (Lincoln Park, the Loop, condo blocks) can be a parcel that *isn't even the nearest* — so even nearest-centroid logic can't be trusted there.

3. **Treat the underlying gap as data coverage, not logic.** `2400 N Milwaukee` and `481 W Deming` are simply absent from `78yw-iddh` while their block-mates are present. Options (each needs validation, none is a blind promote): (a) same-block, same-parity nearest-address interpolation within `78yw-iddh`; (b) periodic check of `78yw-iddh` coverage on the marketing/demo addresses; (c) at minimum, **swap the homepage's flagship example to an address that round-trips** (Belden does) so the demo isn't "Unconfirmed".

4. **Caveat the per-card data when identity is approximate.** Even with the top-level "approximate" badge, the Scorecard currently renders Property/tax/assessment/comps for the *specific* (wrong) neighbor PIN with no per-card caveat. When `resolved_pin` is null but `property.pin14` was used, those cards should carry a "based on nearest parcel — may differ" note (or be suppressed).

---

## 5. New bug uncovered (file separately)

**`_lookup_parcel_socrata` returns wrong parcels in dense areas — silent.** Severity **P2** (correctness, dense neighborhoods).
- **Where:** `backend/retrieval/property/parcels.py:193-235`.
- **What:** the bbox query (`±0.002°`, `$limit=2000`, **no `$order`**) can return a truncated, *unordered* candidate set in dense areas; `min(distance²)` is then taken over a set that may **exclude the true-nearest parcel**, returning a neighbor. Proven live: for `481 W Deming` the true parcel (`14283190070000`, ~18 m) was absent from the 2000-row candidate set and `470 W Deming` (34 m) was returned.
- **Blast radius:** this `pin14` flows into the property domain's characteristics, assessment history, tax estimate, and comparable-sales seed — so a wrong neighbor PIN yields a Scorecard whose Property/tax/comps describe the **wrong parcel**, even when the top-level badge says "approximate".
- **Fix direction (not applied):** order server-side by distance (`$order=distance_in_meters(...)` if a geom/point column is available, else a computed expression) and take `$limit` small; OR shrink `_BBOX_DELTA` with empty-result expansion; AND when the cap is hit, **don't return a confident nearest** — return `None`/strongly-flagged so the caller treats identity as unresolved rather than wrong.

---

*Read-only investigation. Only this findings file was created (plus a cross-link added to Finding #1 of the sweep). No product code touched.*
