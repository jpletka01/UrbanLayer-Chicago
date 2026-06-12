# SelectedParcel Unification

**Completed**: 2026-06-11
**Status**: Shipped to production (merged fast-forward to `main`, auto-deployed, verified via live API 2026-06-11)

## What Was Built

A frontend parcel-identity primitive that ends identity fragmentation across the assessment core (Scorecard/Chat/Report). Four phases, each one commit on branch `selected-parcel`:

- **Phase 0** (`7a610d6`) — Identity primitive + visible identity: `SelectedParcel`/`ParcelQuery` types, `SelectedParcelContext` (sole write site via `select()`), `resolved_lat`/`resolved_lon` added to `/api/scorecard`, Scorecard identity strip (PIN in mono linked to the Cook County Assessor + confidence badge: authoritative → "✓ Exact parcel match", approximate → amber).
- **Phase 1** (`2b0c8b1`) — Non-degrading handoffs + canonical `?pin=` URLs: Explorer clicks navigate by pin (normalized from dash-formatted display strings), Scorecard mount precedence pin → address → lat/lon, report download + access check keyed on `parcel.pin`.
- **Phase 2** (`82fd399`) — Money binds to PIN: db schema **v11** (nullable `pin` column on `report_purchases` + `(user_id, pin)` index, no backfill), `has_purchased_report` matches `pin = ?` OR the legacy 4-decimal coordinate cell (retained permanently), pin in Stripe metadata/purchase row/success URLs, checkout accepts pin-only bodies (resolves centroid server-side for the row's NOT NULL lat/lon), 13 new tests.
- **Phase 3** (`4c78986`) — Type enforcement: `fetchReport`/`createReportCheckoutSession`/`checkReportAccess` accept `SelectedParcel` and derive wire params internally (highest-fidelity key: pin → address → coords); `ReportPurchasePrompt` takes `parcel`; hand-assembled identity at all three report call sites deleted.

Plus docs commits `0886b38`, `865f8af`, `8b812c1` (status, findings, baseline refresh).

## Verification Results

- **Per-phase (pre-merge)**: tsc clean at every phase; 577 backend unit tests pass (565 pre-Phase 2). Browser-driven QA: Explorer row pin = URL pin = badge pin; `/api/report?pin=` intercepted from the download button; legacy `?address=` and `?lat&lon` URLs still work (coords → amber "Parcel identity unconfirmed"). Stripe test-mode end-to-end: checkout session by pin → Stripe metadata carries pin, success URL `?pin=…&report_purchased=1` → webhook completion (simulated with real retrieved session payload) → purchase row `status=completed` with pin → entitlement granted by pin despite 0.01° coordinate drift, unrelated pin rejected.
- **Post-deploy (live API, 2026-06-11)**: `GET /api/scorecard?pin=14331030110000` and `?address=642 W Belden Ave` both return `resolved_pin=14331030110000`, `resolved_confidence="authoritative"`, `resolved_lat`/`resolved_lon` present (Phase 0 markers prove the new image is serving). Served frontend bundle contains the "Exact parcel match" badge. Schema migration v11 ran additively at startup (prod schema verified sane during Phase 2).
- **QA parcels**: taxable control `14331030110000` = 642 W Belden Ave (authoritative by address and by pin); EX subject `14283190070000` (authoritative by PIN; see findings for the by-address drift).

## Key Decisions

- **One identity producer, one frontend holder.** Backend `_resolve_location` (precedence: explicit lat/lon → pin → address via Address Points → degraded geocode → 422) was already correct; the fix was a single frontend holder. The only `SelectedParcel` write in the codebase is inside `SelectedParcelContext.select()`, which commits backend response fields verbatim — identity is never constructed client-side.
- **Two-value confidence**: `"authoritative" | "approximate"`. No "exact" tier.
- **Surface contract**: Explorer emits intent only (`?pin=` navigation, no read); Scorecard is the sole creation site and renders identity; Chat is read-only (per-message `pin14` is history, not selection); Report consumes exclusively (request, entitlement, purchase all from `SelectedParcel.pin`).
- **Must-never-happen list** (binding for future work): no silent re-resolution when pin is known; no fidelity downgrade at handoffs (coords when pin exists, address when either exists); money never keyed on coordinates when a pin exists; no client-side identity construction; never display a pin detached from its confidence; never promote chat parcels to the selection.
- **Legacy entitlement retained forever**: pin-less purchase rows match via the coordinate OR-clause; no backfill. Legacy `?address=`/`?lat&lon` URLs honored at every phase.
- **React context + `useState` only** (AuthContext precedent) — no store library, no localStorage; the URL (`?pin=`) is the sole serialization. A second store would recreate the competing-sources problem.
- **Deliberately deferred** (separate known issues, not regressions): landing hero routes to chat; chat's area-vs-parcel intent split; Explorer Pro paywall; condo-stack pin10 ambiguity; chat map parcel handoff.

## Implementation Findings (worth preserving)

1. **Explorer pins are dash-formatted display strings** (`14-28-115-084-0000`, from `_format_pin` in `retrieval/explore.py`); `_resolve_location` 422s on that form. All pin handoffs normalize with `.replace(/\D/g, "")`. Any future pin-emitting surface must do the same (or the resolver should learn to strip non-digits). (Also in known-issues Gotchas.)
2. **Pin-only checkout resolves server-side.** A `{pin}`-only body to `/api/checkout/report` calls `_resolve_location(pin=...)` to fill the purchase row's NOT NULL `lat`/`lon` (kept for legacy coordinate entitlement). Pin-only rows have `address` NULL (display-only). The real frontend always sends pin+address+lat+lon, so resolution is skipped there — backend short-circuits on the explicit point.
3. **Address Points neighbor-parcel mis-resolution** (STILL OPEN — see known-issues.md): "443 W Wrightwood Ave" resolves *authoritative* to neighboring pin `14283180570000`, not the EX subject `14283190070000`; one cold-cache probe returned approximate/no-pin (resolver nondeterminism under transient Socrata failures). Purchases binding to the pin the user *saw* mitigates but doesn't fix mis-resolution at search time. QA the approximate badge via `?lat&lon` instead of by-address.
4. **Local dev DB was schema-corrupt (pre-existing)**: `schema_version` ahead of actual schema — missing the v9 `report_purchases` and v10 `events` tables (`executescript` implicitly commits, so a crashed init leaves the version row without the tables). Repaired locally by re-running idempotent migrations; production unaffected. `_migrate_v11` assumes `report_purchases` exists. (Also in known-issues Gotchas.)
5. **Dev-mode Stripe checkout fixtures**: `_DEV_USER` email `dev@localhost` was rejected by Stripe's `customer_email` validation (500ing every dev checkout) → changed to `dev@example.com` in `auth.py`; the synthetic dev user needs a `users` row for the `report_purchases.user_id` FK. (Also in known-issues Gotchas.)
6. URL canonicalization must carry over `report_purchased` (or post-purchase auto-download breaks) and keeps the previous `address` param when a pin-keyed re-entry resolves without one (pin-only scorecard responses have `address: null`).
7. `ScorecardResponse` lives in `frontend/src/lib/api.ts`, not `types.ts`.

## Files Changed

- `backend/main.py` — scorecard returns `resolved_lat`/`resolved_lon`; `checkout_report` accepts pin-or-(address+lat+lon); `report()`/`check_report_access` pass `pin=rl.pin` to entitlement.
- `backend/db.py` — migration v11; `save_report_purchase(..., pin)`; `has_purchased_report(..., pin=None)` with pin-OR-coordinate match.
- `backend/payments.py` — `create_report_checkout_session(pin)`: Stripe metadata, purchase row, pin-keyed success/cancel URLs.
- `backend/auth.py` — `_DEV_USER` email fix; `handle_me` reads from `_DEV_USER`.
- `backend/tests/test_payments.py` — 13 new tests (entitlement matrix, checkout endpoint, Stripe session units).
- `frontend/src/lib/api.ts` — `resolved_*` fields on `ScorecardResponse`; report API functions take `SelectedParcel`.
- `frontend/src/lib/types.ts` — `SelectedParcel`, `ParcelQuery`.
- `frontend/src/contexts/SelectedParcelContext.tsx` — new; sole write site.
- `frontend/src/main.tsx` — provider mount.
- `frontend/src/pages/ScorecardPage.tsx` — `select()`-driven search, identity strip, mount param precedence, canonical URL, pin-keyed download/checkout.
- `frontend/src/pages/ExplorePage.tsx` — pin-keyed navigation (map + table clicks).
- `frontend/src/components/ReportPurchasePrompt.tsx` — takes `parcel`.
- Docs: `frontend/CLAUDE.md`, `claude-context/core/architecture.md` ("Parcel Identity" section), `claude-context/core/known-issues.md`.

## Full Original Plan (spec as executed)

### System truth at plan time (2026-06-11)

- Backend had one correct identity producer (`_resolve_location` → `ResolvedLocation(lat, lon, address, pin, confidence)`); `/api/scorecard` already returned `resolved_pin`/`resolved_confidence`, which the frontend ignored. `?pin=` was already accepted by scorecard/report endpoints; zero frontend callers sent it.
- The frontend had no "currently selected parcel" state — seven competing partial representations (URL params, page state, per-message chat context, purchase rows, Explorer rows, tracking layer, backend per-request). Identity was re-resolved 4+ times per journey and downgraded at every handoff (PIN→coords at Explorer, identity→address-string at report download).
- Purchase entitlement was keyed on a 4-decimal coordinate cell (~11 m), wider than a Chicago lot (~7.6 m); `report_purchases` had no PIN column.

### Identity model

```ts
export interface SelectedParcel {
  pin: string | null;
  confidence: "authoritative" | "approximate";
  lat: number;
  lon: number;
  address: string | null;
}
export type ParcelQuery =
  | { pin: string }
  | { address: string }
  | { lat: number; lon: number };
```

Field classes: `pin`/`confidence` authoritative (set only from backend response fields); `lat`/`lon` derived (map anchor; lookup key only when pin is null); `address` display-only. Creation: exactly one site — `select(query)` calls `fetchScorecard(query)` and commits the response atomically. Updates: only a new `select()`; refresh re-enters via `?pin=` → backend PIN precedence → identical parcel.

### Strategic context (non-binding, from the originating audit)

UrbanLayer turns a Chicago address into one verified parcel's complete public-record assessment, sold at the moment a professional needs it in writing; Scorecard/Chat/Report are three fidelity levels of one assessment. The dominant cause of perceived fragmentation within the assessment core was the absence of a held, visible parcel identity in the frontend (one producer, four consumers, zero holders). North-star Phase 2 (customer validation) remains the governing priority; this plan was the minimal correctness/trust fix worth doing alongside it.
