// "Pick up where you left off": the last search a viewer ran, kept in THIS browser only
// (localStorage). A per-viewer convenience, never the source of anything shown as a result:
// it stores the inputs that were sent plus the sentence the server's cqs produced, and
// resuming runs the search again (so what is then shown is evaluated fresh, INV-4). Every
// read and write is guarded: private windows and blocked storage must not break the page.

import type { SearchInputs } from "./searchClient";

const KEY = "ul_discovery_last";
const VERSION = 1;
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;

export interface SavedSearch {
  inputs: Pick<SearchInputs, "panelState" | "text" | "sort" | "topicId">;
  /** The summary sentence of the evaluated cqs, in the language it was saved in. */
  sentence: string;
  savedAt: number;
}

export function saveLastSearch(search: Omit<SavedSearch, "savedAt">, now = Date.now()): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ v: VERSION, ...search, savedAt: now }));
  } catch {
    // storage unavailable: the convenience just does not exist
  }
}

export function loadLastSearch(now = Date.now()): SavedSearch | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<SavedSearch> & { v?: number };
    if (parsed.v !== VERSION || typeof parsed.sentence !== "string" || typeof parsed.savedAt !== "number") return null;
    if (!parsed.inputs || typeof parsed.inputs.panelState !== "object" || parsed.inputs.panelState === null) return null;
    if (now - parsed.savedAt > MAX_AGE_MS) return null;
    return { inputs: parsed.inputs, sentence: parsed.sentence, savedAt: parsed.savedAt };
  } catch {
    return null;
  }
}

export function clearLastSearch(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // nothing to clear
  }
}
