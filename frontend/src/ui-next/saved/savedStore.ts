// Saved lots, one interface for the whole new UI (Phase 9, decision Item 119). Signed in, the lots live in the
// account (`/api/saved`); signed out, in this browser (`lotMemory`). The first time the account loads in a browser,
// the browser's saved lots move to it once (the server adds a lot only if its key isn't there yet, so a second tab
// or a repeat is harmless) and leave the browser; a lot with no point to place it stays in the browser.
// The home, the Profile, Discovery and the Saved page all read this one store, so a bookmark anywhere shows
// everywhere at once.
import { useCallback, useEffect, useSyncExternalStore } from "react";
import { SavedError, savedApi, type SavedLotInput, type SavedLotWire } from "../../lib/api";
import { useAuthContext } from "../../contexts/AuthContext";
import { readSaved, toggleSaved as toggleBrowser, useLotMemory, writeSaved, type RememberedLot } from "../home/lotMemory";

/** A saved lot as every page shows it. `id` is set for an account lot, null for a browser one. */
export interface SavedLot extends RememberedLot {
  id: string | null;
  note: string;
  watchingSince: string | null;
}

/** What a bookmark needs to save a lot. */
export type SaveInput = Omit<RememberedLot, "at">;

interface AccountState {
  status: "idle" | "loading" | "ready" | "error";
  lots: SavedLotWire[];
  /** The browser lots that just moved to the account, and the ones that couldn't (no point, or over the limit). */
  moved: { added: number; kept: number } | null;
  /** A save the account refused because it holds the most lots it can. */
  full: boolean;
  max: number;
}

const INITIAL: AccountState = { status: "idle", lots: [], moved: null, full: false, max: 200 };
let state: AccountState = INITIAL;
const listeners = new Set<() => void>();

function set(next: Partial<AccountState>) {
  state = { ...state, ...next };
  listeners.forEach((l) => l());
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};
const snapshot = () => state;

/** Where a browser lot sits: its own point, else the middle of its outline; null when neither is known. */
export function pointOf(lot: Pick<RememberedLot, "lat" | "lon" | "outline">): { lat: number; lon: number } | null {
  if (lot.lat != null && lot.lon != null) return { lat: lot.lat, lon: lot.lon };
  if (!lot.outline || lot.outline.length < 3) return null;
  const lon = lot.outline.reduce((a, p) => a + p[0], 0) / lot.outline.length;
  const lat = lot.outline.reduce((a, p) => a + p[1], 0) / lot.outline.length;
  return { lat, lon };
}

/** The body the server takes for a lot, or null when it has no point. */
export function toInput(lot: SaveInput & { at?: number }): SavedLotInput | null {
  const p = pointOf(lot);
  if (!p) return null;
  return {
    pin: lot.pin ? lot.pin.replace(/-/g, "") : null,
    address: lot.address,
    lat: p.lat,
    lon: p.lon,
    zone: lot.zone,
    area: lot.area,
    outline: lot.outline && lot.outline.length >= 3 ? lot.outline.slice(0, 40) : null,
    ...(lot.at ? { saved_at: lot.at } : {}),
  };
}

export function fromWire(w: SavedLotWire): SavedLot {
  return {
    id: w.id, key: w.key, address: w.address, pin: w.pin, zone: w.zone, area: w.area, outline: w.outline,
    at: w.saved_at, lat: w.lat, lon: w.lon, note: w.note, watchingSince: w.watching_since,
  };
}

function fromBrowser(l: RememberedLot): SavedLot {
  return { ...l, id: null, note: "", watchingSince: null };
}

/** Load the account's lots once per page load, moving the browser's saves in first. */
export async function loadAccount(force = false): Promise<void> {
  if (!force && (state.status === "loading" || state.status === "ready")) return;
  set({ status: "loading" });
  try {
    const local = readSaved();
    const movable = local.map((l) => ({ l, body: toInput(l) }));
    const bodies = movable.filter((m) => m.body).map((m) => m.body!) as SavedLotInput[];
    if (bodies.length) {
      const r = await savedApi.merge(bodies);
      const inAccount = new Set(r.lots.map((l) => l.key));
      // A lot leaves the browser once the account holds it; the rest stay (no point, or the account is full).
      const kept = local.filter((l) => !inAccount.has(l.key));
      writeSaved(kept);
      set({ status: "ready", lots: r.lots, max: r.max, moved: { added: r.added, kept: kept.length } });
    } else {
      const r = await savedApi.lots();
      set({ status: "ready", lots: r.lots, max: r.max });
    }
  } catch {
    set({ status: "error" });
  }
}

/** Signed out: forget the account's lots (they stay on the server). */
export function resetAccount(): void {
  if (state !== INITIAL) set(INITIAL);
}

async function toggleAccount(lot: SaveInput): Promise<boolean> {
  const have = state.lots.find((l) => l.key === lot.key);
  if (have) {
    set({ lots: state.lots.filter((l) => l.key !== lot.key), full: false });
    try {
      await savedApi.unsave(have.id);
    } catch (e) {
      if (!(e instanceof SavedError && e.status === 404)) set({ lots: [have, ...state.lots] });
    }
    return false;
  }
  const body = toInput(lot);
  if (!body) return false;
  try {
    const saved = await savedApi.save(body);
    set({ lots: [saved, ...state.lots.filter((l) => l.key !== saved.key)], full: false });
    return true;
  } catch (e) {
    if (e instanceof SavedError && e.status === 409) set({ full: true });
    return false;
  }
}

export async function setNote(id: string, note: string): Promise<boolean> {
  try {
    const saved = await savedApi.note(id, note);
    set({ lots: state.lots.map((l) => (l.id === id ? saved : l)) });
    return true;
  } catch {
    return false;
  }
}

/** For tests: back to a fresh page load. */
export function _resetForTests(): void {
  state = INITIAL;
  listeners.clear();
}

/** Saved lots for this visitor, from the account or this browser, plus the browser's recent lots. */
export function useSaved() {
  const { isAuthenticated, authRequired, loading } = useAuthContext();
  const account = !loading && (isAuthenticated || !authRequired);
  const memory = useLotMemory();
  const acc = useSyncExternalStore(subscribe, snapshot, snapshot);

  useEffect(() => {
    if (loading) return;
    if (account) void loadAccount();
    else resetAccount();
  }, [account, loading]);

  const lots: SavedLot[] = account ? acc.lots.map(fromWire) : memory.saved.map(fromBrowser);
  const keys = new Set(lots.map((l) => l.key));
  const isSaved = useCallback((key: string) => keys.has(key), [lots]); // eslint-disable-line react-hooks/exhaustive-deps
  const toggle = useCallback(
    (lot: SaveInput) => (account ? toggleAccount(lot) : Promise.resolve(toggleBrowser(lot))),
    [account],
  );

  return {
    /** True when the lots are the account's (signed in, or sign-in turned off in development). */
    account,
    status: account ? acc.status : ("ready" as const),
    lots,
    isSaved,
    toggle,
    setNote,
    moved: account ? acc.moved : null,
    full: account && acc.full,
    max: acc.max,
    recent: memory.recent,
    clearRecent: memory.clearRecent,
  };
}
