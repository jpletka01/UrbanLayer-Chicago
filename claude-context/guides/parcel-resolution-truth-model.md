# Parcel Resolution — Canonical Truth Model & Design Spec

**Status:** DESIGN OF RECORD (decided 2026-06-11). Supersedes the ad-hoc resolution
behavior described across R5/R6/R7 in `report-status.md`. **No code yet** — this doc
defines the target before implementation.

**Problem being closed:** R7 — under the current (indefinite) Cook County GIS outage,
address-typed report/scorecard requests resolve the **wrong parcel ~77%** of the time
(n=111 audit). Root cause is architectural, not a tuning bug: **the pipeline is
coordinate-driven and re-derives parcel identity from a geocoded point**, instead of
being keyed by the parcel's authoritative unique key (PIN).

---

## 1. Truth Model — what is authoritative

A Cook County parcel has exactly one authoritative identity: its **14-digit PIN**. Every
downstream fact the report renders (class, characteristics, assessments, sales, tax,
ownership signals, zoning interpretation) is keyed by PIN. Therefore:

> **The PIN is the system-of-record primary key for a parcel. Address and lat/lon are
> not identities — they are *inputs from which a PIN must be derived*.**

### Authority ranking of the three inputs

| Input | What it actually is | Authority for *identity* |
|-------|--------------------|--------------------------|
| **PIN** | The parcel's unique key | **Authoritative** — it *is* the parcel |
| **Address** | A label that maps 1:1→PIN via an authoritative dataset | Authoritative **only after** mapping to a PIN via Address Points (`78yw-iddh`) |
| **lat/lon** | A *locator*, not an identity | Authoritative **only by containment** (point-in-polygon). Never by proximity. |

### Source-of-truth datasets

| Question | Authoritative source |
|----------|----------------------|
| What is the parcel's identity? | **PIN14** (Cook County) |
| What PIN does this address belong to? | **Cook County Address Points `78yw-iddh`** (address→PIN→lat/long, GIS-index-independent) |
| What are this PIN's attributes? | CCAO Parcel Universe `pabr-t5kh` + CCAO characteristics / assessments / sales / tax (all keyed by PIN) |
| What PIN contains this point? | Cook County GIS layer 44 point-in-polygon (when up); cached-polygon PIP (future) |
| What is this PIN's geometry/centroid? | GIS layer 44 (when up); Parcel Universe `lat/lon` centroid (degraded — centroid only, no polygon) |

### Conflict rules (when inputs disagree)

1. **PIN beats everything.** A supplied PIN is never overridden by a co-supplied address
   or by geocoded coordinates. (This was R6.)
2. **Address resolves *to* a PIN, then the PIN is the identity.** Address never directly
   selects a parcel.
3. **lat/lon resolves to a PIN by containment only.** A map-click point lands *inside* its
   parcel; that is authoritative via PIP. A *geocoded* point (from a typed address) is
   street-interpolated and offset ~30 m — it must not select a parcel by nearest-centroid
   except as a last-resort, explicitly-flagged fallback.
4. **More-authoritative never loses to less-authoritative.** No equal-weight voting among
   sources — they are not peers (see §3, Hybrid).

---

## 2. Where the current system violates the model

```
_resolve_location(address)          # returns (lat, lon) — PIN is DISCARDED here
  → geocode_address                 # Census street-interpolated point, ~30 m off-parcel
  → _fetch_report_data
  → _fetch_scorecard_data
  → property_domain(lat, lon)       # coordinate-driven
  → lookup_parcel(lat, lon)         # GIS PIP is DOWN → _lookup_parcel_socrata
  → nearest Parcel-Universe centroid in a ~220 m bbox
  → WRONG parcel (~4 lots away; Chicago lots ~7.6 m wide)
```

Two compounding defects:
- **D-identity:** parcel identity is re-derived from coordinates instead of being carried
  as a PIN. `_resolve_location` even *has* the PIN path but throws the PIN away, returning
  only `(lat, lon)`. The entire pipeline below it is coordinate-keyed.
- **D-locator:** with GIS down, lat/lon→PIN degrades from *containment* (PIP) to
  *proximity* (nearest-centroid), which is wrong by construction for an offset point.

R5 raised the cap on the nearest-centroid search, but that was insufficient — a dense-block
bbox still hit the (raised) cap unordered and truncated out the true nearest, returning a
neighbor; **2026-06-21** fixed this properly with server-side distance ordering + a reverse
round-trip gate that keeps a nearest-centroid PIN from becoming identity unless it matches
the input address (see step 4 and `archive/2026-06-21_pin-resolution-seam.md`).
R6 fixed only the PIN-vs-address precedence *when a PIN is also passed*.
Neither touches the dominant path — a user typing an address — because the frontend sends
no PIN and the address still becomes coordinates.

---

## 3. Resolution architectures — evaluation

The meta-decision (PIN is the primary key) is fixed by §1. The architectures differ in
**how the PIN is obtained from each input**. Evaluated against the named criteria:

