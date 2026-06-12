# SelectedParcel Unification — Canonical Handoff Artifact

Plan date: 2026-06-11. Status: **Phases 0+1 implemented & verified 2026-06-11 on branch `selected-parcel` (commits `7a610d6`, `2b0c8b1`) — not pushed, awaiting Jack's review. Phases 2+3 not started. See §8 for implementation findings that amend §5's literal steps.**
Origin: full product/architecture audit → identity-fragmentation analysis → state-model grounding (this document is the compressed output; it supersedes the conversation that produced it).
This artifact is the sole input for the implementation session. Where it conflicts with code comments, older docs, or intuition, this artifact wins.

## 1. System Truth Summary

- UrbanLayer is a Chicago parcel-assessment engine: address in → resolved parcel identity → assembled public-record assessment, rendered at three fidelities (free Scorecard, chat explainer, paid $25 PDF report).
- The backend has one correct identity producer: `_resolve_location` (`backend/main.py:1127`) → `ResolvedLocation(lat, lon, address, pin, confidence)`, strict precedence: explicit lat/lon → supplied PIN → address→PIN via Cook County Address Points → degraded geocode → 422.
- Confidence is a **two-value system**: `"authoritative" | "approximate"`. No `"exact"` tier exists. Do not invent one.
- `/api/scorecard` already returns `resolved_pin` and `resolved_confidence` (`main.py:1371–1372`). The frontend receives and ignores both; they are absent from `types.ts`.
- `/api/scorecard` and `/api/report` already accept `?pin=` (`api.ts:540,561` already declare it client-side). Zero frontend callers send it.
- The frontend has **no** "currently selected parcel" state. Seven competing partial representations exist (URL params, page state, per-message chat context, purchase rows, Explorer rows, tracking layer, backend per-request).
- Identity is re-resolved 4+ times per user journey and downgraded at every handoff (PIN→coords at Explorer, identity→address-string at report download).
- Purchase entitlement is keyed on a 4-decimal coordinate cell (~11 m), wider than a Chicago lot (~7.6 m). `report_purchases` has no PIN column.
- Production deploys automatically on push to `main`. QA parcels: EX subject `14283190070000` (no address point — resolves `approximate` by address; QA it by PIN), taxable control `14331030110000` = 642 W Belden Ave (resolves `authoritative`).

## 2. Identity Model (Final)

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

**Field classes:** `pin`, `confidence` — authoritative, set only from backend response fields, never computed client-side. `lat`, `lon` — derived; map anchor; lookup key only when `pin` is null. `address` — display-only; never a lookup key once SelectedParcel exists.

**Creation:** exactly one site — `SelectedParcelContext.select(query)` calls `fetchScorecard(query)` and commits `{resolved_pin, resolved_confidence, resolved_lat, resolved_lon, address}` from the response. The set-state inside `select` is the only write in the codebase. All user actions (Explorer click, address search, URL load) produce a `ParcelQuery`, never a `SelectedParcel`.

**Updates:** only a new `select()`. Responses replace the whole object atomically — no field merging. Refresh re-enters via `?pin=` → backend PIN precedence → identical parcel guaranteed.

**Must never happen:**
1. Silent re-resolution when `pin` is known.
2. Fidelity downgrade at any handoff (coords when pin exists; address when either exists).
3. Money/entitlement keyed on anything but `pin` when pin exists.
4. Client-side construction of a SelectedParcel from input, URL, or Explorer rows.
5. Displaying/propagating a pin detached from its confidence tier.
6. Promoting chat's per-message parcels to the current selection.

## 3. Surface Responsibilities

| Surface | READ | WRITE | IGNORE |
|---|---|---|---|
| **Explorer** | No | Intent only: click emits `ParcelQuery{pin}` (navigate `?pin=`) | Current selection while browsing |
| **Scorecard** | Yes — renders pin + confidence badge + standardized address as header truth | **Sole creation site** via `select()` | — |
| **Chat** | Yes (read-only; per-message `pin14` is history, not selection) | Never | Area-mode questions |
| **Report** | Exclusively — request, entitlement, purchase all from `SelectedParcel.pin` | No | — |

