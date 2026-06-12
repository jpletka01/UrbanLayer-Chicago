# Frontend — UrbanLayer

## Stack

React + TypeScript + Vite + Tailwind v3. Map: Mapbox GL JS (dark-v11) + deck.gl via `@deck.gl/mapbox` MapboxOverlay. State: React hooks (no external state library). i18n: react-i18next with bundled JSON catalogs. Build: ~322KB JS, 16KB CSS.

## Key Files

| File | Purpose |
|------|---------|
| `src/App.tsx` | State machine: splash → workspace. Conversation lifecycle, per-question toggling, URL routing |
| `src/components/AddressInput.tsx` | Hero address input: whole-value autocomplete (300ms debounce), suggestion select submits immediately, free-text Enter submits too (backend resolves) |
| `src/components/landing/HeroEntrance.tsx` | Homepage entry surface: address mode (default — AddressInput + example-address chips → `/scorecard?address=`) ⇄ chat mode (librarian: ChatInput + code-question chips), swapped by a quiet link. `chatPrefill` prop flips to chat mode (used by persona cards) |
| `src/lib/useChat.ts` | SSE consumption, message limit (10), activity tracking, plan/context/mapData attachment |
| `src/lib/types.ts` | TypeScript types matching backend Pydantic models |
| `src/lib/api.ts` | SSE streaming, conversation CRUD, map data, admin endpoints, fetchSection cache, `fetchExploreParcels()`/`fetchExploreMap()`. `fetchReport()`/`createReportCheckoutSession()`/`checkReportAccess()` accept a `SelectedParcel` and derive wire params internally (pin when present, else address/coords) — hand-constructed report identity is a compile error. All requests use `authFetch()` with `credentials: include` + CSRF |
| `src/lib/useAuth.ts` | Auth state hook: user, isAuthenticated, authRequired, signIn/signOut/checkAuth |
| `src/contexts/AuthContext.tsx` | React context provider wrapping `useAuth`, available app-wide |
| `src/contexts/SelectedParcelContext.tsx` | Held parcel identity (`SelectedParcel`: pin + confidence + lat/lon + display address). `select(ParcelQuery)` is the **only** write site — fetches scorecard, commits backend-resolved identity atomically. Never construct identity client-side |
| `src/components/AuthModal.tsx` | "Sign in with Google" modal, shown at identity moments (save/share nudge, rate-limit 429) — NOT on first chat |
| `src/components/UserMenu.tsx` | Google avatar dropdown in workspace header (sign out, tier badge, manage subscription/upgrade link) |
| `src/components/PricingPage.tsx` | 3-card pricing page at `/pricing`: Free / $25 Development Feasibility Report (lead card, CTA → `/scorecard`) / Pro ($99/mo, "4 reports ≈ a month of Pro" upsell). Also linked from the landing footer |
| `src/components/UpgradePrompt.tsx` | Modal shown when free user hits premium-gated feature (Explorer, etc.) |
| `src/components/ReportPurchasePrompt.tsx` | Modal for a la carte report purchase ($25 one-time) with dual CTA: buy single report or upgrade to Pro. Takes the `SelectedParcel`; checkout is PIN-keyed when pin exists (address/lat/lon still sent for display + legacy entitlement) |
| `src/components/ScorecardPage.tsx` | Property Scorecard page. Param precedence `?pin=` → `?address=` → `?lat=&lon=`; pin-confirmed results canonicalize the URL to `?pin=&address=` (legacy URLs still work). Identity band: Mapbox Static thumbnail (pin-only, hidden on failure), i18n'd confidence badges with tooltip explanations, dash-formatted PIN → assessor link, facts-only verdict line composed from context flags (zone name · TIF · OZ · TOD · ADU · ARO · flood). Page-local cards: ZoningCard (renders `zone_definition` Title-17 standards from the scorecard API), CrimeYoYCard (shows prior-year base counts), Address311Card. One investigate link per card, muted style (solid accent reserved for purchase). `?report_purchased=1` post-purchase auto-download (Stripe success URL is `?pin=...&report_purchased=1` for pin-keyed purchases). Report download/access/purchase keyed on `parcel.pin` when present |
| `src/components/ExplorePage.tsx` | Site Explorer: split-screen CA parcel browser with filter panel + deck.gl map. Premium-gated. Click parcel → Scorecard via `?pin=` (display pins are dash-formatted; handoff strips to 14 digits) |
| `src/components/ProtectedRoute.tsx` | Route guard for auth + tier checks (used for `/admin`) |
| `src/lib/mapColors.ts` | Shared colors for map + charts + zone categories + OVERLAY_INFO/ZONE_INFO definitions + hash-based incentive zone colors |
| `src/lib/termDefinitions.ts` | Unified term lookup: overlays, zones, incentives, flood zones → `getTermInfo()` |
| `src/components/InfoTooltip.tsx` | Hover/tap popover for domain terms (dotted underline trigger, portal-based) |
| `src/lib/analytics.ts` | Client-side trend/pie computation from map data |
| `src/lib/tracking.ts` | Usage analytics: `track()`, `flush()`, `setAddress()`, `initTracking()`. 7 events (page_view, investigate_click, report_cta_click, chat_message_sent, scorecard_bridge_click, hero_address_submit, hero_librarian_click). Batched flush every 30s + sendBeacon on page hide. Session ID (per tab) + visitor ID (cross-session). |
| `src/lib/format.ts` | Shared display formatters: `formatDate`, `humanizeShoutyCase` (re-cases ALL-CAPS dataset strings, acronym/run-aware — used by scorecard cards + RegulatoryCard) |
| `src/lib/csvExport.ts` | CSV export utility: `toCSV`, `downloadCSV`, `exportCSV`, `buildScorecardCSV`. Used by Scorecard, Explorer, AnalyticsSection |
| `src/lib/history.ts` | Async API-backed persistence + localStorage→SQLite migration |
| `src/lib/i18n.ts` | i18next initialization, bundled resources, localStorage language persistence |
| `src/locales/{en,es}/` | Translation JSON files: common, chat, sidebar, landing, map, data, pages namespaces |
| `src/components/LanguageSelector.tsx` | Globe icon dropdown for language switching (English/Español) |