### A. PIN-first (thread the PIN; resolve by PIN, no coord round-trip)
- **GIS outage:** Excellent *if a PIN is present* — PIN→data is pure Socrata, GIS-independent.
- **Partial data:** Robust; PIN is unique, zero ambiguity.
- **Failure modes:** Says nothing about *how to get a PIN from a typed address* — and the
  production frontend sends no PIN. Standalone impact on the 77% failure ≈ **0**.
- **Op risk:** Low. **Complexity:** S–M (plumbing).
- **Verdict:** **Necessary backbone, insufficient alone.** It is the *delivery mechanism*
  for B, not a fix on its own.

### B. Address-point-first (address→PIN via `78yw-iddh`, then resolve by PIN)
- **GIS outage:** **Excellent** — fully independent of the broken GIS spatial index; the
  dataset *is* the authoritative address→PIN map. This is the property that kills R7.
- **Partial data:** Bounded by dataset coverage/freshness (new construction lags; the
  flagship "2400 N Milwaukee" had no point) and address-parser robustness → needs a fallback.
- **Failure modes:** ambiguous/range/half addresses, unit suffixes, unparseable strings,
  missing points. All are *"no confident match"* → fall through, never *wrong match*.
- **Op risk:** Low–Med (one more Socrata dataset, same client/portal, TTLCache; no infra).
- **Complexity:** M.
- **Verdict:** **RECOMMENDED primary** for the address path. Ceiling ~100% (authoritative,
  unique in the n=111 sample); realistic ~85–95% bounded by parser + coverage.

### C. Geometry-first / PIP (point-in-polygon)
- **GIS outage:** **Fails** — GIS *is* the PIP engine and it is down. A cached-polygon PIP
  store could substitute, but a street-interpolated geocode point often falls in the
  street or neighbor polygon, so PIP still mis-assigns for *typed* addresses.
- **Partial data:** Needs full, fresh polygon coverage cached locally.
- **Failure modes:** geocoder offset → point in wrong polygon; missing geometry.
- **Op risk:** **High** (bulk geometry store + refresh + spatial index).
- **Complexity:** L–XL.
- **Verdict:** Correct *in principle* and the right path for **map-click lat/lon** (the
  point is genuinely inside the parcel) — but **defer the cached-polygon build**; it is
  heavy and does not solve the geocoder-offset problem that drives R7.

### D. Hybrid voting / fallback
- **GIS outage:** Excellent **iff** ordered so authoritative sources lead and degraded
  ones only fill gaps / break ties.
- **Partial data:** Best resilience — each source covers the others' gaps.
- **Failure modes:** The trap is **equal-weight voting**: the sources are *not peers*.
  Letting three proximity guesses outvote one authoritative key reproduces the R6 class of
  bug (a weaker signal overriding a stronger one). Voting is the wrong primitive here.
- **Op risk:** Med. **Complexity:** M (ordered fallback) → L (true voting).
- **Verdict:** Adopt the **ordered-fallback** form, **reject voting**. The shipped resolver
  is a strict precedence chain, not a vote.

---

## 4. Decision — system of record

**Adopt a PIN-keyed identity model with a single strict-precedence resolver** that derives
the PIN from the most authoritative available input and **threads that PIN through the
entire pipeline**. Concretely this is **A (backbone) + B (primary address strategy) + C
(only for map-click lat/lon, GIS-PIP when it returns) + an ordered fallback (D-ordered)** —
**not** voting, **not** coordinate re-derivation.

### Explicit answers to the three questions

**Q1 — Thread PIN through the pipeline, or treat as authoritative primary key?**
**Both, and they are the same requirement.** PIN is the primary key, and *because* it is,
it must be threaded. Today it dies in `_resolve_location` (returns only `lat,lon`). Target:
the resolver returns a **PIN** (plus lat/lon for maps as metadata), and the downstream
functions (`_fetch_*_data` → `property_domain` → `lookup_parcel`) accept a PIN and **skip
coordinate re-derivation** when one is present.

**Q2 — Should address ever resolve a parcel without PIN confirmation?**
**No.** An address must always resolve to a PIN first (authoritatively via `78yw-iddh`),
and the PIN is the identity. The current "address → geocode → nearest-centroid → implicit
PIN" is exactly the banned pattern. Address→geocode→PIP is permissible **only** as a
degraded fallback and **must be flagged low-confidence**.

**Q3 — Minimal change that eliminates the 77% failure mode?**
**Insert one authoritative `address→PIN` lookup (`78yw-iddh`) ahead of the
geocode-and-nearest-centroid path, and resolve the parcel by that PIN.** That single
insertion removes the dominant failure mode; threading the PIN downstream (A) is its
delivery mechanism. Nothing else in the report needs to change to stop describing the wrong
parcel.

---

## 5. Recommended design (the spec)

### Resolution order (strict precedence — first confident match wins)

For any request carrying any of `{pin, address, lat, lon}`, produce a **resolved PIN** and
a **confidence tier**:

