import i18n from "./i18n";
import type { DataDate } from "./dataDates";
import type { FailedSource } from "./failedSources";
import { parseSSE } from "./sse";
import { flush, getVisitorId, track } from "./tracking";
import type {
  PinsResponse as DiscoveryPinsResponse,
  ResultRow as DiscoveryResultRow,
  Registry as DiscoveryRegistry,
  SearchRequest as DiscoverySearchRequest,
  TextPreview as DiscoveryTextPreview,
  SearchResponse as DiscoverySearchResponse,
} from "../discovery/types";
import type {
  AddressSuggestion,
  AdminOverview,
  Amendment,
  BenchmarkResults,
  ChatChunk,
  CodeChunk,
  ContextObject,
  Conversation,
  ConversationDetail,
  ConversationStats,
  EngagementMetrics,
  JudgeResults,
  LatencyPercentiles,
  MapData,
  Message,
  RequestLogEntry,
  SelectedParcel,
  SinceThenResult,
  TimeseriesBucket,
  UploadMeta,
} from "./types";
import type { ParcelMapLayers } from "./parcelMap";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8001";

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return match?.[1] ?? "";
}

let _refreshPromise: Promise<boolean> | null = null;
// False once we know there's no session to refresh (anonymous visitor, or a
// refresh already failed), so a 401 doesn't trigger a refresh that can only
// 401 too. Anonymous page loads used to log two or three of those errors.
let _sessionMayRefresh = true;

async function _tryRefresh(): Promise<boolean> {
  if (_refreshPromise) return _refreshPromise;
  _refreshPromise = (async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": getCsrfToken() },
      });
      return resp.ok;
    } catch {
      return false;
    } finally {
      _refreshPromise = null;
    }
  })();
  return _refreshPromise;
}

// The double-submit CSRF cookie is issued by GET /api/auth/me. A page whose first
// request is a POST (Discovery auto-runs a search on load) could fire before that
// call returned, send an empty token, and get a 403 — an empty results page on a
// first visit. Unsafe requests wait for the cookie instead (one shared request).
let _csrfPromise: Promise<void> | null = null;

function ensureCsrfCookie(): Promise<void> {
  if (getCsrfToken()) return Promise.resolve();
  _csrfPromise ??= fetch(`${API_BASE}/api/auth/me`, { credentials: "include" })
    .then(() => undefined, () => undefined)
    .finally(() => { _csrfPromise = null; });
  return _csrfPromise;
}

async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const method = (options.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") await ensureCsrfCookie();
  const buildHeaders = () => {
    const csrfHeaders: Record<string, string> =
      method !== "GET" && method !== "HEAD"
        ? { "X-CSRF-Token": getCsrfToken() }
        : {};
    return { ...csrfHeaders, ...(options.headers as Record<string, string>) };
  };

  const resp = await fetch(url, {
    ...options,
    credentials: "include",
    headers: buildHeaders(),
  });

  if (resp.status === 401 && _sessionMayRefresh) {
    const refreshed = await _tryRefresh();
    if (!refreshed) _sessionMayRefresh = false;
    if (refreshed) {
      return fetch(url, {
        ...options,
        credentials: "include",
        headers: buildHeaders(),
      });
    }
  }

  return resp;
}

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  picture_url: string | null;
  tier: "free" | "premium" | "admin";
}

export interface AuthStatus {
  authenticated: boolean;
  auth_required: boolean;
  user: AuthUser | null;
  /** Unauthenticated only: whether a refresh cookie exists (it's httponly). */
  can_refresh?: boolean;
}

export async function getAuthStatus(): Promise<AuthStatus> {
  const resp = await authFetch(`${API_BASE}/api/auth/me`);
  if (!resp.ok) return { authenticated: false, auth_required: true, user: null };
  const status: AuthStatus = await resp.json();
  _sessionMayRefresh = status.authenticated || !!status.can_refresh;
  return status;
}

export async function refreshAuthToken(): Promise<AuthStatus | null> {
  // Plain fetch: going through authFetch would retry a failed refresh via the
  // 401 handler, i.e. call this same endpoint twice.
  const resp = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: { "X-CSRF-Token": getCsrfToken() },
  });
  if (!resp.ok) {
    _sessionMayRefresh = false;
    return null;
  }
  const data = await resp.json();
  return {
    authenticated: true,
    auth_required: true,
    user: data.user,
  };
}

export async function logout(): Promise<void> {
  await authFetch(`${API_BASE}/api/auth/logout`, { method: "POST" });
}

export function getSignInUrl(): string {
  return `${API_BASE}/api/auth/google`;
}

// ---------------------------------------------------------------------------
// Payments API
// ---------------------------------------------------------------------------

export async function subscribeNewsletter(email: string, source: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/newsletter`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, source }),
  });
  if (!resp.ok) throw new Error("Failed to subscribe");
}

export async function createCheckoutSession(): Promise<{ url: string }> {
  track("checkout_started", { type: "subscription" });
  flush(); // the page is about to redirect to Stripe
  const resp = await authFetch(`${API_BASE}/api/checkout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ visitor_id: getVisitorId() }),
  });
  if (!resp.ok) throw new Error("Failed to create checkout session");
  return resp.json();
}

export async function getSubscription(): Promise<{
  tier: string;
  stripe_customer_id: string | null;
  subscription_active: boolean;
  comp_until: number | null;
}> {
  const resp = await authFetch(`${API_BASE}/api/subscription`);
  if (!resp.ok) throw new Error("Failed to get subscription");
  return resp.json();
}

// Voucher redemption failure reasons, mapped from the endpoint's status codes.
export type VoucherRedeemError = "invalid" | "already_redeemed" | "exhausted" | "error";