## Design Tokens

| Token | Value | Tailwind |
|-------|-------|----------|
| Background | `#0d0d0d` | `bg-dark-bg` |
| Surface | `#171717` | `bg-dark-surface` |
| Elevated | `#1f1f1f` | `bg-dark-elevated` |
| Border | `#2a2a2a` | `border-dark-border` |
| Accent | `#c96442` | `bg-accent` / `text-accent` |
| Text Primary | `#eeeeee` | `text-text-primary` |
| Text Secondary | `#a3a098` | `text-text-secondary` |
| Text Muted | `#6b6962` | `text-text-muted` |
| Font | Inter, system-ui, sans-serif | — |

## Patterns

- **Per-message context**: each assistant message stores its own `context`, `plan`, `mapData`, `mapFetchedAt`. Citations survive multi-turn. Clicking a past user message loads that turn's data into the sidebar.
- **Sidebar (desktop)**: drag-to-resize, collapsed rail (44px). Data tab (map + analytics) / Sources tab (code chunks). Auto-opens when context arrives.
- **Sidebar (mobile)**: `MobileSidebarSheet` bottom sheet with 3 snap heights (20vh peek / 70vh default / 90vh full). 3-tab layout: Map / Data / Sources (bypasses `DataMapLayout`, renders `MapView` and `DataView` independently at full height). MapView stays mounted when switching tabs to preserve GL context. Smart default tab: Map for spatial queries, Data for domain queries, Sources for legal questions. Map controls use compact layer toggles + filter popover (vs inline desktop controls). `isMobile` prop on `MapView` drives mobile-specific rendering.
- **New sidebar card**: use `CollapsibleCard` pattern from `sidebar/CollapsibleCard.tsx`.
- **Chat→Scorecard bridge**: `sidebar/ScorecardBridgeCard.tsx` pinned at top of `DataView` when the active message's context resolves a parcel (`property.pin14` → `/scorecard?pin=`, else `resolved_address` → `?address=`). `ReportTeaser` takes optional `href` — clickable in the chat sidebar, static on ScorecardPage. Both fire `scorecard_bridge_click`. The word "report" is reserved for the paid Development Feasibility Report; the free chat export is the "transcript" (button: "Export").
- **Citations**: `[N]` → `CitationPill` (§ section reference), `[data:X]` → `DataPill` (opens Data tab).
- **Map layer order** (bottom → top): zoning polygons → overlay districts → incentive zones → parcel boundary → data dots (crime/311/permits) → transit stations → address pin.
- **Map layer defaults** (`MapView.tsx`): zoning/incentives/overlays/transit ON; crime/311/permit dots OFF. Dots auto-enable when `deriveFilterMode(sources)` is a single-source mode (explicit crime/311/permits query) — same one-way-ratchet pattern as `hasTransitContext`. Per coherence audit §6: the default map is the analyst's view of the parcel; ambient point clouds appear behind explicit intent or the Points toggle.
- **Tooltip**: `position: fixed` via `createPortal` to `document.body`, viewport-clamped with `useLayoutEffect`.
- **InfoTooltip**: Wrap term text in `<InfoTooltip term="key">{text}</InfoTooltip>` for hover/tap definitions. Uses `termDefinitions.ts` for lookups across overlays, zones, incentives, flood zones. Dotted underline trigger, 150ms hover persistence, click-away dismiss on mobile.
- **Charts**: `PieChart` (SVG donut) and `BarChart` (SVG horizontal bars) are custom — no chart library. `BarChart` takes `DistributionBucket[]` and renders labeled horizontal bars with hover state.
- **Routing**: `/` (splash — address-first hero via `HeroEntrance` → `/scorecard?address=`; librarian chat secondary), `/c/:id` (conversation), `/s/:shareToken` (shared read-only view), `/scorecard` (property scorecard, non-AI), `/explore` (Site Explorer, premium-gated), `/pricing` (Free vs Pro plan comparison), `/admin` (dashboard, admin-only via `ProtectedRoute`), `/about` (technical deep dive).
- **Auth**: `AuthProvider` wraps the app in `main.tsx`. **No gate on `sendMessage`** — anonymous chat works at the server-enforced 3/day IP limit. Anonymous = in-memory only: `canPersist` (`!authRequired || isAuthenticated`) gates conversation creation, history load, and attachments (the conversation endpoints 401 without a session); workspace header shows a "Sign in to save your research" nudge, and a 429 renders the server detail + sign-in button (`rateLimited` from `useChat`, `ChatStreamError` from `api.ts`). `AuthModal` appears at identity moments only (nudge, share, purchase, 429). `UserMenu` in workspace header shows avatar + sign-out. Admin link only visible when `user.tier === "admin"`. In dev mode (`GOOGLE_CLIENT_ID` not set), auth is fully bypassed — no sign-in UI shown.
- **401-interceptor**: `authFetch()` in `api.ts` intercepts 401 responses, attempts `POST /api/auth/refresh` via raw `fetch` (not `authFetch` to avoid recursion), coalesces concurrent refreshes with a module-level `_refreshPromise`, re-reads CSRF cookie after refresh, retries original request once.
- **History stripping**: `useChat.ts` sends only `{role, content}` in chat POST history (strips `context`/`plan`/`mapData` blobs) to avoid HTTP 413 from nginx's `client_max_body_size`.
- **Stream close detection**: `useChat.ts` tracks `receivedDone` flag — if the SSE stream ends without a `done` event and wasn't user-aborted, shows "Connection lost — please try again."
- **i18n**: `react-i18next` with 7 namespaces (`common`, `chat`, `sidebar`, `landing`, `map`, `data`, `pages`). Languages: English (default) + Spanish. Bundled JSON resources in `src/locales/{en,es}/`. Language persisted in localStorage as `urbanlayer-language`. `LanguageSelector` component in splash and workspace headers. Backend synthesizer responds in target language via `LANGUAGE_INSTRUCTION` prompt append — English path is +0ms latency. Adding a new language: create `src/locales/{code}/` with 7 JSON files + add option to `LanguageSelector.tsx` + add entry to `LANGUAGE_NAMES` dict in `backend/synthesizer.py`. Non-React code (mapColors.ts, mapTooltip.ts, termDefinitions.ts) uses `i18n.t()` directly. **Not yet localized**: Admin dashboard, About page (excluded by design).
- **Pipeline timing**: The `done` SSE event includes a `timings` dict (`PhaseTimings` in `types.ts`) with `conv_synth`, `router`, `retrieval`, `first_token`, `total` (all in ms). Logged to console via `[perf] pipeline timings (ms):` in `useChat.ts`.