1. **`pin` supplied** → resolve **by PIN** directly (Parcel Universe / CCAO). `lat/lon` for
   maps comes from the PIN's centroid. → **confidence = authoritative**.
2. **`lat`+`lon` supplied from a deliberate point** (map/Explorer click) → **PIP
   containment** via GIS layer 44. On a hit → PIN. → **confidence = authoritative**.
   (If GIS is down and no cached-polygon PIP exists, fall to step 4's degraded path but
   keep the click point.)
3. **`address` supplied** → **Address Points `78yw-iddh`** lookup (parse via
   `parse_chicago_address`) → unique PIN → resolve by PIN. → **confidence = authoritative**.
4. **Degraded fallback** (only when 1–3 yield no confident PIN): `geocode_address` → point
   → GIS PIP if it returns, else **nearest Parcel-Universe centroid**.
   → **confidence = approximate**, `resolved_pin = null`. The geocoded location/address
   **must be surfaced for user verification**, and this path is logged/counted.
   **The nearest-centroid PIN is NOT promoted to identity by default (2026-06-21).** The
   property orchestrator still resolves it (to fill property/tax/comps), but `/api/scorecard`
   promotes it to `resolved_pin`/`authoritative` **only when it passes a reverse round-trip**
   (`parcel_address_matches`: the candidate PIN's own Address Points must match the input on
   number + direction + parity). Otherwise the PIN stays withheld and the response carries
   `nearest_parcel_unverified=true` so the UI caveats the parcel-specific cards (they describe
   the nearest parcel, possibly a neighbor). The nearest-centroid search itself now orders by
   distance **server-side** (`pabr-t5kh` `$order`) so a dense-block row cap can't truncate out
   the true nearest (the old unordered cap returned a *neighbor* — e.g. 470 vs 481 W Deming);
   it refuses on a full cap if ordering is unavailable. See
   `archive/2026-06-21_pin-resolution-seam.md`.
5. **No resolution** → `422`, ask for a different format or a map pin.

### Fallback rules

- Each step falls through to the next **only on "no confident match"**, never on "a guess."
- A multi-match in step 3 (e.g. address range, missing unit, building with many PINs) is
  **not** a confident match → fall through (or, later, prompt to disambiguate). Never pick
  arbitrarily.
- Steps 1–3 are GIS-independent (pure Socrata) and remain correct throughout the GIS outage.
  Only step 2's PIP and step 4's PIP leg depend on GIS; both degrade safely.

### Invariants (must always hold)

- **INV-1:** Every report/scorecard is rendered for **exactly one PIN**, and that PIN is
  recorded and **displayed on the artifact**.
- **INV-2:** The downstream data pipeline is **keyed by PIN**, never by a re-derived bare
  lat/lon, whenever a PIN is available.
- **INV-3:** A more-authoritative input **never loses** to a less-authoritative one
  (PIN > PIP-containment > address-point > nearest-centroid). No equal-weight voting.
- **INV-4:** lat/lon selects a parcel **only by containment**, never by proximity — except
  the step-4 degraded fallback, which is explicitly flagged.
- **INV-5:** When resolution is degraded (fell to step 4), the artifact **discloses it**
  ("approximate parcel — verify the PIN/address") rather than rendering silently as fact.
- **INV-6:** A supplied `pin` is never overridden by a co-supplied `address` or geocode
  (R6, already fixed in `_resolve_location` precedence — preserve it).

### Authoritative sources (recap)

- Identity: **PIN14**.
- address→PIN: **`78yw-iddh`** (Cook County Address Points).
- PIN→attributes: **`pabr-t5kh`** + CCAO characteristics/assessments/sales/tax.
- lat/lon→PIN: **GIS layer 44 PIP** (when up) → cached-polygon PIP (future) → nearest
  centroid (flagged).
- PIN→geometry/centroid: **GIS layer 44** (when up) → Parcel Universe centroid (degraded).

---

## 6. What this implies for implementation (next session — not now)

- `_resolve_location` returns a **resolved PIN + confidence**, not just `(lat, lon)`.
- A new `address→PIN` resolver over `78yw-iddh` (reuse `parse_chicago_address`,
  shared `socrata_get`, TTLCache) inserted as step 3.
- `property_domain` / `lookup_parcel` accept an optional **PIN** and resolve by it,
  bypassing coordinate re-derivation when present.
- Confidence tier threaded to the report/scorecard for the INV-5 disclosure.
- **Acceptance:** re-run the R7 audit harness on a held-out, user-formatted address sample,
  target **≥90% exact-PIN**, plus the EX (`14283190070000`) + control (`14331030110000`)
  QA parcels. Gate future *report* deploys on this.

### Deliberately deferred (do not block R7 on these)
- Cached-polygon PIP store (Architecture C build) — heavy, doesn't solve geocoder offset.
- Parcel-accurate (rooftop) geocoder — complementary, not primary.
- Disambiguation UI for multi-match addresses — fall-through is correct in the interim.
