# Coherence Audit Step 3 — Address-First Homepage + Auth Off the Front Door

**Completed**: 2026-06-12
**Status**: Shipped to production (merge `0a408a9`, deploy verified live: bundle `index-B7hsOZ9h.js`,
`GET /api/conversations` → 401). **Caveat:** the anon-chat CSRF hotfix (`64ae13d`) was committed
after the merge — anon chat 403s on CSRF until it deploys. See Post-Deploy Findings.

## What Was Built

The audit's "THE BIG ONE": the homepage hero became a pure address-autocomplete input — "Which
property?" → `/scorecard?address=` (free, anonymous, ~2s) — replacing the auth-walled chat box.
The auth gate moved off the front door entirely: anonymous chat now works at the server-enforced
3/day IP limit, in-memory only, with sign-in asked at save/share/purchase/rate-limit. Conversation
endpoints were hardened to `require_auth` (closing an anon data-leak that opening chat would have
created). Phase 2 sequencing was decided: this fix lands BEFORE the 20 customer interviews.

## Implementation Details

### Hero (frontend)
- `components/AddressInput.tsx` (new): single-line input, whole-value autocomplete (300ms debounce,
  min 3 chars, `getAutocomplete()`), keyboard nav, suggestion select submits immediately, free-text
  Enter submits too (backend `_resolve_location` handles it).
- `components/landing/HeroEntrance.tsx` (new): address mode (default) ⇄ chat mode ("librarian"),
  swapped by a quiet link with back affordance. Address mode: AddressInput + 3 "Try:" example-address
  chips. Chat mode: existing ChatInput (`variant="hero"`, new `initialValue` prop) + code-question
  chips. `chatPrefill` prop flips to chat mode — used by the Architect persona card
  (scroll-to-top + prefill; user reviews then sends).