export async function redeemVoucher(
  code: string,
): Promise<{ ok: true; premium_until: number } | { ok: false; reason: VoucherRedeemError }> {
  try {
    const resp = await authFetch(`${API_BASE}/api/voucher/redeem`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    if (resp.ok) {
      const data = await resp.json();
      return { ok: true, premium_until: data.premium_until };
    }
    const reason: VoucherRedeemError =
      resp.status === 404 || resp.status === 400
        ? "invalid"
        : resp.status === 409
          ? "already_redeemed"
          : resp.status === 410
            ? "exhausted"
            : "error";
    return { ok: false, reason };
  } catch {
    return { ok: false, reason: "error" };
  }
}

export async function createReportCheckoutSession(
  parcel: SelectedParcel,
): Promise<{ url: string }> {
  track("checkout_started", { type: "report", pin: parcel.pin ?? null });
  flush(); // the page is about to redirect to Stripe
  // pin+address+lat+lon travel together: lat/lon let the backend skip
  // re-resolution, address stays display-only metadata on the purchase row.
  const resp = await authFetch(`${API_BASE}/api/checkout/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      address: parcel.address ?? "",
      lat: parcel.lat,
      lon: parcel.lon,
      pin: parcel.pin ?? undefined,
      language: i18n.language && i18n.language !== "en" ? i18n.language : undefined,
      visitor_id: getVisitorId(),
    }),
  });
  if (!resp.ok) throw new Error("Failed to create report checkout session");
  return resp.json();
}

export interface PaymentsStatus {
  reports: boolean;
  subscriptions: boolean;
}

let _paymentsStatus: Promise<PaymentsStatus> | null = null;

/** Which purchases can start (Stripe configured). Fetched once per page load.
 *  If the check itself fails, purchases are treated as unavailable: a
 *  "coming soon" note beats a buy button that silently does nothing. */
export function fetchPaymentsStatus(): Promise<PaymentsStatus> {
  _paymentsStatus ??= fetch(`${API_BASE}/api/payments/status`)
    .then((r) => (r.ok ? r.json() : { reports: false, subscriptions: false }))
    .catch(() => ({ reports: false, subscriptions: false }));
  return _paymentsStatus;
}

export async function checkReportAccess(
  parcel: SelectedParcel,
): Promise<{ has_access: boolean; reason: string }> {
  // lat/lon accompany the pin so _resolve_location short-circuits on the
  // explicit point instead of re-resolving the pin server-side.
  const qs = new URLSearchParams({
    lat: String(parcel.lat),
    lon: String(parcel.lon),
  });
  if (parcel.pin) qs.set("pin", parcel.pin);
  try {
    const resp = await authFetch(`${API_BASE}/api/report/access?${qs}`);
    if (!resp.ok) return { has_access: false, reason: "error" };
    return resp.json();
  } catch {
    return { has_access: false, reason: "error" };
  }
}

export interface ReportPurchase {
  id: number;
  address: string | null;
  pin: string | null;
  lat: number;
  lon: number;
  amount_cents: number;
  created_at: number;
  completed_at: number | null;
  /** The first report this purchase rendered, kept as sold (WS6 M8). Null for a purchase made before originals
      were kept: its next download becomes one. `available` is false if the stored file has gone missing. */
  original?: { rendered_at: number; available: boolean } | null;
  /** The original's facts against today's (WS6 M9). Null when there is no original to compare, or the check failed. */
  changes?: SinceThenResult | null;
}

export async function fetchMyPurchases(): Promise<ReportPurchase[]> {
  const resp = await authFetch(`${API_BASE}/api/me/purchases`);
  if (!resp.ok) throw new Error(`Failed to load purchases: ${resp.status}`);
  const data = await resp.json();
  return data.purchases;
}

export async function deleteAccount(): Promise<void> {
  const resp = await authFetch(`${API_BASE}/api/me`, { method: "DELETE" });
  if (!resp.ok) {
    const detail = (await resp.json().catch(() => null))?.detail;
    throw new Error(
      typeof detail === "string" ? detail : `Failed to delete account (${resp.status})`,
    );
  }
}

export async function createBillingPortal(): Promise<{ url: string }> {
  const resp = await authFetch(`${API_BASE}/api/billing/portal`, { method: "POST" });
  if (!resp.ok) throw new Error("Failed to create billing portal session");
  return resp.json();
}

// Sections are immutable, so cache by ID — lets hover-prefetch and the
// subsequent click share one request. Failed lookups are evicted so they retry.
const sectionCache = new Map<string, Promise<CodeChunk | SectionNotCodified | null>>();

/** A 404 that is not "no such section": an amendment passed after the code text's vintage
 * added the section (17-3-0600), so the text isn't published yet. */
export interface SectionNotCodified {
  not_in_published_code: true;
  section_id: string;
  message: string;
  added_by: Amendment[];
}

export function isNotCodified(x: unknown): x is SectionNotCodified {
  return !!x && typeof x === "object" && (x as SectionNotCodified).not_in_published_code === true;
}

async function notCodifiedFrom(resp: Response): Promise<SectionNotCodified | null> {
  if (resp.status !== 404) return null;
  try {
    const body = await resp.json();
    return isNotCodified(body?.detail) ? body.detail : null;
  } catch {
    return null;
  }
}

export function fetchSection(sectionId: string): Promise<CodeChunk | SectionNotCodified | null> {
  const key = sectionId.trim();
  const hit = sectionCache.get(key);
  if (hit) return hit;
  const p = (async () => {
    try {
      const resp = await authFetch(`${API_BASE}/section/${encodeURIComponent(key)}`);
      if (!resp.ok) return notCodifiedFrom(resp);
      return (await resp.json()) as CodeChunk;
    } catch {
      return null;
    }
  })();
  sectionCache.set(key, p);
  p.then((r) => {
    if (r === null) sectionCache.delete(key);
  });
  return p;
}

export async function getAutocomplete(query: string): Promise<AddressSuggestion[]> {
  if (query.length < 3) return [];
  try {
    const resp = await authFetch(`${API_BASE}/autocomplete?q=${encodeURIComponent(query)}`);
    if (!resp.ok) return [];
    return await resp.json();
  } catch {
    return [];
  }
}

export async function fetchMapData(params: {
  community_area: number;
  time_range_days: number;
  sources?: string[];
  address_lat?: number;
  address_lon?: number;
  address_label?: string;
}): Promise<MapData | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/map-data`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!resp.ok) return null;
    return (await resp.json()) as MapData;
  } catch {
    return null;
  }
}

export class ChatStreamError extends Error {
  status: number;
  detail: string | null;

  constructor(status: number, statusText: string, detail: string | null) {
    super(detail ?? `Chat request failed: ${status} ${statusText}`);
    this.name = "ChatStreamError";
    this.status = status;
    this.detail = detail;
  }
}

export async function* chatStream(
  message: string,
  history: Message[],
  signal?: AbortSignal,
  conversationId?: string | null,
  uploadIds?: string[],
  cachedCommunityArea?: number | null,
  language?: string,
  parcelPin?: string | null,
  scorecardContext?: import("./types").ScorecardContext | null,
): AsyncGenerator<ChatChunk, void, unknown> {
  const body: Record<string, unknown> = { message, history };
  if (conversationId) body.conversation_id = conversationId;
  if (uploadIds?.length) body.upload_ids = uploadIds;
  if (cachedCommunityArea != null) body.cached_community_area = cachedCommunityArea;
  if (language && language !== "en") body.language = language;
  if (parcelPin) body.parcel_pin = parcelPin;
  // Pre-resolved parcel grounding (Scorecard handoff). Paired with parcel_pin so
  // the backend gate (plan.location.pin == sc.pin) can match this turn.
  if (scorecardContext) body.scorecard_context = scorecardContext;

  const resp = await authFetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!resp.ok || !resp.body) {
    const errBody = await resp.json().catch(() => null);
    const detail = typeof errBody?.detail === "string" ? errBody.detail : null;
    throw new ChatStreamError(resp.status, resp.statusText, detail);
  }

  yield* parseSSE<ChatChunk>(resp.body.getReader());
}

// ---------------------------------------------------------------------------
// Conversation CRUD
// ---------------------------------------------------------------------------

