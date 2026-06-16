// Registry client (08): fetch once per session, cache in-module, and persist to
// localStorage ONLY as an offline fallback. The registry is the one source of predicate
// kinds + topic definitions, shared with the backend (no FE/BE drift).
//
// ⚠️ We deliberately do NOT serve localStorage as a fetch-skip. The persisted payload also
// carries injected index meta (coverage / populatedFields / recipeCounts), which changes as
// the prod index grows — but `registry.version` is the STATIC schema version and does not
// move when only the index changes. A localStorage-first read therefore pins returning
// visitors to whatever coverage was live when they first loaded the page (e.g. a dormant
// `coverage: "none"` payload → the "being prepared" banner forever). So every fresh session
// revalidates against the server; localStorage is used only when that fetch fails.

import { fetchDiscoveryRegistry } from "../lib/api";
import type { Registry } from "./types";

const LS_KEY = "urbanlayer-discovery-registry";

let _cache: Registry | null = null;
let _pending: Promise<Registry | null> | null = null;

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
 * Return the registry. Within a session, the first successful fetch is reused (in-memory),
 * so PageHeader + DiscoveryPage mounting together share one request. A fresh session always
 * revalidates against the server (localStorage is NOT a fetch-skip — see file header). Pass
 * `force` to refetch unconditionally. Falls back to any persisted/in-memory copy only when
 * the network fetch fails.
 */
export async function loadRegistry(force = false): Promise<Registry | null> {
  if (!force) {
    if (_cache) return _cache;
    if (_pending) return _pending; // coalesce concurrent first-load callers
  }
  _pending = fetchDiscoveryRegistry()
    .then((fresh) => {
      if (fresh) {
        _cache = fresh;
        _writeLocalStorage(fresh);
        return fresh;
      }
      return _cache ?? _readLocalStorage(); // offline fallback
    })
    .finally(() => {
      _pending = null;
    });
  return _pending;
}

/** Test-only: drop the in-memory cache. */
export function _resetCache(): void {
  _cache = null;
  _pending = null;
}
