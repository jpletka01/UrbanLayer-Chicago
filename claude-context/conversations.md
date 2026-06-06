# Conversation Persistence — Architecture & Known Issues

## How Conversations Work

### Backend Flow
1. **Create**: `POST /api/conversations` → `main.py:309` → `db.create_conversation(conv_id, title, user_id)` → `INSERT INTO conversations (id, title, user_id, created_at, updated_at)`
2. **Save messages**: `PUT /api/conversations/{id}/messages` → `main.py:338` → `db.save_messages(conv_id, messages)`
3. **List**: `GET /api/conversations` → `main.py:302` → `db.list_conversations(user_id)`
4. **Get**: `GET /api/conversations/{id}` → `main.py:318` → `db.get_conversation(conv_id, user_id)`
5. **Delete**: `DELETE /api/conversations/{id}` → `main.py:328`

All conversation endpoints use `Depends(get_current_user)` which returns `dict | None`. The `_user_id(user)` helper (main.py:298) extracts `user["id"]` or returns `None`.

### User Scoping in DB Queries (`db.py`)
- `list_conversations(user_id)`:
  - If `user_id` is set → `WHERE c.user_id = ? OR c.user_id IS NULL` (line 257)
  - If `user_id` is None → no WHERE clause, returns ALL conversations (line 264)
- `get_conversation(conv_id, user_id)`:
  - If `user_id` is set → `WHERE id = ? AND (user_id = ? OR user_id IS NULL)` (line 293)
  - If `user_id` is None → `WHERE id = ?` (line 299)

### Frontend Flow
- **`api.ts`**: `authFetch()` wraps `fetch()` with `credentials: "include"` + CSRF token header for POST/PUT/DELETE
- **`history.ts`**: Thin wrapper — `loadConversations()` → `listConversations()`, `saveConversation()` → `createConversation()` + `apiSaveMessages()`
- **`App.tsx`**:
  - Init effect (line 250): runs `migrateLocalStorageToSQLite()` then `loadConversations()` on mount
  - URL sync effect (line 113): if URL has `/c/{id}`, calls `getConversation(id)` — redirects to `/` if null
  - `sendMessage()` (line 292): creates conversation via API if new, then starts SSE chat
  - Post-stream effect (line 259): calls `appendMessages()` then reloads conversation list

### Auth Integration
- **`useAuth.ts`**: `checkAuth()` calls `GET /api/auth/me`, if unauthenticated tries `POST /api/auth/refresh`, runs once on mount
- **`AuthContext.tsx`**: Wraps `useAuth`, exposes `{ user, isAuthenticated, authRequired, loading, signIn, signOut, checkAuth }`
- **Auth gate in sendMessage**: `if (authRequired && !isAuthenticated) { setShowAuthModal(true); return; }`
- **Backend auth bypass**: When `GOOGLE_CLIENT_ID` is empty, `get_current_user()` returns `_DEV_USER` (id="dev"), `handle_me()` returns `{authenticated: true, auth_required: false}`

### Cookie Configuration (`auth.py:78-100`)
| Cookie | Path | Max-Age | HttpOnly | Secure (prod) |
|--------|------|---------|----------|----------------|
| `access_token` | `/` | 900 (15 min) | Yes | Yes |
| `refresh_token` | `/api/auth` | 604800 (7 days) | Yes | Yes |
| `csrf_token` | `/` | 900 (15 min) | No | Yes |

## Production Conversation Persistence — Fixed (2026-06-05)

**Original symptom**: Signed-in user's conversations didn't persist — not appearing in history, refreshing a conversation URL redirected to home. Worked locally (auth disabled).

### Root Causes (all three fixed)

1. **Silent write failures**: `createConversation()`, `saveMessages()`, and other write functions in `api.ts` didn't check `resp.ok`. Fixed: all write functions now `throw` on non-OK responses.

2. **Auth/conversation race condition**: `checkAuth()` and `loadConversations()` fired as independent `useEffect` hooks. Fixed: init effect gated on `!authLoading` so conversations load after auth resolves.

3. **No 401-interceptor**: Expired access tokens weren't refreshed for API calls. Fixed: `authFetch()` now intercepts 401 responses, attempts `POST /api/auth/refresh` (raw fetch to avoid recursion), coalesces concurrent refreshes via module-level `_refreshPromise`, re-reads CSRF cookie, retries original request.

