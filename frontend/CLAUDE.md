# Frontend — UrbanLayer

## Stack

React + TypeScript + Vite + Tailwind v3. Map: Mapbox GL JS (dark-v11) + deck.gl via `@deck.gl/mapbox` MapboxOverlay. State: React hooks (no external state library). Build: ~322KB JS, 16KB CSS.

## Key Files

| File | Purpose |
|------|---------|
| `src/App.tsx` | State machine: splash → workspace. Conversation lifecycle, per-question toggling, URL routing |
| `src/lib/useChat.ts` | SSE consumption, message limit (10), activity tracking, plan/context/mapData attachment |
| `src/lib/types.ts` | TypeScript types matching backend Pydantic models |
| `src/lib/api.ts` | SSE streaming, conversation CRUD, map data, admin endpoints, fetchSection cache. All requests use `authFetch()` with `credentials: include` + CSRF |
| `src/lib/useAuth.ts` | Auth state hook: user, isAuthenticated, authRequired, signIn/signOut/checkAuth |
| `src/contexts/AuthContext.tsx` | React context provider wrapping `useAuth`, available app-wide |
| `src/components/AuthModal.tsx` | "Sign in with Google" modal, shown when unauth user tries to chat |
| `src/components/UserMenu.tsx` | Google avatar dropdown in workspace header (sign out) |
| `src/components/ProtectedRoute.tsx` | Route guard for auth + tier checks (used for `/admin`) |
| `src/lib/mapColors.ts` | Shared colors for map + charts + zone categories + OVERLAY_INFO/ZONE_INFO definitions + hash-based incentive zone colors |
| `src/lib/termDefinitions.ts` | Unified term lookup: overlays, zones, incentives, flood zones → `getTermInfo()` |
| `src/components/InfoTooltip.tsx` | Hover/tap popover for domain terms (dotted underline trigger, portal-based) |
| `src/lib/analytics.ts` | Client-side trend/pie computation from map data |
| `src/lib/history.ts` | Async API-backed persistence + localStorage→SQLite migration |

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
- **Sidebar**: drag-to-resize, collapsed rail (44px). Data tab (map + analytics) / Sources tab (code chunks). Auto-opens when context arrives.
- **New sidebar card**: use `CollapsibleCard` pattern from `sidebar/CollapsibleCard.tsx`.
- **Citations**: `[N]` → `CitationPill` (§ section reference), `[data:X]` → `DataPill` (opens Data tab).
- **Map layer order** (bottom → top): zoning polygons → overlay districts → incentive zones → parcel boundary → data dots (crime/311/permits) → transit stations → address pin.
- **Tooltip**: `position: fixed` via `createPortal` to `document.body`, viewport-clamped with `useLayoutEffect`.
- **InfoTooltip**: Wrap term text in `<InfoTooltip term="key">{text}</InfoTooltip>` for hover/tap definitions. Uses `termDefinitions.ts` for lookups across overlays, zones, incentives, flood zones. Dotted underline trigger, 150ms hover persistence, click-away dismiss on mobile.
- **Charts**: `PieChart` (SVG donut) and `BarChart` (SVG horizontal bars) are custom — no chart library. `BarChart` takes `DistributionBucket[]` and renders labeled horizontal bars with hover state.
- **Routing**: `/` (splash), `/c/:id` (conversation), `/s/:shareToken` (shared read-only view), `/admin` (dashboard, admin-only via `ProtectedRoute`), `/about` (technical deep dive).
- **Auth**: `AuthProvider` wraps the app in `main.tsx`. Auth gate on `sendMessage` in `App.tsx` — shows `AuthModal` if `authRequired && !isAuthenticated`. `UserMenu` in workspace header shows avatar + sign-out. Admin link only visible when `user.tier === "admin"`. In dev mode (`GOOGLE_CLIENT_ID` not set), auth is fully bypassed — no sign-in UI shown.
- **401-interceptor**: `authFetch()` in `api.ts` intercepts 401 responses, attempts `POST /api/auth/refresh` via raw `fetch` (not `authFetch` to avoid recursion), coalesces concurrent refreshes with a module-level `_refreshPromise`, re-reads CSRF cookie after refresh, retries original request once.
- **History stripping**: `useChat.ts` sends only `{role, content}` in chat POST history (strips `context`/`plan`/`mapData` blobs) to avoid HTTP 413 from nginx's `client_max_body_size`.
- **Stream close detection**: `useChat.ts` tracks `receivedDone` flag — if the SSE stream ends without a `done` event and wasn't user-aborted, shows "Connection lost — please try again."
- **Pipeline timing**: The `done` SSE event includes a `timings` dict (`PhaseTimings` in `types.ts`) with `conv_synth`, `router`, `retrieval`, `first_token`, `total` (all in ms). Logged to console via `[perf] pipeline timings (ms):` in `useChat.ts`.

## Docker / Nginx

- **Dockerfile**: multi-stage (node build → nginx serve). `NGINX_CONF` build arg selects config (defaults to `nginx.conf` for dev).
- **`nginx.conf`**: dev config — port 80 only, proxies `/api/`, `/chat`, `/health`, `/autocomplete`, `/section/` to `backend:8001`. SPA fallback for all other routes.
- **`nginx.prod.conf`**: production config — HTTP→HTTPS redirect on port 80, SSL termination on port 443 (Cloudflare Origin Certificate), security headers (HSTS, CSP tuned for Mapbox/deck.gl, X-Frame-Options DENY), gzip compression. Same proxy locations as dev plus `X-Forwarded-Proto`. `client_max_body_size 16m` on `/api/` and `/chat` location blocks.
- **CSP domains**: `script-src` allows `static.cloudflareinsights.com`; `style-src` allows `fonts.googleapis.com`; `font-src` allows `fonts.gstatic.com`; `img-src` allows `lh3.googleusercontent.com` (Google avatars); `connect-src` allows `*.ingest.de.sentry.io` (Sentry). CSP is defined in two places (lines 26 and 54) — both must be updated together.
- **Production deploy**: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` — the override adds port 443, SSL cert volume mount, and selects `nginx.prod.conf`.

## Commands

```bash
npm run dev          # dev server on :5173
npx tsc --noEmit     # type check
npm run build        # production build (~322KB JS)
```
