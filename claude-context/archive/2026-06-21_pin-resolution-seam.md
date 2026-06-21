# PIN-Resolution Seam Fix (neighbor-parcel withholding + bbox distance ordering)

**Completed**: 2026-06-21
**Status**: Shipped to production (`main` @ `6a23793`, fast-forward from `f28d02a`)

## What Was Built
Closed the seam where two address→parcel resolvers disagreed: the scorecard's
authoritative `resolved_pin` (Address Points `78yw-iddh`) correctly returned
`approximate`/null for addresses absent from that dataset, while the property
orchestrator's nearest-centroid fallback still produced a **neighbor** PIN that
then drove the property/tax/comps cards and (almost) the parcel identity. Three
changes make the system withhold rather than guess, and one swaps the demo
address that exposed the issue.

## Background (the settled diagnosis)
Full evidence in `claude-context/audits/2026-06-21_resolver-investigation.md`
(and the product-wide context in `2026-06-21_full-site-sweep.md`, Finding #1).
Verified live: with GIS down, `_lookup_parcel_socrata` returned a neighbor for
`2400 N Milwaukee Ave` (→ 2401/2403, across the street) and `481 W Deming Pl`
(→ 470, wrong side) — the latter because the 220 m bbox hit the 2000-row cap
with no `$order`, so the **true nearest parcel was truncated out of the
candidate set**. `642 W Belden Ave` round-trips cleanly on both paths (the
control). **The `null` was correct; promoting `property.pin14` would have turned
a visible "approximate" disclosure into an invisible wrong answer.**

## Implementation Details
1. **Server-side distance ordering** (`backend/retrieval/property/parcels.py`).
   `_lookup_parcel_socrata` now pushes `$order` by squared planar distance to
   Socrata (verified supported on `pabr-t5kh`) with a small window
   (`_SOCRATA_NEAREST_LIMIT = 64`), so the row cap can never evict the true
   nearest. If `$order` is rejected (older SoQL), it falls back to an unordered
   bbox and **refuses on a full cap** (returns None) rather than guess. After the
   fix, the Deming data parcel moved from the wrong-side `14283180160000` (470)
   to the genuinely-nearest parcel.
2. **Reverse round-trip gate** (`backend/retrieval/property/address_points.py`).
   New `parcel_address_matches(pin14, address)` accepts a candidate PIN as
   identity only when one of its own Address Points round-trips to the input on
   **house number + directional + street name + side-of-street parity**. Any
   error withholds (returns False), never default-accepts.
3. **Scorecard identity reconciliation** (`backend/main.py`, `/api/scorecard`).
   On the approximate path, the orchestrator's `pin14` is promoted to
   authoritative identity **only if it round-trips**; otherwise `resolved_pin`
   stays null (→ "Unconfirmed" badge + hidden "Ask about this property" chat
   button, unchanged) and a new `nearest_parcel_unverified=true` flag is set.
4. **Nearest-parcel caveat UI** (`frontend/src/components/ScorecardPage.tsx`,
   `lib/api.ts`, en/es `pages.json`). When `nearest_parcel_unverified`, an amber
   banner above the data cards warns that property/tax/comps describe the nearest
   (possibly-neighbor) parcel — verify the PIN first.
5. **Flagship demo address swap** → `1601 N Milwaukee Ave` (authoritative, PIN
   `14313320180000`, B3-2, West Town) replacing `2400 N Milwaukee Ave` (which
   resolves approximate). Swapped in hero chips, PersonaScenarios Attorney card,
   `addressNotFound` hint, Scorecard placeholder, prompt suggestion, About-page
   schema example (CA/coords updated), and both CLAUDE.md killer-query lines.
   Left the bug-example comments + test fixtures on 2400 untouched (2400 is the
   genuine diagnostic case there). Note: 1601 is **not** in a TIF (2400 was), so
   the Attorney Class-6b demo now reads as an eligibility *check*.

## Key Decisions
- **Address Points stays authoritative; never blind-promote `pin14`.** The
  nearest-centroid fallback is the same mechanism R7 replaced; promotion is
  gated on an address round-trip so the rare correct case can promote while
  neighbors are withheld.
- **Withhold, don't drop.** A withheld identity keeps the approximate badge and
  caveats the per-card data rather than presenting a neighbor as the subject —
  the right bias for a due-diligence product.
- **Ordering over a bigger cap.** The earlier "raise the cap to 2000" fix was
  insufficient (Lincoln Park still truncated); server-side ordering is the
  correct fix and makes the cap irrelevant.

## Files Changed
- `backend/retrieval/property/parcels.py` — distance-ordered fallback + refuse-on-cap
- `backend/retrieval/property/address_points.py` — `parcel_address_matches()`
- `backend/main.py` — `/api/scorecard` identity reconciliation + `nearest_parcel_unverified`
- `frontend/src/lib/api.ts`, `components/ScorecardPage.tsx`, `locales/{en,es}/pages.json` — caveat banner
- Demo-address swap: `locales/{en,es}/landing.json`, `pages.json`, `components/{ScorecardPage,AboutPage}.tsx`, `lib/constants.ts`, `CLAUDE.md`, `backend/CLAUDE.md`
- Tests: `test_property_parcels.py` (updated + 3 new), `test_address_points.py` (+8), `test_scorecard_identity.py` (new, 4)
- Audits: `claude-context/audits/2026-06-21_{full-site-sweep,resolver-investigation}.md`

## Verification
- Local: `python -m pytest backend/tests/ -q` → 874 passed, 56 deselected; `tsc --noEmit` clean; i18n parity 14/14.
- Live (post-deploy): see this file's companion deploy log / the README archive entry. 1601 → authoritative ✓ Exact + chat; 642 W Belden → authoritative (unchanged); 2400 N Milwaukee + 481 W Deming → null/approximate + `nearest_parcel_unverified=true`, no neighbor surfaced as exact.

## Known Limits / Follow-ups
- GIS is still down; the fallback is the hot path. The gate adds one (cached)
  Address Points call on the approximate path only.
- Condo stacks remain pin10-ambiguous (separate known issue) — the gate matches
  on address, not unit.
