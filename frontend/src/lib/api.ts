import { parseSSE } from "./sse";
import type { AddressSuggestion, ChatChunk, CodeChunk, Message } from "./types";

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

export async function* chatStream(
  message: string,
  history: Message[],
  signal?: AbortSignal,
): AsyncGenerator<ChatChunk, void, unknown> {
  const resp = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
    signal,
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`Chat request failed: ${resp.status} ${resp.statusText}`);
  }

  yield* parseSSE<ChatChunk>(resp.body.getReader());
}