### Additional Production Issues Fixed (same deploy cycle)

4. **CSP blocking external resources**: Added `https://static.cloudflareinsights.com` (script-src), `https://fonts.googleapis.com` (style-src), `https://fonts.gstatic.com` (font-src), `https://lh3.googleusercontent.com` (img-src for Google avatars), `https://*.ingest.de.sentry.io` (connect-src for Sentry).

5. **SSE stream dying silently**: Unprotected async calls in `_event_stream()` could crash the generator before any SSE chunk was yielded. Fixed: fatal calls wrapped in try-except that yields error event; non-fatal calls wrapped separately. Frontend now detects missing `done` event and shows "Connection lost" error.

6. **HTTP 413 on message saves**: nginx's default 1MB `client_max_body_size` too small for context/mapData blobs. Fixed: (a) `client_max_body_size 16m` on `/api/` and `/chat` location blocks, (b) frontend strips `context`/`plan`/`mapData` from history sent to `/chat` — only sends `{role, content}`.

7. **OOM kills (exit code 137) on heavy queries**: "Can I open a bar at 2200 W Chicago" triggers 10+ parallel retrieval tasks. Embedding model (~500MB) + reranker (~1.3GB) + Python/PyTorch (~500MB) exceeded 4GB server RAM. Fixed: concurrency semaphore (`asyncio.Semaphore(4)`); blocking ML model preload at startup; reranker disabled in production (`RERANKER_ENABLED=false`).

### Files Changed

| File | Changes |
|------|---------|
| `frontend/src/lib/api.ts` | 401-interceptor with `_tryRefresh()` coalescing; `if (!resp.ok) throw` on all write functions |
| `frontend/src/App.tsx` | Auth-gated init effect; try/catch on `createConversation()`; `.catch()` on `appendMessages()` |
| `frontend/src/lib/useAuth.ts` | `console.log("[auth] ...")` at each decision point for production debugging |
| `frontend/src/lib/useChat.ts` | History stripping (`{role, content}` only); `receivedDone` flag for stream close detection |
| `frontend/nginx.prod.conf` | CSP header updates (lines 26, 54); `client_max_body_size 16m` on `/api/` and `/chat` |
| `backend/main.py` | `_RETRIEVAL_SEM` concurrency limiter; `_event_stream()` error wrapping; blocking ML preload |
| `docker-compose.prod.yml` | `RERANKER_ENABLED=false` for backend service |

### Testing Method

1. Deploy: push to main → SSH → `git fetch && git merge origin/main && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
2. Watch `docker compose logs -f backend` for startup (model preload, health check) and request processing
3. Browser console: `[auth]` logs for auth flow, CSP errors, network tab for 4xx/5xx
4. Heavy query stress test: "Can I open a bar at 2200 W Chicago" (10+ parallel retrievals)
5. Light query: "Tell me about the property at 1425 N Wells St" (single domain, basic flow)
6. Persistence: refresh page after query, verify conversation appears in history
7. Server OOM check: `dmesg | grep -i -E 'oom|kill|memory'` (exit code 137 = SIGKILL from OOM killer)

### Key Design Notes
- `verify_csrf()` exists in `auth.py:186` but is **never called** as a FastAPI dependency — CSRF is not enforced on any endpoint
- The 401-interceptor uses raw `fetch` (not `authFetch`) for the refresh call to avoid infinite recursion
- A module-level `_refreshPromise` coalesces concurrent 401s — only one refresh request fires
- After refresh, CSRF token is re-read from `document.cookie` since refresh sets a new one
- The SSE `/chat` endpoint doesn't use `get_current_user()` at all — unaffected by auth issues

### Production Environment Reference
- Server: Hetzner CX22 at 178.105.184.66, `/opt/urbanlayer`
- Docker: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
- Database: SQLite at `/app/backend/data/chicago.db` (Docker volume `backend_data`)
- Production .env should have: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `JWT_SECRET`, `AUTH_COOKIE_SECURE=true`, `FRONTEND_URL=https://urbanlayerchicago.com`, `CORS_ORIGINS=["https://urbanlayerchicago.com","https://www.urbanlayerchicago.com"]`
- Auth setup documented in `claude-context/deployment-plan.md` Phase "Google Cloud OAuth Setup"
