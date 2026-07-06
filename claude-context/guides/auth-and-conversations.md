# Auth & Conversations — UrbanLayer

## Authentication Architecture

Google OAuth2 Authorization Code flow + self-rolled JWT sessions. Auth is opt-in — when `GOOGLE_CLIENT_ID` is not set, all requests are treated as admin (local dev works without OAuth).

### Token Strategy
- httpOnly `access_token` cookie (JWT HS256, 15min TTL)
- httpOnly `refresh_token` cookie (opaque, SHA-256 hashed in SQLite, 7d TTL, path-scoped to `/api/auth`, rotation on each refresh)
- JS-readable `csrf_token` cookie (double-submit CSRF pattern)

### Backend (`auth.py`)

**Endpoints**: `GET /api/auth/google` (redirect to Google), `GET /api/auth/google/callback` (exchange code, set cookies, redirect), `POST /api/auth/refresh` (rotate tokens), `GET /api/auth/me` (current user status), `POST /api/auth/logout`.

**FastAPI dependencies**: `get_current_user()` (returns user dict or None), `require_auth()` (401 if not auth'd), `require_admin()` (403 if not admin), `require_tier("premium")` (gates premium endpoints).

**User tiers**: `free` (default on sign-up), `premium` (Stripe subscription), `admin` (manual DB flag).

**Comp premium (vouchers, 2026-07-06)**: `users.premium_until` (epoch ms) grants *effective* premium to a free user while in the future — applied by `_apply_comp_premium()` inside `get_current_user()`, the single choke point every gate reads (report, Discovery, rate limits, `require_tier`). The tier column stays `free` (CHECK constraint untouched), so Stripe webhooks can never clobber a grant and expiry is implicit. The dict gains `comp_premium: True`; `get_subscription_status` reports `comp_until` and keeps `subscription_active` false for comp (no Stripe customer → no billing portal). Grants come from voucher redemption (`POST /api/voucher/redeem`, settings page + report-paywall modal, per-user attempt cap) or admin (`POST /api/admin/grant` by email, `GET/POST /api/admin/vouchers` to mint/list codes — AdminDashboard "Early Access" section). Stacking codes extends from the current expiry. Tests: `test_vouchers.py`.

**Config settings**: `google_client_id`, `google_client_secret`, `jwt_secret`, `jwt_access_token_ttl` (900s), `jwt_refresh_token_ttl` (604800s), `auth_cookie_secure`, `frontend_url`.

**CSRF enforcement**: `CSRFMiddleware` in `main.py` on all POST/PUT/DELETE/PATCH. Exempt paths: `/api/webhook/stripe` (server-to-server), `/api/auth/refresh` (cookie may be expired), `/api/auth/logout`. In dev mode (no `GOOGLE_CLIENT_ID`), CSRF is skipped entirely.

### Frontend

- **`useAuth.ts`**: `checkAuth()` calls `GET /api/auth/me`, if unauthenticated tries `POST /api/auth/refresh`, runs once on mount
- **`AuthContext.tsx`**: Wraps `useAuth`, exposes `{ user, isAuthenticated, authRequired, loading, signIn, signOut, checkAuth }`
- **`AuthModal.tsx`**: "Sign in with Google" modal, shown when unauth user submits a message
- **`UserMenu.tsx`**: Google avatar dropdown (name, email, tier badge, sign-out)
- **`ProtectedRoute.tsx`**: Route guard for tier-based access (used for `/admin`)
- **`api.ts`**: `authFetch()` wrapper with `credentials: 'include'` + CSRF headers on mutations

**401-interceptor**: `authFetch()` intercepts 401 responses, attempts `POST /api/auth/refresh` (raw fetch to avoid recursion), coalesces concurrent refreshes via module-level `_refreshPromise`, re-reads CSRF cookie, retries original request.

**Auth gate in sendMessage**: `if (authRequired && !isAuthenticated) { setShowAuthModal(true); return; }`

**Auth bypass (dev)**: When `GOOGLE_CLIENT_ID` is empty, `get_current_user()` returns `_DEV_USER` (id="dev"), `handle_me()` returns `{authenticated: true, auth_required: false}`.

## Conversation Persistence

### Backend Flow
1. **Create**: `POST /api/conversations` → `db.create_conversation(conv_id, title, user_id)`
2. **Save messages**: `PUT /api/conversations/{id}/messages` → `db.save_messages(conv_id, messages)`
3. **List**: `GET /api/conversations` → `db.list_conversations(user_id)`
4. **Get**: `GET /api/conversations/{id}` → `db.get_conversation(conv_id, user_id)`
5. **Delete**: `DELETE /api/conversations/{id}`

All endpoints use `Depends(get_current_user)`. `_user_id(user)` extracts `user["id"]` or returns `None`.

### User Scoping in DB Queries
- `list_conversations(user_id)`: If set → `WHERE user_id = ? OR user_id IS NULL`; if None → no WHERE, returns all
- `get_conversation(conv_id, user_id)`: If set → `WHERE id = ? AND (user_id = ? OR user_id IS NULL)`; if None → `WHERE id = ?`

### Frontend Flow
- **`api.ts`**: `authFetch()` wraps `fetch()` with `credentials: "include"` + CSRF token header
- **`history.ts`**: `loadConversations()` → `listConversations()`, `saveConversation()` → `createConversation()` + `apiSaveMessages()`
- **`App.tsx`**: Init effect gated on `!authLoading` so conversations load after auth resolves. URL sync for `/c/{id}`. Post-stream `appendMessages()` + list reload.

## Sharing

**Share API** (4 endpoints):
- `POST /api/conversations/{id}/share` — create share link (requires auth, replaces existing)
- `GET /api/conversations/{id}/share` — check share status
- `DELETE /api/conversations/{id}/share` — revoke share link
- `GET /api/share/{token}` — public endpoint, loads conversation without auth

Share tokens are 132-bit URL-safe (`secrets.token_urlsafe(22)`). Live links, not snapshots — CASCADE delete cleans up when conversation is deleted. `ShareModal` UI for create/copy/revoke.

## Stripe Payment System

`backend/payments.py` handles Stripe Checkout sessions, webhook events (`checkout.session.completed`, `subscription.updated/deleted`), and billing portal. Schema v7 adds `stripe_customer_id` + `stripe_subscription_id` to users table. Frontend: `/pricing` page (Free vs Pro $99/mo), `UpgradePrompt` modal on gated features.

## Database Schema

SQLite via aiosqlite, WAL mode, singleton connection, schema versioning (currently v8).

**Tables**: `conversations` (with `language` column), `messages` (with context/plan/map_data blobs), `uploads`, `llm_calls` (per-call token/cost tracking), `request_logs` (per-turn summary with `user_id`, `language`), `users` (with tier, stripe fields), `refresh_tokens`, `conversation_shares`, `schema_version`.

**Key design**: Message limit of 10 per conversation, enforced backend + frontend.