Landing/pricing: neither read nor write (pre-selection surfaces).

## 4. Critical Violations (Condensed)

1. **PIN discard at Explorer handoff** — known PIN converted to coords at click (`ExplorePage.tsx:179, 325`).
2. **Address-string report purchase** — full identity held, address sent; report re-resolves at payment time (`ScorecardPage.tsx:142`).
3. **Ignored identity fields** — `resolved_pin`/`resolved_confidence` shipped on every scorecard response, never typed or rendered.
4. **Coordinate-cell entitlement** — purchases stored/matched on `ROUND(lat,4)` (`db.py:1154`), no PIN column (`db.py:167–180`); Stripe metadata and success URL carry address+rounded coords (`payments.py:77, 82–84`).
5. **Unreconciled multi-resolution** — every fetch site independently re-resolves; no reuse anywhere.

## 5. Implementation Plan (Phased)

Each phase = one commit, independently shippable, fully reversible by revert. Legacy URLs and purchase rows remain honored at every stage.

### Phase 0 — Primitive + visible identity (additive; ~150 LOC)
1. `backend/main.py` `scorecard()` (~`:1371`): add `data["resolved_lat"] = rl.lat; data["resolved_lon"] = rl.lon`.
2. `frontend/src/lib/types.ts`: add `resolved_pin`, `resolved_confidence`, `resolved_lat`, `resolved_lon` to the scorecard response type; add `SelectedParcel`, `ParcelQuery` exactly as in §2.
3. New `frontend/src/contexts/SelectedParcelContext.tsx` (~70 lines, mirror `AuthContext.tsx` pattern: `useState` in a context, no store library): `{ parcel, select }`, `select` as defined in §2.
4. `frontend/src/main.tsx:38`: mount `<SelectedParcelProvider>` inside `<AuthProvider>`.
5. `ScorecardPage.tsx`: `doSearch` (`:170`) uses `select()`; page keeps local `data` for content. Identity strip under header (`:304`): PIN in mono linked to `https://www.cookcountyassessor.com/pin/{pin}` (same convention as PDF, `zoning_report.html:419`); badge — `authoritative` → "✓ Exact parcel match"; `approximate` → amber "Approximate — parcel not confirmed"; `pin===null` → amber "Parcel identity unconfirmed".

**Verify:** `npx tsc --noEmit`; `/scorecard?address=642 W Belden Ave` shows `14331030110000` + authoritative; EX subject by address shows approximate.

### Phase 1 — Non-degrading handoffs + canonical `?pin=` URL (frontend; ~40 LOC)
1. `ExplorePage.tsx:179` and `:325`: `navigate(\`/scorecard?pin=${p.pin}\`)`.
2. `ScorecardPage.tsx` mount effect (`:196–198`): param precedence `pin → address → lat/lon` → `ParcelQuery` → `select()`. After successful commit with non-null pin: `setSearchParams({pin, address}, {replace:true})`. Pin-less results keep original params.
3. `ScorecardPage.tsx` `triggerDownload` (`:142,157–159`): `fetchReport(parcel.pin ? {pin: parcel.pin} : {address: parcel.address!})`; same keying for the access check.
4. `api.ts` `checkReportAccess` (`:157`): add `pin?: string`, pass through (backend `main.py:4425` already accepts it).

**Verify:** Explorer click → URL pin = clicked-row pin = Scorecard badge pin; refresh on `?pin=` reproduces parcel; report request logs `/api/report?pin=`; legacy `?address=` URLs still work.