## Docker / Nginx

- **Dockerfile**: multi-stage (node build → nginx serve). `NGINX_CONF` build arg selects config (defaults to `nginx.conf` for dev).
- **`nginx.conf`**: dev config — port 80 only, proxies `/api/`, `/chat`, `/health`, `/autocomplete`, `/section/` to `backend:8001`. SPA fallback for all other routes.
- **`nginx.prod.conf`**: production config — HTTP→HTTPS redirect on port 80, SSL termination on port 443 (Cloudflare Origin Certificate), security headers (HSTS, CSP tuned for Mapbox/deck.gl, X-Frame-Options DENY), gzip compression. Same proxy locations as dev plus `X-Forwarded-Proto`. `client_max_body_size 16m` on `/api/` and `/chat` location blocks.
- **CSP domains**: `script-src` allows `static.cloudflareinsights.com`; `style-src` allows `fonts.googleapis.com`; `font-src` allows `fonts.gstatic.com`; `img-src` allows `lh3.googleusercontent.com` (Google avatars); `connect-src` allows `*.ingest.de.sentry.io` (Sentry). CSP is defined in two places (lines 26 and 54) — both must be updated together.
- **Production deploy**: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` — the override adds port 443, SSL cert volume mount, and selects `nginx.prod.conf`.

## Responsive

- **Mobile** (<768px): Single-column chat. Sidebar is `MobileSidebarSheet` (bottom sheet with snap heights 20/70/90vh). 3-tab Map/Data/Sources layout with `MapView isMobile={true}` (compact layer toggles, filter popover). `SidebarView "map"` only set on mobile.
- **Desktop** (768px+): Dual-pane, `SidebarPanel` with `hidden md:flex`. 2-tab Data/Sources with `DataMapLayout` stacking map + data cards.
- Hero title: `text-4xl md:text-5xl`.
- Chat: `w-full` mobile, `w-[60%]` desktop (sidebar open).

## Commands

```bash
npm run dev          # dev server on :5173
npx tsc --noEmit     # type check
npm run build        # production build (~322KB JS)
```