export async function listConversations(): Promise<Conversation[]> {
  const resp = await authFetch(`${API_BASE}/api/conversations`);
  if (!resp.ok) {
    console.error(`Failed to list conversations: ${resp.status} ${resp.statusText}`);
    return [];
  }
  const data = await resp.json();
  return data.map((c: Record<string, unknown>) => ({
    id: c.id,
    title: c.title,
    language: (c.language as string) || "en",
    message_count: c.message_count,
    createdAt: c.created_at,
    updatedAt: c.updated_at,
  }));
}

export async function getConversation(id: string): Promise<ConversationDetail | null> {
  const resp = await authFetch(`${API_BASE}/api/conversations/${encodeURIComponent(id)}`);
  if (!resp.ok) {
    console.error(`Failed to load conversation ${id}: ${resp.status} ${resp.statusText}`);
    return null;
  }
  return await resp.json();
}

export async function createConversation(id: string, title: string, language?: string): Promise<void> {
  const body: Record<string, string> = { id, title };
  if (language && language !== "en") body.language = language;
  const resp = await authFetch(`${API_BASE}/api/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`Failed to create conversation: ${resp.status}`);
}

export async function deleteConversationAPI(id: string): Promise<void> {
  const resp = await authFetch(`${API_BASE}/api/conversations/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!resp.ok) throw new Error(`Failed to delete conversation: ${resp.status}`);
}

export async function saveMessages(
  conversationId: string,
  messages: Record<string, unknown>[],
): Promise<void> {
  const resp = await authFetch(
    `${API_BASE}/api/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    },
  );
  if (!resp.ok) throw new Error(`Failed to save messages: ${resp.status}`);
}

export async function updateMessageMapData(
  conversationId: string,
  position: number,
  mapData: MapData,
): Promise<void> {
  const resp = await authFetch(
    `${API_BASE}/api/conversations/${encodeURIComponent(conversationId)}/messages/${position}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ map_data: mapData, map_fetched_at: Date.now() }),
    },
  );
  if (!resp.ok) throw new Error(`Failed to update map data: ${resp.status}`);
}

export async function importConversations(
  conversations: Record<string, unknown>[],
): Promise<number> {
  const resp = await authFetch(`${API_BASE}/api/conversations/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversations }),
  });
  if (!resp.ok) return 0;
  const data = await resp.json();
  return data.imported ?? 0;
}

export async function clearAllConversations(): Promise<void> {
  const resp = await authFetch(`${API_BASE}/api/conversations`, { method: "DELETE" });
  if (!resp.ok) throw new Error(`Failed to clear conversations: ${resp.status}`);
}

// ---------------------------------------------------------------------------
// Conversation sharing
// ---------------------------------------------------------------------------

export async function createShareLink(
  conversationId: string,
): Promise<{ token: string; url: string } | null> {
  const resp = await authFetch(
    `${API_BASE}/api/conversations/${encodeURIComponent(conversationId)}/share`,
    { method: "POST" },
  );
  if (!resp.ok) return null;
  return await resp.json();
}

export async function revokeShareLink(conversationId: string): Promise<boolean> {
  const resp = await authFetch(
    `${API_BASE}/api/conversations/${encodeURIComponent(conversationId)}/share`,
    { method: "DELETE" },
  );
  return resp.ok;
}

export async function getShareStatus(
  conversationId: string,
): Promise<{ shared: boolean; token?: string; url?: string; created_at?: number }> {
  const resp = await authFetch(
    `${API_BASE}/api/conversations/${encodeURIComponent(conversationId)}/share`,
  );
  if (!resp.ok) return { shared: false };
  return await resp.json();
}

/** "Since then" notes for each parcel answer of a conversation, keyed by message index. Never throws:
    a failed check just means no note. */
export async function getConversationChanges(id: string): Promise<Record<string, SinceThenResult>> {
  try {
    const resp = await authFetch(`${API_BASE}/api/conversations/${encodeURIComponent(id)}/changes`);
    if (!resp.ok) return {};
    return (await resp.json()).notes ?? {};
  } catch {
    return {};
  }
}

export async function getSharedChanges(token: string): Promise<Record<string, SinceThenResult>> {
  try {
    const resp = await fetch(`${API_BASE}/api/share/${encodeURIComponent(token)}/changes`);
    if (!resp.ok) return {};
    return (await resp.json()).notes ?? {};
  } catch {
    return {};
  }
}

export async function getSharedConversation(
  token: string,
): Promise<ConversationDetail | null> {
  const resp = await fetch(`${API_BASE}/api/share/${encodeURIComponent(token)}`);
  if (!resp.ok) return null;
  return await resp.json();
}

// ---------------------------------------------------------------------------
// File uploads
// ---------------------------------------------------------------------------

export async function uploadFiles(
  conversationId: string,
  files: File[],
): Promise<UploadMeta[]> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  const resp = await authFetch(
    `${API_BASE}/api/conversations/${encodeURIComponent(conversationId)}/uploads`,
    { method: "POST", body: formData },
  );
  if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`);
  const data = await resp.json();
  return data.uploads;
}

export function getUploadUrl(uploadId: string): string {
  return `${API_BASE}/api/uploads/${encodeURIComponent(uploadId)}/file`;
}

// ---------------------------------------------------------------------------
// Admin API
// ---------------------------------------------------------------------------

export interface VoucherRedemption {
  user_id: string;
  redeemed_at: number;
  email: string | null;
  name: string | null;
}

export interface AdminVoucher {
  code: string;
  label: string | null;
  duration_days: number;
  max_redemptions: number;
  disabled: number;
  created_at: number;
  redemptions: VoucherRedemption[];
}

export async function fetchAdminVouchers(): Promise<AdminVoucher[]> {
  try {
    const resp = await authFetch(`${API_BASE}/api/admin/vouchers`);
    if (!resp.ok) return [];
    return (await resp.json()).vouchers;
  } catch { return []; }
}