### Phase 2 — Money binds to PIN (backend; ~120 LOC + migration + tests)
1. `backend/db.py`: migration **v11** — `ALTER TABLE report_purchases ADD COLUMN pin TEXT` + index `(user_id, pin)`. `save_report_purchase(..., pin)`. `has_purchased_report(user_id, lat, lon, pin=None)`: `WHERE user_id=? AND (pin=? OR (ROUND(lat,4)=ROUND(?,4) AND ROUND(lon,4)=ROUND(?,4)))` — legacy coordinate match retained permanently; no backfill.
2. `backend/payments.py` `create_report_checkout_session`: add `pin` param → Stripe metadata + purchase row; success/cancel URLs become `?pin={pin}&report_purchased=1` when pin exists (address form as fallback). Webhook unchanged (matches `stripe_session_id`).
3. `backend/main.py` `checkout_report` (`:4407`): accept optional `pin`; requirement relaxes to "pin or (address+lat+lon)". `report()` (`:4288`) and `check_report_access` (`:4434`): pass `pin=rl.pin` to `has_purchased_report`.
4. `api.ts` `createReportCheckoutSession` (`:143`): add `pin?`; `ScorecardPage`/`ReportPurchasePrompt` pass `parcel.pin`.
5. Tests (`test_payments.py` + new): pin-keyed purchase grants access despite coordinate drift; legacy pin-less row still matches by coords; checkout with pin-only body.

**Verify:** full unit suite; Stripe test-mode end-to-end (buy by pin → webhook → row has pin → download via pin).

### Phase 3 — Type enforcement + cleanup (~60 LOC)
1. `api.ts`: change `fetchReport`, `createReportCheckoutSession`, `checkReportAccess` to accept `SelectedParcel`; derive wire params internally (pin when present, else address/coords). Hand-constructed identity becomes a compile error.
2. Delete dead address-string plumbing in `ScorecardPage`.
3. Docs: `frontend/CLAUDE.md` (add SelectedParcelContext to Key Files), `claude-context/core/architecture.md` (identity section), `claude-context/core/known-issues.md` (condo stacks remain pin10-ambiguous; chat is read-only by design).

## 6. Hard Constraints

**Backend:** confidence literals are `"authoritative"`/`"approximate"` only. `_resolve_location` precedence must not change. Legacy purchase rows (no pin) must remain entitled forever via the coordinate OR-clause. Migration column is nullable/additive. Webhook matching stays session-id-based. Tests stubbing `property_domain` must patch `estimate_tax` (opens an 8.8 GB SQLite DB otherwise — see `test_property_domain_pin.py`).

**Frontend:** React context + `useState` only (AuthContext precedent) — no store library, no localStorage (URL is the sole serialization; a second store recreates the competing-sources problem). Chat gets no write path. Explorer gets no read path. No backfill, no new features, no scope beyond §5.

**Deployment:** push to `main` = production deploy within minutes. Each phase is its own commit on a branch; **confirm with Jack before any push to `main`** — mandatory for Phases 1 and 2 (purchase-adjacent / payment path). Verify deploys via the live API (`curl https://urbanlayerchicago.com/api/scorecard?address=...`), not server git HEAD. Backend port 8001, frontend dev 5173. Test commands: `python -m pytest backend/tests/ -q -m "not integration"`, `cd frontend && npx tsc --noEmit`.

## 7. Final Execution Contract

1. Implement §5 phases strictly in order 0→1→2→3; do not merge, reorder, or split phases.
2. Use the §2 model verbatim — exact type names, exact two-value confidence union, exact field classes. Do not add fields, tiers, stores, or persistence mechanisms.
3. The only SelectedParcel write in the entire frontend is inside `SelectedParcelContext.select()`. If an implementation step seems to require a second write site, the step is wrong — re-read §3.
4. Never construct identity client-side; never downgrade key fidelity at a handoff; never key money on coordinates when a pin exists. These override any convenience found in existing code.
5. Preserve all legacy behavior: `?address=` and `?lat&lon` URLs, pin-less purchase rows, the backend resolver, the webhook. Nothing existing breaks at any phase boundary.
6. Run the §5 per-phase verifications plus the QA parcels (control `14331030110000` / 642 W Belden Ave → authoritative; EX `14283190070000` → by-address approximate, by-PIN exact) before declaring a phase complete.
7. Commit each phase separately with conventional messages on a branch. Do not push to `main` without explicit user confirmation. Report test results faithfully, including failures.
8. Where this artifact conflicts with code comments, older docs, or intuition, this artifact wins. Where it is silent, choose the minimal change that satisfies §2's "must never happen" list.

---

## 8. Implementation status & findings (added 2026-06-11 after Phases 0+1)

