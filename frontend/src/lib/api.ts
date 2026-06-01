import { parseSSE } from "./sse";
import type {
  AddressSuggestion,
  AdminOverview,
  BenchmarkResults,
  ChatChunk,
  CodeChunk,
  Conversation,
  ConversationDetail,
  ConversationStats,
  JudgeResults,
  LatencyPercentiles,
  MapData,
  Message,
  RequestLogEntry,
  TimeseriesBucket,
  UploadMeta,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8001";

// Sections are immutable, so cache by ID — lets hover-prefetch and the
// subsequent click share one request. Failed lookups are evicted so they retry.
const sectionCache = new Map<string, Promise<CodeChunk | null>>();

export function fetchSection(sectionId: string): Promise<CodeChunk | null> {
  const key = sectionId.trim();
  const hit = sectionCache.get(key);
  if (hit) return hit;
  const p = (async () => {
    try {
      const resp = await fetch(`${API_BASE}/section/${encodeURIComponent(key)}`);
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
    const resp = await fetch(`${API_BASE}/autocomplete?q=${encodeURIComponent(query)}`);
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
    const resp = await fetch(`${API_BASE}/api/map-data`, {
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

export async function getCommunityAreaByPoint(
  lat: number,
  lon: number,
): Promise<{ community_area: number; name: string } | null> {
  try {
    const resp = await fetch(
      `${API_BASE}/api/community-area?lat=${lat}&lon=${lon}`,
    );
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

export async function* chatStream(
  message: string,
  history: Message[],
  signal?: AbortSignal,
  conversationId?: string | null,
  uploadIds?: string[],
): AsyncGenerator<ChatChunk, void, unknown> {
  const body: Record<string, unknown> = { message, history };
  if (conversationId) body.conversation_id = conversationId;
  if (uploadIds?.length) body.upload_ids = uploadIds;

  const resp = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`Chat request failed: ${resp.status} ${resp.statusText}`);
  }

  yield* parseSSE<ChatChunk>(resp.body.getReader());
}

// ---------------------------------------------------------------------------
// Conversation CRUD
// ---------------------------------------------------------------------------

export async function listConversations(): Promise<Conversation[]> {
  const resp = await fetch(`${API_BASE}/api/conversations`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.map((c: Record<string, unknown>) => ({
    id: c.id,
    title: c.title,
    message_count: c.message_count,
    createdAt: c.created_at,
    updatedAt: c.updated_at,
  }));
}

export async function getConversation(id: string): Promise<ConversationDetail | null> {
  const resp = await fetch(`${API_BASE}/api/conversations/${encodeURIComponent(id)}`);
  if (!resp.ok) return null;
  return await resp.json();
}

export async function createConversation(id: string, title: string): Promise<void> {
  await fetch(`${API_BASE}/api/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, title }),
  });
}

export async function deleteConversationAPI(id: string): Promise<void> {
  await fetch(`${API_BASE}/api/conversations/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function saveMessages(
  conversationId: string,
  messages: Record<string, unknown>[],
): Promise<void> {
  await fetch(
    `${API_BASE}/api/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    },
  );
}

export async function updateMessageMapData(
  conversationId: string,
  position: number,
  mapData: MapData,
): Promise<void> {
  await fetch(
    `${API_BASE}/api/conversations/${encodeURIComponent(conversationId)}/messages/${position}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ map_data: mapData, map_fetched_at: Date.now() }),
    },
  );
}

export async function importConversations(
  conversations: Record<string, unknown>[],
): Promise<number> {
  const resp = await fetch(`${API_BASE}/api/conversations/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversations }),
  });
  if (!resp.ok) return 0;
  const data = await resp.json();
  return data.imported ?? 0;
}

export async function clearAllConversations(): Promise<void> {
  await fetch(`${API_BASE}/api/conversations`, { method: "DELETE" });
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
  const resp = await fetch(
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
  await fetch(`${API_BASE}/api/uploads/${encodeURIComponent(uploadId)}`, {
    method: "DELETE",
  });
}

// ---------------------------------------------------------------------------
// Admin API
// ---------------------------------------------------------------------------

export async function fetchAdminOverview(period: string): Promise<AdminOverview | null> {
  try {
    const resp = await fetch(`${API_BASE}/api/admin/overview?period=${period}`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

export async function fetchAdminTimeseries(
  period: string, bucket = "day",
): Promise<TimeseriesBucket[]> {
  try {
    const resp = await fetch(
      `${API_BASE}/api/admin/timeseries?period=${period}&bucket=${bucket}`,
    );
    if (!resp.ok) return [];
    return await resp.json();
  } catch { return []; }
}

export async function fetchAdminLatency(period: string): Promise<LatencyPercentiles[]> {
  try {
    const resp = await fetch(`${API_BASE}/api/admin/latency?period=${period}`);
    if (!resp.ok) return [];
    return await resp.json();
  } catch { return []; }
}

export async function fetchConversationStats(): Promise<ConversationStats | null> {
  try {
    const resp = await fetch(`${API_BASE}/api/admin/conversations`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

export async function fetchRequestLogs(
  limit = 50, offset = 0,
): Promise<RequestLogEntry[]> {
  try {
    const resp = await fetch(
      `${API_BASE}/api/admin/requests?limit=${limit}&offset=${offset}`,
    );
    if (!resp.ok) return [];
    return await resp.json();
  } catch { return []; }
}

export async function fetchBenchmarkResults(): Promise<BenchmarkResults | null> {
  try {
    const resp = await fetch(`${API_BASE}/api/admin/benchmark`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

export async function fetchJudgeResults(): Promise<JudgeResults | null> {
  try {
    const resp = await fetch(`${API_BASE}/api/admin/judge`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

let _transitStationsCache: import("./types").TransitStation[] | null = null;

export async function fetchTransitStations(): Promise<import("./types").TransitStation[]> {
  if (_transitStationsCache) return _transitStationsCache;
  try {
    const resp = await fetch(`${API_BASE}/api/transit-stations`);
    if (!resp.ok) return [];
    _transitStationsCache = await resp.json();
    return _transitStationsCache!;
  } catch { return []; }
}