- Hero copy: h1 "UrbanLayer" + north-star §4 headline ("Site feasibility for any Chicago address.
  In seconds.") + `heroSubline` enumeration. `howItWorks` re-flavored: Enter an address → We
  assemble the file → You get the dossier. Old mixed `suggestions` array deleted.
- `PersonaScenarios`: i18n items gained `action: "scorecard"|"chat"` + `address`;
  Developer (4520 N Clark St) and Attorney (2400 N Milwaukee Ave) navigate to the Scorecard,
  Architect prefills the librarian chat. Falls back to chat when `address` missing.
- Deleted dead landing demo code (unrendered since Phase 0): `LandingMap`, `LandingAnalytics`,
  `NeighborhoodExplorer`, `NeighborhoodSelector`, `DataSourceTabs`, `lib/dummyData.ts`,
  `lib/communityAreas.ts`, `getCommunityAreaByPoint` (api.ts), `explorer.*` i18n keys (en+es).
  This closed the audit's "crime demo" item by deletion. −794 lines net.

### Auth deferral (frontend)
- `sendMessage` auth gate (App.tsx:318) deleted. `canPersist = !authRequired || isAuthenticated`
  gates: conversation creation/navigation, init-effect history load + localStorage migration,
  attachments (paperclip hidden when `onAttach` undefined).
- Workspace header gains a "Sign in to save your research" nudge (anon only) → AuthModal.
- 429 UX fixed: `ChatStreamError` (api.ts) carries the server `detail`; `useChat` exposes
  `rateLimited`, no longer overwrites stream errors with "Connection lost", and pops the optimistic
  empty assistant bubble when the request fails pre-token. Banner shows the real message
  ("Daily query limit reached (3/day). Sign in for higher limits.") + sign-in button for anon.

### Backend hardening
- All 9 conversation CRUD endpoints + GET share-status: `get_current_user` → `require_auth`.
  Rationale: db.py's `user_id IS NULL` fallback is unscoped — with anon chat open, every anonymous
  visitor would have seen and could delete every other anon visitor's conversations
  (and `DELETE /api/conversations` would wipe them all). Dev mode unaffected (`require_auth`
  resolves to the dev user; NULL rows stay visible via the fallback).
- `PATCH /api/conversations/{id}/messages/{position}` gained its missing ownership check
  (previously ANY caller could rewrite any conversation's map data).
- CSRF bootstrap (hotfix `64ae13d`): `GET /api/auth/me` now issues the JS-readable double-submit
  `csrf_token` cookie to anonymous visitors. Without it, CSRFMiddleware 403s anon `POST /chat` —
  the cookie was previously only issued at OAuth callback/refresh, which anon users never hit.
- New events in `_VALID_EVENT_NAMES`: `hero_address_submit` (source: hero/chip/persona),
  `hero_librarian_click` (source: hero/persona). Not yet charted on the admin dashboard.
- Tests: `test_conversation_endpoints.py` (401s on all endpoints, cross-user 404 scoping,
  dev-mode round-trip + NULL-fallback preservation, CSRF bootstrap incl. anon /chat reaching the
  rate limiter instead of 403) and `test_rate_limit.py` (anon 429 detail contract, per-IP windows,
  HTTP-level /chat 429). Suite: 599 unit tests.

## Key Decisions (Jack, via AskUserQuestion, 2026-06-12)
1. **Pure address input hero** (over smart combined input / tabbed hero) — cleanest identity,
   matches north-star §4 verbatim; librarian gets a secondary entrance.
2. **Open anonymous chat fully** (over gate-after-first-answer / keep walled) — auth at identity
   moments only; the 3/day IP limit is the cost control.
3. **Re-route chips/personas by intent** — every element routes to the surface that can serve it.
4. **Full scope bundle**: docs reconciliation + dead-code deletion + es parity + Phase 2 note.
5. **Delete legacy NULL conversations unconditionally** on prod (pending — see below).
6. Purchase-time sign-in stays (anonymous Stripe purchase = separate future project).

## Verification
- Playwright against live dev servers: hero render (subtitle/chips/librarian link), autocomplete
  dropdown → suggestion click → Scorecard fully resolves (identity strip, PIN, report CTA),
  librarian swap + back, Developer/Attorney → Scorecard, Architect → prefilled chat, garbage
  address → clean Scorecard error, empty Enter → no nav, 429 banner shows server detail (verified
  with `RATE_LIMIT_ANON_DAY=1`) — not "Connection lost" — with the user message preserved.
- Live post-deploy: new bundle serves hero strings; `GET /api/conversations` → 401;
  `GET /api/scorecard` → 200 anonymous. **Anon `POST /chat` → 403 CSRF** — the gap the hotfix
  closes; the UI gate had always masked it in production.
- Note: anon auth-wall UI behavior (no conversation POST, nudge, hidden History) is untestable in
  dev mode (auth bypassed) — covered by the HTTP-level tests; spot-check on prod after the hotfix.

## Post-Deploy Findings
- **CSRF blocked anon chat** (found by live API probe, same lesson as R7: verify the live artifact).
  Hotfix `64ae13d` committed; deploys with the next push.
- **Prod NULL-row cleanup pending**: `DELETE FROM conversations WHERE user_id IS NULL` (+ orphan
  messages/uploads/shares — SQLite FK cascade is OFF by default, delete children first). Approved
  unconditionally. Low urgency now: the 401 hardening already makes NULL rows unreachable
  anonymously; they remain visible to signed-in users via the legacy fallback until cleaned.
- Local dev: `chicago-backend-1` docker container crash-loops on `ModuleNotFoundError: jwt`
  (image predates PyJWT) — needs `docker compose build backend`. Unrelated to this change.

## Files Changed
Backend: `main.py` (conversation deps, PATCH ownership, CSRF bootstrap, event names),
`tests/test_conversation_endpoints.py` (new), `tests/test_rate_limit.py` (new).
Frontend: `App.tsx`, `lib/api.ts`, `lib/useChat.ts`, `components/AddressInput.tsx` (new),
`components/landing/HeroEntrance.tsx` (new), `components/ChatInput.tsx`,
`components/landing/PersonaScenarios.tsx`, `locales/{en,es}/{landing,common}.json`;
deleted 5 landing components + 2 lib modules.
Docs: root/frontend/backend `CLAUDE.md`, `strategy/north-star.md`,
`strategy/product-coherence-audit.md`.