export async function createAdminVoucher(params: {
  label: string;
  duration_days: number;
  max_redemptions: number;
  code?: string;
}): Promise<AdminVoucher> {
  const resp = await authFetch(`${API_BASE}/api/admin/vouchers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!resp.ok) {
    const detail = (await resp.json().catch(() => null))?.detail;
    throw new Error(typeof detail === "string" ? detail : "Failed to create voucher");
  }
  return resp.json();
}

export async function adminGrantPremium(
  email: string,
  days: number,
): Promise<{ email: string; premium_until: number }> {
  const resp = await authFetch(`${API_BASE}/api/admin/grant`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, days }),
  });
  if (!resp.ok) {
    const detail = (await resp.json().catch(() => null))?.detail;
    throw new Error(typeof detail === "string" ? detail : "Failed to grant access");
  }
  return resp.json();
}

export async function fetchAdminEngagement(period: string): Promise<EngagementMetrics | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/admin/engagement?period=${period}`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

export async function fetchAdminOverview(period: string): Promise<AdminOverview | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/admin/overview?period=${period}`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

export async function fetchAdminTimeseries(
  period: string, bucket = "day",
): Promise<TimeseriesBucket[]> {
  try {
    const resp = await authFetch(
      `${API_BASE}/api/admin/timeseries?period=${period}&bucket=${bucket}`,
    );
    if (!resp.ok) return [];
    return await resp.json();
  } catch { return []; }
}

export async function fetchAdminLatency(period: string): Promise<LatencyPercentiles[]> {
  try {
    const resp = await authFetch(`${API_BASE}/api/admin/latency?period=${period}`);
    if (!resp.ok) return [];
    return await resp.json();
  } catch { return []; }
}

export async function fetchConversationStats(): Promise<ConversationStats | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/admin/conversations`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

export async function fetchRequestLogs(
  limit = 50, offset = 0,
): Promise<RequestLogEntry[]> {
  try {
    const resp = await authFetch(
      `${API_BASE}/api/admin/requests?limit=${limit}&offset=${offset}`,
    );
    if (!resp.ok) return [];
    return await resp.json();
  } catch { return []; }
}

/** The admin "Code currency" card: how current the code text is and how well the gap is handled. */
export interface AdminCodeCurrency {
  code: {
    source_id: string;
    as_of: string | null;
    ingested_at: string | null;
    age_days: number | null;
    lag: {
      title17_passed_since: number | null;
      cited_other_passed_since: number | null;
      unreviewed: number;
      oldest_unreviewed_days: number | null;
      uncodified_applied: number;
    };
    last_checked: string | null;
    check_state: "fresh" | "aging" | "unknown";
    status: "green" | "amber" | "red";
    reasons: string[];
  };
  clerk: {
    last_success: string | null;
    last_attempt: string | null;
    last_error: string | null;
    consecutive_failures: number;
    snapshot_state: string;
    contract_ok: boolean;
    contract_problems: string[];
  };
  map_lag?: AdminMapLag | null;
  /** Passed Chicago Landmark designations and how many we could place on a parcel (WS1 M5b). */
  designations?: AdminDesignations | null;
  amendments: Amendment[];
}

/** Passed rezonings the City's zoning map lacks (WS1 M5). Counts are null until the check has succeeded once. */
export interface AdminMapLag {
  source_id: string;
  passed_not_on_map: number | null;
  oldest_days: number | null;
  flaggable: number | null;
  with_parcels: number | null;
  unparsed_titles: number | null;
  unparsed: string[];
  no_parcels: string[];
  check_status: "ok" | "failed" | "missing";
  last_checked: string | null;
  last_error: string | null;
}

export interface AdminDesignations {
  passed: number | null;
  flaggable: number | null;
  with_parcels: number | null;
  unparsed_titles: number | null;
  unparsed: string[];
  no_parcels: string[];
  check_status: "ok" | "failed" | "missing";
  last_checked: string | null;
  last_error: string | null;
}

export async function fetchAdminCodeCurrency(): Promise<AdminCodeCurrency | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/admin/code-currency`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

/** The admin "Data health" panel (WS6 M3): the source registry joined with the daily checker's stored status. */
export type SourceState = "alarm" | "error" | "warn" | "unknown" | "acked" | "ok" | "frozen_ok";

export interface DataHealthSource {
  id: string;
  name: string;
  publisher: string | null;
  link: string | null;
  tier: string | null;
  kind: string | null;
  severity: "critical" | "standard" | "info";
  owner_modules: string[];
  surfaces: string[];
  state: SourceState;
  reason: string;
  as_of: string | null;
  basis: "content" | "published" | null;
  age_days: number | null;
  warn_days: number | null;
  alarm_days: number | null;
  frozen: string | null;
  contract: { layer_name: string | null; required_fields: string[]; count_band: number[] | null; values?: string[] } | null;
  ack: { reason: string; until: string; owner: string } | null;
  state_since: string | null;
  checked_at: string | null;
  probe_error: boolean;
  latency_ms: number | null;
  requests: number | null;
  note: string;
}

export interface DataHealth {
  checker: {
    state: "ok" | "late";
    last_run: string | null;
    age_h: number | null;
    late_after_h: number;
    next_run: string | null;
    last_error: string | null;
    runs: { started_at: string; finished_at: string | null; sources: number; alarms: number; requests: number; error: string | null }[];
  };
  counts: Partial<Record<SourceState, number>>;
  sources: DataHealthSource[];
}

export interface DataHealthHistory {
  source: string;
  history: { checked_at: string; state: SourceState; reason: string; as_of: string | null; age_days: number | null }[];
}

export async function fetchDataHealth(): Promise<DataHealth | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/admin/data-health`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

export async function fetchDataHealthHistory(source: string): Promise<DataHealthHistory | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/admin/data-health?source=${encodeURIComponent(source)}`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

export async function fetchBenchmarkResults(): Promise<BenchmarkResults | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/admin/benchmark`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

export async function fetchJudgeResults(): Promise<JudgeResults | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/admin/judge`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

// Deterministic Title-17 bulk standards (backend zoning_definitions.py via asdict)
export interface ZoneDefinition {
  zone_class: string;
  name: string;
  code_section: string;
  far: number | null;
  max_height: string | null;
  // Never populated: Title 17 has no base-district lot-coverage standard
  // (kept for payload stability; the card row simply doesn't render).
  lot_coverage: string | null;
  // Minimum lot SIZE (Table 17-2-0303) — R districts only.
  min_lot_sqft: number | null;
  // Minimum lot area PER DWELLING UNIT — the number that caps unit count (null for
  // districts with no per-unit minimum: PD, C3, M, DS).
  min_lot_area_per_unit?: number | null;
  lot_area_note?: string;
  uses: string;
  notes: string;
  is_fallback: boolean;
}

/** How the address became this parcel (backend/resolution.py). */
export interface ParcelResolutionRecord {
  method: "coordinates" | "pin" | "address_points" | "assessor_addresses" | "geocode_nearest" | "geocode_nearest_verified" | null;
  point_basis: "given" | "parcel_centroid" | "address_point" | "geocode" | null;
  input_address: string | null;
  pin: string | null;
  confidence: "authoritative" | "approximate" | null;
  point: { lat: number; lon: number };
  /** Feet from the matched point to the parcel polygon's center, when both are known. */
  centroid_gap_ft: number | null;
  /** Every parcel the two address sources list for the input address; the used one is marked. */
  candidates: { pin: string; sources: Array<"address_points" | "assessor_addresses">; used: boolean }[];
  multiple_parcels: boolean;
  /** The two official address sources name different parcels for this address. */
  sources_disagree: boolean;
  /** >0 when the matched PIN is a condominium building whose units each have their own PIN. */
  condo_units?: number;
  identity_unconfirmed: boolean;
  unverified_reason: "nearest_parcel_address_mismatch" | "property_record_is_another_parcel" | null;
  property_record_pin: string | null;
}

/** A dated source for one Profile fact (backend/provenance.py). */
export interface Provenance {
  label: string;
  kind: "official_record" | "code_text" | "derived";
  source: string | null;
  record_id: string | null;
  url: string | null;
  /** Code section id the source viewer can open (code_text entries). */
  section: string | null;
  /** When the source says it last changed / the code is current through. */
  as_of: string | null;
  /** When the rule took effect (e.g. the ordinance date). */
  effective_date: string | null;
  /** When we queried it. Always set. */
  query_date: string;
  note?: string | null;
  // --- schema v2 (backend/provenance.py; guide: claude-context/guides/source-confidence.md).
  // Every field below is additive and optional: older stored answers lack them.
  /** Authority tier: A record, B code text, C government estimate, D our calculation, E AI reading, F private. */
  tier?: ProvenanceTier;
  /** Data-health registry id (backend/data_health/registry.py). */
  source_id?: string | null;
  /** What `as_of` means. `record_updated` = one record's own edit date, not the dataset's currency. */
  as_of_basis?: ProvenanceAsOfBasis;
  /** A statistic's period, e.g. "2020–2024". */
  period?: string | null;
  age_days?: number | null;
  scope?: ProvenanceScope | null;
  geography?: string | null;
  /** Absent on a parcel record means "not applicable", not "unknown". */
  coverage?: ProvenanceCoverage | null;
  /** Absent means no error is published. */
  precision?: ProvenancePrecision | null;
  method_key?: ProvenanceMethodKey;
  method_params?: Record<string, unknown> | null;
  /** English fallback for the method; the UI translates by `method_key`. */
  method?: string;
  /** A calculation's inputs (fact ids or registry source ids) and the weakest input's tier. */
  inputs?: string[] | null;
  basis_tier?: ProvenanceTier | null;
  corroborated?: boolean | null;
  /** Computed once by the backend. Read it; never recompute it in a component. */
  confidence?: ProvenanceConfidence;
  confidence_reasons?: string[];
  /** The figure as displayed. */
  value?: string | number | boolean | null;
  /** The lot's outline is a whole development's, shared with this many other parcels (Item 59). */
  shared_outline_with?: number | null;
}

export type ProvenanceTier =
  | "official_record" | "official_publication" | "official_estimate"
  | "our_calculation" | "ai_extracted" | "non_government";
export type ProvenanceAsOfBasis =
  | "source_updated" | "record_updated" | "current_through" | "period_end" | "vintage" | "tax_year" | "queried";
export type ProvenanceScope = "parcel" | "address" | "radius" | "zip" | "tract" | "puma" | "community_area" | "city" | "county";
export type ProvenanceConfidence = "standard" | "low" | "withheld";
export type ProvenanceMethodKey =
  | "recorded" | "published_text" | "code_table" | "hand_reviewed"
  | "survey_estimate" | "government_model" | "bracket_median" | "calculation" | "keyword_grouping"
  | "ai_read_code" | "ai_read_ordinance" | "ai_read_filing" | "commercial_index";

export interface ProvenanceCoverage {
  n?: number | null;
  share?: number | null;
  universe?: string | null;
  unit?: string | null;
  /** Which n rule applies: an area sample (n < 30 withholds) or a comparable-sales set (fade < 5, withhold < 3). */
  sample?: "area_sample" | "comps" | null;
}

export interface ProvenancePrecision {
  moe?: number | null;
  moe_level?: number | null;
  cv?: number | null;
  /** How a margin we derived ourselves was derived (`acs_handbook_median`); absent when the publisher states it. */
  moe_method?: string | null;
  agreement?: { n: number; agree: number } | null;
}

export interface ScorecardResponse {
  address: string | null;
  lat: number;
  lon: number;
  community_area: number | null;
  community_area_name: string | null;
  context: ContextObject;
  comparables?: import("./types").ComparablesSummary | null;
  partial_failures: string[];
  resolved_pin: string | null;
  resolved_confidence: "authoritative" | "approximate";
  // True when identity is unconfirmed but the property/comps cards were filled
  // from a nearest (possibly-neighbor) parcel — the UI caveats those cards.
  nearest_parcel_unverified?: boolean;
  resolved_lat: number;
  resolved_lon: number;
  zone_definition?: ZoneDefinition | null;
  /** Where each fact came from and how current it is, keyed by fact id (zoning.district,
      zoning.far, overlay.<layer_type>, parcel.identity, ...). */
  provenance?: Record<string, Provenance>;
  /** The dates behind this page, in reading order (backend/data_health/vintages.py). */
  data_dates?: DataDate[];
  /** What couldn't be checked, by source key, with the words that reported it (backend/data_health/failures.py). */
  failed_sources?: FailedSource[];
  /** How the address became this parcel: method, every parcel at the address, disagreements. */
  resolution?: ParcelResolutionRecord;
  // True when the address-scoped violation lookup actually ran (parsed + queried).
  // Lets the UI show "no violations on record" for a confirmed-zero vs. omitting
  // for an unconfirmed lookup — silence must not mean two different things.
  violations_checked?: boolean;
  /** Sources only the new UI's Profile parts fetch (the Neighborhood tab, decision Item 102); absent from
      /api/scorecard. A key that is absent wasn't asked (or hasn't landed); a failed one is listed in `failed`. */
  next_ui?: NextUiData;
}

export interface CrimeSplit { violent: number; property: number; other: number }

export interface NextUiCrime {
  window_days: number;
  current: CrimeSplit;
  /** The same 90 days a year earlier; null when that comparison didn't answer. */
  prior: CrimeSplit | null;
  current_label?: string | null;
  prior_label?: string | null;
}

export interface NextUiSchoolReportCard {
  year: number;
  designation?: "Exemplary" | "Commendable" | "Targeted" | "Comprehensive" | "Intensive";
  /** CPS's 5Essentials culture-and-climate rating ("Well organized" … "Not yet organized"). */
  culture?: string;
  enrollment?: number;
  ela_pct?: number;
  math_pct?: number;
  graduation_4yr_pct?: number;
  ela_source?: "hs_assessment";
  math_source?: "hs_assessment";
}

export interface NextUiSchool {
  school_id: string;
  level: "elementary" | "high";
  name: string | null;
  grades: string | null;
  address: string | null;
  cps_url: string | null;
  report_card_url: string | null;
  report_card: NextUiSchoolReportCard | null;
}

export interface NextUiSchools {
  elementary: NextUiSchool | null;
  high: NextUiSchool | null;
  boundary_year: string;
  report_year: number | null;
  source?: string | null;
}

export interface ConstructionProject {
  permit: string | null;
  kind: "new" | "renovation";
  description: string | null;
  issued: string | null;
  cost: number | null;
  units_added: number | null;
  address: string | null;
  lat: number;
  lon: number;
  distance_mi: number;
  /** The City's status (ACTIVE, COMPLETE, SUSPENDED, ...) and stage (PERMIT ISSUED (FEE DUE), INSPECTIONS, ...). */
  status?: string | null;
  milestone?: string | null;
  applied?: string | null;
  processing_days?: number | null;
  review_type?: string | null;
}

/** A City building permit at this address (History, Item 103): the same fields as a permit nearby, any kind (signs,
    elevators, easy permits, … as "other" with the City's own `permit_type`), no distance. The permit page reads both. */
export interface AddressPermit extends Omit<ConstructionProject, "kind" | "lat" | "lon" | "distance_mi"> {
  kind: "new" | "renovation" | "demolition" | "other";
  permit_type: string | null;
  lat: number | null;
  lon: number | null;
  distance_mi: null;
}

export interface NextUiConstruction {
  radius_mi: number;
  months: number;
  renovation_cost_floor: number;
  projects: ConstructionProject[];
  capped: boolean;
}

export interface NextUiArea311 {
  days: number;
  total: number;
  top: Array<{ type: string; count: number }>;
}

export interface TractShare { key: string; pct: number; low: boolean }
export interface TractHeadline {
  median_age: number | null; housing_units: number | null; households: number | null; persons_per_household: number | null;
  travel_minutes: number | null; moved_pct: number | null; occupied_pct: number | null; per_capita_income: number | null;
  median_household_income: number | null; median_home_value: number | null;
}
export interface NextUiTract {
  tract: TractHeadline;
  city: TractHeadline | null;
  structure: TractShare[] | null; tenure: TractShare[] | null; occupancy: TractShare[] | null; moved_in: TractShare[] | null;
  home_value: TractShare[] | null; household_type: TractShare[] | null; mobility: TractShare[] | null;
  travel_time: TractShare[] | null; income: TractShare[] | null;
}

export interface NextUiData {
  crime?: NextUiCrime;
  schools?: NextUiSchools;
  construction_within?: NextUiConstruction;
  area_311?: NextUiArea311;
  /** The tract's housing, household, moving and commuting figures (Item 102), Chicago's headline figures beside. */
  tract?: NextUiTract;
  /** The community area's own figures (population, a bracket-estimated median income); null when none. */
  area_demographics?: import("./types").DemographicsSummary | null;
  /** The History tab (Item 103): the City's permits and violations at the address, every year on record; null when
      the address can't be searched by street fields. */
  permits_at_address?: { years: number; projects: AddressPermit[]; capped: boolean } | null;
  violations_at_address?: { years: number; violations: import("../ui-next/profile/historyModel").ViolationRow[]; capped: boolean } | null;
  /** Every source's value per building fact; null for vacant land. */
  building_records?: import("../ui-next/profile/historyModel").BuildingRecords | null;
  failed?: Array<"schools" | "construction_within" | "area_311" | "area_demographics" | "permits_at_address" | "violations_at_address" | "building_records">;
}

export async function fetchScorecard(params: {
  address?: string;
  lat?: number;
  lon?: number;
  pin?: string;
}): Promise<ScorecardResponse | null> {
  const qs = new URLSearchParams();
  if (params.address) qs.set("address", params.address);
  if (params.lat != null) qs.set("lat", String(params.lat));
  if (params.lon != null) qs.set("lon", String(params.lon));
  if (params.pin) qs.set("pin", params.pin);
  try {
    const resp = await authFetch(`${API_BASE}/api/scorecard?${qs}`);
    if (!resp.ok) {
      if (resp.status === 422) return null;
      return null;
    }
    return await resp.json();
  } catch { return null; }
}

/** The Profile's first screen (`/api/scorecard/first`, decision Item 82): identity, the district at the point with
    its Title 17 row, and for a PIN-resolved parcel the lot outline and area, by the full response's own rules.
    About 2 s cold; the full `/api/scorecard` response replaces it. A failed part is `*_unchecked`, never empty. */
export interface ScorecardFirst {
  address: string | null;
  resolved_pin: string | null;
  resolved_confidence: "authoritative" | "approximate";
  resolved_lat: number;
  resolved_lon: number;
  zoning: { zone_class: string; zone_type?: number | null } | null;
  zoning_unchecked: boolean;
  zone_definition: ZoneDefinition | null;
  lot: {
    pin14: string;
    land_sqft: number | null;
    land_sqft_source: "assessor" | "geometry" | null;
    parcel_geometry: GeoJSON.Geometry | null;
    shared_outline_with: number;
  } | null;
  lot_unchecked: boolean;
}

/** The first-screen request; null on any failure (the page then waits for the full response). */
export async function fetchScorecardFirst(params: {
  address?: string;
  lat?: number;
  lon?: number;
  pin?: string;
}, signal?: AbortSignal): Promise<ScorecardFirst | null> {
  const qs = new URLSearchParams();
  if (params.address) qs.set("address", params.address);
  if (params.lat != null) qs.set("lat", String(params.lat));
  if (params.lon != null) qs.set("lon", String(params.lon));
  if (params.pin) qs.set("pin", params.pin);
  try {
    const resp = await authFetch(`${API_BASE}/api/scorecard/first?${qs}`, { signal });
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

/** The new Profile's parts (decision Item 89, `backend/profile_parts.py`). The Overview resolves the parcel once and
    signs a `lookup`; each late part reads it and never resolves again. Every response carries the whole Profile
    assembled so far (`profile`, the `/api/scorecard` shape); the page keeps the highest `version` of a record. */
export type ProfileLatePart = "building" | "history" | "money" | "incentives" | "neighborhood" | "activity" | "block_face";

export interface ProfilePartResponse {
  part: "overview" | ProfileLatePart;
  lookup: string;
  record: string;
  version: number;
  parts_in: Array<"overview" | ProfileLatePart>;
  parts_pending: ProfileLatePart[];
  /** Sources of this part past their deadline: "couldn't check in time", never "none". */
  timed_out: string[];
  timed_out_by_part: Partial<Record<ProfileLatePart, string[]>>;
  profile: ScorecardResponse;
}

function parcelQs(params: { address?: string; lat?: number; lon?: number; pin?: string }): URLSearchParams {
  const qs = new URLSearchParams();
  if (params.address) qs.set("address", params.address);
  if (params.lat != null) qs.set("lat", String(params.lat));
  if (params.lon != null) qs.set("lon", String(params.lon));
  if (params.pin) qs.set("pin", params.pin);
  return qs;
}

/** The Overview part. `notFound` = the address didn't resolve to a Chicago parcel (422); `failed` = anything else. */
export async function fetchProfileOverview(
  params: { address?: string; lat?: number; lon?: number; pin?: string },
  signal?: AbortSignal,
): Promise<ProfilePartResponse | "notFound" | "failed"> {
  try {
    const resp = await authFetch(`${API_BASE}/api/profile/overview?${parcelQs(params)}`, { signal });
    if (resp.status === 422) return "notFound";
    if (!resp.ok) return "failed";
    return await resp.json();
  } catch { return "failed"; }
}

/** One late part. `expired` = the server no longer trusts the lookup (409): ask the Overview again. */
export async function fetchProfilePart(
  name: ProfileLatePart,
  lookup: string,
  have: string[],
  signal?: AbortSignal,
): Promise<ProfilePartResponse | "expired" | "failed"> {
  const qs = new URLSearchParams({ lookup });
  if (have.length) qs.set("have", have.join(","));
  try {
    const resp = await authFetch(`${API_BASE}/api/profile/part/${name}?${qs}`, { signal });
    if (resp.status === 409) return "expired";
    if (!resp.ok) return "failed";
    return await resp.json();
  } catch { return "failed"; }
}

/** One Municipal Code subsection (and the table it cites) with how current the code is. */
export interface CodeSubsection {
  section_id: string;
  article: string;
  article_title: string;
  heading: string;
  paragraphs: string[];
  /** Raw "Columns: ... / Row n: ..." text, one entry per table. */
  tables: string[];
  current_through: string | null;
  vintage_label: string | null;
  source: string | null;
  /** Amendments passed after this text was published that touch the section. */
  amended_since?: Amendment[];
}

const subsectionCache = new Map<string, Promise<CodeSubsection | SectionNotCodified | null>>();

export function fetchCodeSubsection(sectionId: string): Promise<CodeSubsection | SectionNotCodified | null> {
  const key = sectionId.trim();
  const hit = subsectionCache.get(key);
  if (hit) return hit;
  const p = (async () => {
    try {
      const resp = await authFetch(`${API_BASE}/api/code/section/${encodeURIComponent(key)}`);
      return resp.ok ? ((await resp.json()) as CodeSubsection) : await notCodifiedFrom(resp);
    } catch {
      return null;
    }
  })();
  subsectionCache.set(key, p);
  p.then((r) => {
    if (r === null) subsectionCache.delete(key);
  });
  return p;
}

/** The PDF report. ``copy`` picks which: "original" is the first report this purchase rendered, kept as sold;
    "updated" (and the default) is a live render with today's data, labeled once an original exists. A purchase's
    first download becomes its original whichever is asked for. */
export async function fetchReport(parcel: SelectedParcel, copy?: "original" | "updated"): Promise<Blob | null> {
  // Highest-fidelity key only: pin → address → coords (never downgrade).
  const qs = new URLSearchParams();
  if (parcel.pin) {
    qs.set("pin", parcel.pin);
  } else if (parcel.address) {
    qs.set("address", parcel.address);
  } else {
    qs.set("lat", String(parcel.lat));
    qs.set("lon", String(parcel.lon));
  }
  if (i18n.language && i18n.language !== "en") qs.set("language", i18n.language);
  if (copy) qs.set("copy", copy);
  try {
    const resp = await authFetch(`${API_BASE}/api/report?${qs}`);
    if (!resp.ok) return null;
    return await resp.blob();
  } catch { return null; }
}

// --- Property Discovery (filter/search) ---

export async function fetchDiscoveryRegistry(): Promise<DiscoveryRegistry | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/discovery/registry`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

// `signal` lets the page abort a superseded search. An aborted request resolves to null like
// any other failure; the caller tells them apart by checking its own signal/request id.
export async function discoverySearch(
  req: DiscoverySearchRequest,
  signal?: AbortSignal,
): Promise<DiscoverySearchResponse | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/discovery/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal,
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

// Full ordered coord set for the map (PR6) — decoupled from the paginated list.
export async function discoverySearchPins(
  req: DiscoverySearchRequest,
  signal?: AbortSignal,
): Promise<DiscoveryPinsResponse | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/discovery/search/pins`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal,
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

// One result row by PIN, for the map's dot preview (decision Item 57). null when the parcel is not in the
// current index or the request fails; the preview then shows what the dot itself carries.
export async function discoveryParcelRow(pin: string, sort: string, signal?: AbortSignal): Promise<DiscoveryResultRow | null> {
  try {
    const qs = new URLSearchParams({ pin, sort });
    const resp = await authFetch(`${API_BASE}/api/discovery/parcel?${qs}`, { signal });
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

// A map outline's lot (decision Item 68): found, not in the index (404), or the read failed. The outline
// preview words these three apart, so a failed read never says "not in our data".
export type DiscoveryOutlineLookup =
  | { status: "found"; row: DiscoveryResultRow }
  | { status: "missing" }
  | { status: "failed" };

export async function discoveryOutlineRow(pin10: string, sort: string, signal?: AbortSignal): Promise<DiscoveryOutlineLookup> {
  try {
    const qs = new URLSearchParams({ pin: pin10, sort });
    const resp = await authFetch(`${API_BASE}/api/discovery/parcel?${qs}`, { signal });
    if (resp.status === 404) return { status: "missing" };
    if (!resp.ok) return { status: "failed" };
    return { status: "found", row: await resp.json() };
  } catch { return { status: "failed" }; }
}

// Compile-only: what the free-text compiler makes of a phrase (no search, no index read).
// null on any failure, so the caller can fail open and just search.
export async function discoveryTextPreview(
  text: string,
  signal?: AbortSignal,
): Promise<DiscoveryTextPreview | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/discovery/text-preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal,
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

// Full-match-set CSV export (PR7). Premium-gated server-side (free tier → 403). Streams the
// whole result set; the browser downloads it. Returns false on failure (e.g. not premium).
export async function discoveryExportCsv(req: DiscoverySearchRequest): Promise<boolean> {
  try {
    const resp = await authFetch(`${API_BASE}/api/discovery/search/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!resp.ok) return false;
    const blob = await resp.blob();
    const cd = resp.headers.get("Content-Disposition") ?? "";
    const filename = /filename="?([^"]+)"?/.exec(cd)?.[1] ?? "discovery.csv";
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return true;
  } catch { return false; }
}