**Done, on branch `selected-parcel` (not pushed — push = production deploy, needs Jack's confirmation):**
- Phase 0 (`7a610d6`): `resolved_lat`/`resolved_lon` on `/api/scorecard`; `SelectedParcel`/`ParcelQuery` in `types.ts`; `SelectedParcelContext.tsx` (sole write site); provider mounted in `main.tsx`; ScorecardPage searches via `select()`; identity strip (PIN mono → assessor link + confidence badge) under the address header.
- Phase 1 (`2b0c8b1`): Explorer map+table clicks navigate `?pin=`; ScorecardPage mount precedence pin → address → lat/lon through a single `runQuery(ParcelQuery)`; canonical `?pin=&address=` URL on pin-confirmed results; report download + access check keyed on `parcel.pin`; `checkReportAccess` passes `pin` through.

**Verified:** tsc clean; 565 backend unit tests pass; control 14331030110000 by address → PIN + authoritative badge + canonical URL; EX 14283190070000 by PIN → authoritative; Explorer row pin = URL pin = badge pin (browser-driven); `/api/report?pin=` request intercepted from the download button; legacy `?address=` and `?lat&lon` URLs work (coords → amber "Parcel identity unconfirmed").

**Findings that amend §5's literal steps (binding for Phases 2+3):**
1. `ScorecardResponse` lives in `frontend/src/lib/api.ts`, not `types.ts`; the `resolved_*` fields were added there.
2. **Explorer pins are dash-formatted display strings** (`14-28-115-084-0000`, from `_format_pin` in `retrieval/explore.py`); the backend resolver 422s on that form. Handoffs normalize with `.replace(/\D/g, "")`. Any future pin-emitting surface must do the same (or the resolver should learn to strip non-digits).
3. URL canonicalization **carries over `report_purchased`** (the literal `setSearchParams({pin, address})` would break post-purchase auto-download) and keeps the previous `address` param when a pin-keyed re-entry resolves without one (pin-only scorecard responses have `address: null`). Address stays display-only.
4. `triggerDownload` reads identity from `parcel` (no address argument); filename falls back to `pin_<pin>` for address-less parcels. Phase 2's checkout call sites should follow the same pattern.
5. **QA expectation drift:** "443 W Wrightwood Ave" (EX subject's address) now resolves *authoritative* to **neighboring pin `14283180570000`** via Address Points — §1's "no address point" claim no longer holds. One cold-cache probe returned approximate/no-pin, so the address path falls through nondeterministically under transient Socrata failures. Backend resolver behavior, out of this plan's scope, but it means an address search can confidently land on an adjacent parcel — worth investigating before money is keyed on pins resolved this way. QA the approximate badge via `?lat&lon` instead.

**Dev-environment notes:** local backend on :8001 must be restarted to pick up backend changes if long-running; dev auth bypass active locally (no `GOOGLE_CLIENT_ID`), dev user has subscription-level access; `@playwright/test` is installed in `frontend/` for browser verification (run scripts from `frontend/`, screenshots pattern in git history of this session's QA).

---

## Appendix — Strategic context behind the plan (compressed, non-binding)

From the audit that produced this plan (full reasoning not preserved; conclusions only):

- **Product behavioral truth:** UrbanLayer turns a Chicago address into one verified parcel's complete public-record assessment, sold at the moment a professional needs it in writing. The Scorecard/Chat/Report are three fidelity levels of one assessment, not three features.
- **Validated hypothesis:** the dominant cause of perceived product fragmentation *within the assessment core* is the absence of a held, visible parcel identity in the frontend (one identity producer, four consumers, zero holders). This plan is the fix.
- **Explicitly NOT addressed by this plan** (separate, known, deferred): landing hero routes to chat rather than Scorecard (`App.tsx:702`) — first-touch ambiguity; chat's area-mode vs parcel-mode intent split; Explorer's Pro paywall on a too-crude feature; condo-stack pin10 ambiguity; the chat map having no parcel handoff at all.
- **Process note:** the north-star Phase 2 (customer validation) remains the governing priority; this plan was scoped to be the minimal correctness/trust fix worth doing alongside it.
