// Opening the full chat never replaces the page the user is on (Jack, 2026-11-06): it opens in a new tab.
// Called from a click, so browsers allow it. When a browser still blocks the tab, the caller is told
// (false) and keeps the page; it never falls back to navigating in place.
export function openInNewTab(path: string): boolean {
  const win = window.open(path, "_blank");
  if (!win) return false;
  try {
    win.opener = null; // the new tab gets no handle on this one (what rel="noopener" does for a link)
  } catch {
    // a cross-origin or already-closed window: nothing to cut
  }
  return true;
}

// The quick-chat dock hands its transcript to the full chat in the NEW tab. sessionStorage is per tab (and is not
// copied to a tab opened without an opener), so the handoff goes through localStorage under a one-time id carried in
// the URL (?handoff=<id>), read once and removed. Entries older than an hour are dropped on every write.
const HANDOFF_PREFIX = "ul_dock_handoff:";
const HANDOFF_TTL_MS = 60 * 60 * 1000;

export interface HandoffMessage {
  role: "user" | "assistant";
  content: string;
}

export function writeHandoff(messages: HandoffMessage[], now: number = Date.now()): string | null {
  try {
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const key = localStorage.key(i);
      if (!key?.startsWith(HANDOFF_PREFIX)) continue;
      const at = Number(JSON.parse(localStorage.getItem(key) ?? "{}").at);
      if (!(now - at < HANDOFF_TTL_MS)) localStorage.removeItem(key);
    }
    const id = Math.random().toString(36).slice(2, 10) + now.toString(36);
    localStorage.setItem(HANDOFF_PREFIX + id, JSON.stringify({ at: now, messages }));
    return id;
  } catch {
    return null; // no storage: the full chat opens without the transcript rather than not at all
  }
}

export function takeHandoff(id: string): HandoffMessage[] | null {
  if (!/^[a-z0-9]{1,40}$/.test(id)) return null;
  try {
    const raw = localStorage.getItem(HANDOFF_PREFIX + id);
    if (!raw) return null;
    localStorage.removeItem(HANDOFF_PREFIX + id);
    const messages = JSON.parse(raw).messages;
    return Array.isArray(messages) ? messages : null;
  } catch {
    return null;
  }
}