// --- Property Profile: area benchmarks + module-map layers ---

/** The middle half and median land area of a district's base parcels in a community area (WS5 PR3). */
export interface TypicalLot {
  n: number;
  p25_lot_sqft: number;
  median_lot_sqft: number;
  p75_lot_sqft: number;
}

/** Community-area benchmark aggregates for the Property Profile KPI band.
    All-null stats when the Discovery index is absent — callers render no
    benchmark line. */
export async function fetchAreaStats(ca: number, zoneClass?: string | null): Promise<{
  community_area: number;
  n_parcels: number;
  median_assessed: number | null;
  n_assessed: number;
  median_mv_per_land_sqft: number | null;
  n_mv_psf: number;
  /** Typical lot per exact district (WS5 PR3, Item 66); only districts with enough lots. */
  lot_size_by_zone_class?: Record<string, TypicalLot>;
  /** The benchmark's own entry (n, coverage, index build date): absent when there is no median. */
  provenance?: Record<string, Provenance>;
} | null> {
  try {
    const zc = zoneClass ? `&zone_class=${encodeURIComponent(zoneClass)}` : "";
    const resp = await authFetch(`${API_BASE}/api/area-stats?ca=${ca}${zc}`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

/** Geometry layers for the Property Profile module maps (zoning quilt +
    overlay/TIF/EZ boundaries). Every layer degrades to null. */
export async function fetchParcelMapLayers(
  lat: number,
  lon: number,
): Promise<ParcelMapLayers | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/parcel-map?lat=${lat.toFixed(5)}&lon=${lon.toFixed(5)}`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

/** The Profile's block capacity map (`/api/capacity-map`). `pin` locates the subject in the Discovery index;
 * lat/lon are the fallback for a withheld PIN. Null on a network or HTTP failure (the component says so). */
export async function fetchCapacityMap(
  pin: string | null | undefined,
  lat: number,
  lon: number,
): Promise<import("../components/scorecard/capacityMapModel").CapacityMapResponse | null> {
  const params = new URLSearchParams({ lat: lat.toFixed(6), lon: lon.toFixed(6) });
  if (pin) params.set("pin", pin);
  try {
    const resp = await authFetch(`${API_BASE}/api/capacity-map?${params}`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

export interface WhatIfFigures {
  zone_class: string;
  name: string;
  code_section: string;
  far: number | null;
  max_floor_area_sqft: number | null;
  max_height: string | null;
  min_lot_area_per_unit: number | null;
  units_by_lot_area: number | null;
  units_arithmetic: string | null;
}

export interface WhatIfResponse {
  suggestions: string[];
  districts: string[];
  lot_sqft?: number | null;
  current?: WhatIfFigures | null;
  target?: WhatIfFigures;
}

/** "What if this were rezoned?" (`/api/what-if`, WS5 PR2): table arithmetic for the parcel's district and a
 * chosen one. Without `district` it returns only the choice lists. Null on failure (the card says so). */
export async function fetchWhatIf(
  current: string,
  district?: string | null,
  lotSqft?: number | null,
  in606?: boolean | null,
): Promise<WhatIfResponse | null> {
  const params = new URLSearchParams({ current });
  if (district) params.set("district", district);
  if (lotSqft) params.set("lot_sqft", String(Math.round(lotSqft)));
  if (in606 != null) params.set("in_606", String(in606));
  try {
    const resp = await authFetch(`${API_BASE}/api/what-if?${params}`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

// --- Transit Stations ---

let _transitStationsCache: import("./types").TransitStation[] | null = null;

export async function fetchTransitStations(): Promise<import("./types").TransitStation[]> {
  if (_transitStationsCache && _transitStationsCache.length > 0) return _transitStationsCache;
  try {
    const resp = await authFetch(`${API_BASE}/api/transit-stations`);
    if (!resp.ok) return [];
    _transitStationsCache = await resp.json();
    return _transitStationsCache!;
  } catch { return []; }
}

// ---------------------------------------------------------------------------
// Saved (Phase 9, decision Item 119): the account's saved lots and Discovery searches
// ---------------------------------------------------------------------------

export interface SavedLotWire {
  id: string;
  key: string;
  pin: string | null;
  address: string;
  lat: number;
  lon: number;
  zone: string | null;
  area: string | null;
  outline: Array<[number, number]> | null;
  note: string;
  saved_at: number;
  watching_since: string | null;
  /** The address is a neighbor's stand-in: shown as "Near …". */
  approximate?: boolean;
}

export interface SavedLotInput {
  pin: string | null;
  address: string;
  lat: number;
  lon: number;
  zone?: string | null;
  area?: string | null;
  outline?: Array<[number, number]> | null;
  saved_at?: number;
  approximate?: boolean;
}

export type SavedChange =
  | { kind: "sale"; date: string; price: number | null }
  | { kind: "permit"; date: string; permit: string | null; permit_type: string | null; description: string | null; cost: number | null }
  | { kind: "violation"; date: string; code: string | null; description: string | null; status: string | null }
  | { kind: "rezoning_filed"; date: string; record: string; title: string; url: string }
  | { kind: "district"; date: string | null; old: string; new: string; record?: string | null; url?: string | null }
  | { kind: "overlay"; date: string | null; change: "added" | "removed"; layer: string; name: string | null }
  | { kind: "standards"; date: string | null; field: string; old: unknown; new: unknown; zone_class?: string }
  | { kind: "map_amendment" | "designation"; date: string | null; record: string | null; url: string | null; name?: string | null };

export interface SavedLotChanges {
  since: string;
  watching_since: string | null;
  status: "changes" | "none" | "partial";
  changes: SavedChange[];
  unchecked: string[];
}

export interface SavedSearchWire {
  id: string;
  name: string;
  draft: Record<string, unknown>;
  cqs: Record<string, unknown>;
  match_count: number;
  saved_at: number;
  seen_at: number;
}

export interface SavedSearchNew {
  total: number;
  new: number;
  gone: number;
  exact: boolean;
  same_data: boolean;
  since: string;
}

/** A Saved request that failed: the status (409 = the saved limit) for the page to word. */
export class SavedError extends Error {
  status: number;
  constructor(status: number) {
    super(`saved request failed: ${status}`);
    this.status = status;
  }
}

async function savedJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await authFetch(`${API_BASE}/api/saved${path}`, {
    ...init,
    headers: init.body ? { "Content-Type": "application/json" } : undefined,
  });
  if (!resp.ok) throw new SavedError(resp.status);
  return (resp.status === 204 ? undefined : await resp.json()) as T;
}

export const savedApi = {
  lots: () => savedJson<{ lots: SavedLotWire[]; max: number }>("/lots"),
  save: (lot: SavedLotInput) => savedJson<SavedLotWire>("/lots", { method: "POST", body: JSON.stringify(lot) }),
  merge: (lots: SavedLotInput[]) =>
    savedJson<{ added: number; skipped: number; lots: SavedLotWire[]; max: number }>("/lots/merge", { method: "POST", body: JSON.stringify({ lots }) }),
  note: (id: string, note: string) =>
    savedJson<SavedLotWire>(`/lots/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ note }) }),
  unsave: (id: string) => savedJson<void>(`/lots/${encodeURIComponent(id)}`, { method: "DELETE" }),
  changes: (id: string) => savedJson<SavedLotChanges>(`/lots/${encodeURIComponent(id)}/changes`),
  searches: () => savedJson<{ searches: SavedSearchWire[]; max: number }>("/searches"),
  saveSearch: (name: string, draft: unknown, request: unknown) =>
    savedJson<SavedSearchWire>("/searches", { method: "POST", body: JSON.stringify({ name, draft, request }) }),
  searchNew: (id: string) => savedJson<SavedSearchNew>(`/searches/${encodeURIComponent(id)}/new`),
  searchSeen: (id: string) => savedJson<SavedSearchWire>(`/searches/${encodeURIComponent(id)}/seen`, { method: "POST" }),
  renameSearch: (id: string, name: string) =>
    savedJson<SavedSearchWire>(`/searches/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ name }) }),
  deleteSearch: (id: string) => savedJson<void>(`/searches/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
