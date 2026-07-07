import i18n from "./i18n";
import { parseSSE } from "./sse";
import { flush, getVisitorId, track } from "./tracking";
import type {
  PinsResponse as DiscoveryPinsResponse,
  Registry as DiscoveryRegistry,
  SearchRequest as DiscoverySearchRequest,
  SearchResponse as DiscoverySearchResponse,
} from "../discovery/types";
import type {
  AddressSuggestion,
  AdminOverview,
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
  TimeseriesBucket,
  UploadMeta,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8001";

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return match?.[1] ?? "";
}

let _refreshPromise: Promise<boolean> | null = null;

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

async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const method = (options.method ?? "GET").toUpperCase();
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

  if (resp.status === 401) {
    const refreshed = await _tryRefresh();
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
}

export async function getAuthStatus(): Promise<AuthStatus> {
  const resp = await authFetch(`${API_BASE}/api/auth/me`);
  if (!resp.ok) return { authenticated: false, auth_required: true, user: null };
  return await resp.json();
}

export async function refreshAuthToken(): Promise<AuthStatus | null> {
  const resp = await authFetch(`${API_BASE}/api/auth/refresh`, { method: "POST" });
  if (!resp.ok) return null;
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
const sectionCache = new Map<string, Promise<CodeChunk | null>>();

export function fetchSection(sectionId: string): Promise<CodeChunk | null> {
  const key = sectionId.trim();
  const hit = sectionCache.get(key);
  if (hit) return hit;
  const p = (async () => {
    try {
      const resp = await authFetch(`${API_BASE}/section/${encodeURIComponent(key)}`);
      if (!resp.ok) return null;
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

export async function deleteUpload(uploadId: string): Promise<void> {
  await authFetch(`${API_BASE}/api/uploads/${encodeURIComponent(uploadId)}`, {
    method: "DELETE",
  });
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
  uses: string;
  notes: string;
  is_fallback: boolean;
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
  // True when the address-scoped violation lookup actually ran (parsed + queried).
  // Lets the UI show "no violations on record" for a confirmed-zero vs. omitting
  // for an unconfirmed lookup — silence must not mean two different things.
  violations_checked?: boolean;
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

export async function fetchReport(parcel: SelectedParcel): Promise<Blob | null> {
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

export async function discoverySearch(
  req: DiscoverySearchRequest,
): Promise<DiscoverySearchResponse | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/discovery/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

// Full ordered coord set for the map (PR6) — decoupled from the paginated list.
export async function discoverySearchPins(
  req: DiscoverySearchRequest,
): Promise<DiscoveryPinsResponse | null> {
  try {
    const resp = await authFetch(`${API_BASE}/api/discovery/search/pins`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
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
