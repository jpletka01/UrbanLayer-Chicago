// Registry client (08): fetch once, cache in-module + localStorage, expose a staleness
// check so a registryVersion mismatch can trigger a refetch. The registry is the one
// source of predicate kinds + topic definitions, shared with the backend (no FE/BE drift).

import { fetchDiscoveryRegistry } from "../lib/api";
import type { Registry } from "./types";

const LS_KEY = "urbanlayer-discovery-registry";

let _cache: Registry | null = null;

function _readLocalStorage(): Registry | null {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? (JSON.parse(raw) as Registry) : null;
  } catch {
    return null;
  }
}

function _writeLocalStorage(reg: Registry): void {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(reg));
  } catch {
    /* quota / unavailable — cache stays in-memory */
  }
}

/** The currently cached registry, if any (no fetch). */
export function cachedRegistry(): Registry | null {
  if (!_cache) _cache = _readLocalStorage();
  return _cache;
}

/** True when there is no cache or the cached version differs from `version`. */
export function isStale(version: string): boolean {
  const cur = cachedRegistry();
  return cur === null || cur.version !== version;
}

/**
 * Return the registry, fetching once and caching. Pass `force` to refetch (e.g. after a
 * `registryVersion` staleness signal). Falls back to any cache on network failure.
 */
export async function loadRegistry(force = false): Promise<Registry | null> {
  if (!force) {
    const cur = cachedRegistry();
    if (cur) return cur;
  }
  const fresh = await fetchDiscoveryRegistry();
  if (fresh) {
    _cache = fresh;
    _writeLocalStorage(fresh);
    return fresh;
  }
  return cachedRegistry();
}

/** Test-only: drop the in-memory cache. */
export function _resetCache(): void {
  _cache = null;
}
