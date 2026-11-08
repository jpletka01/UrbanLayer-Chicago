// The new Profile's loading, in parts (decision Item 89). For one lookup:
// 1. `/api/scorecard/first` (Item 82, about 1–3 s) and `/api/profile/overview` start together; the server resolves
//    the address once for both.
// 2. The Overview answers with the whole Profile so far and a signed `lookup`; the page draws it.
// 3. Once the Overview has painted, the late parts it names start (the server caps how many run at once). Each
//    answers with the whole Profile so far; the page keeps the highest `version`, so the order they land in
//    doesn't matter and nothing is merged by hand.
// 4. A part past its deadline names the sources it couldn't check in time; Retry asks that part again. An expired
//    lookup asks the Overview again. A new lookup or leaving the page aborts everything still running.
import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchProfileOverview,
  fetchProfilePart,
  fetchScorecardFirst,
  type ProfileLatePart,
  type ProfilePartResponse,
  type ScorecardFirst,
  type ScorecardResponse,
} from "../../lib/api";
import type { ParcelQuery } from "../../lib/types";

export type PartStatus = "waiting" | "done" | "failed";

export interface ProfileParts {
  /** idle: no lookup. loading: before the Overview. overview: the Overview is in, late parts on their way.
      complete: every part answered (some sources may have run out of time). notFound / failed: no Profile. */
  status: "idle" | "loading" | "overview" | "complete" | "notFound" | "failed";
  first: ScorecardFirst | null;
  data: ScorecardResponse | null;
  parts: Partial<Record<ProfileLatePart, PartStatus>>;
  /** Per part, the sources past their deadline in its latest answer. */
  timedOut: Partial<Record<ProfileLatePart, string[]>>;
  /** The Overview's record once it is in: the late parts start when this changes. */
  ready: string | null;
}

/** Every part has answered (done or failed): the Profile is as complete as it will get without a Retry. */
const settled = (parts: ProfileParts["parts"]) => Object.values(parts).every((st) => st !== "waiting");

const EMPTY: ProfileParts = { status: "idle", first: null, data: null, parts: {}, timedOut: {}, ready: null };

/** Wait until the browser has painted what was just rendered (the Overview is on screen and interactive). */
function afterPaint(fn: () => void): () => void {
  let timer = 0;
  if (typeof requestAnimationFrame !== "function") {
    timer = window.setTimeout(fn, 0);
    return () => window.clearTimeout(timer);
  }
  const raf = requestAnimationFrame(() => { timer = window.setTimeout(fn, 0); });
  return () => {
    cancelAnimationFrame(raf);
    window.clearTimeout(timer);
  };
}

export function useProfileParts(
  queryKey: string | null,
  { onOverview, onComplete }: {
    /** The Overview answered (canonicalize the URL, track the view). */
    onOverview?: (overview: ProfilePartResponse) => void;
    /** Every part answered: the assembled Profile, the full response's shape. */
    onComplete?: (data: ScorecardResponse) => void;
  } = {},
): ProfileParts & { retryPart: (name: ProfileLatePart) => void; retryAll: () => void } {
  const [state, setState] = useState<ProfileParts>(EMPTY);
  const ctrl = useRef<AbortController | null>(null);
  const lookup = useRef<{ token: string; record: string; version: number } | null>(null);
  const latest = useRef<ProfileParts>(EMPTY);
  const onOverviewRef = useRef(onOverview);
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onOverviewRef.current = onOverview;
    onCompleteRef.current = onComplete;
  });
  const expiredOnce = useRef(false);

  const update = useCallback((fn: (s: ProfileParts) => ProfileParts) => {
    setState((s) => {
      const next = fn(s);
      latest.current = next;
      return next;
    });
  }, []);

  /** Keep a response's Profile when it is newer than the one shown (same record, higher version). */
  const accept = useCallback((r: ProfilePartResponse): boolean => {
    const cur = lookup.current;
    if (cur && cur.record === r.record && r.version <= cur.version) return false;
    lookup.current = { token: r.lookup, record: r.record, version: r.version };
    return true;
  }, []);

  const startOverview = useCallback((key: string, keepFirst: boolean) => {
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    lookup.current = null;
    update((s) => ({ ...EMPTY, status: "loading", first: keepFirst ? s.first : null }));
    const query = JSON.parse(key) as ParcelQuery;
    if (!keepFirst) {
      fetchScorecardFirst(query, c.signal).then((f) => {
        if (c.signal.aborted || !f) return;
        update((s) => (s.status === "loading" ? { ...s, first: f } : s));
      });
    }
    fetchProfileOverview(query, c.signal).then((r) => {
      if (c.signal.aborted) return;
      if (r === "notFound" || r === "failed") {
        update((s) => ({ ...s, status: s.first && r === "failed" ? "failed" : r }));
        return;
      }
      accept(r);
      const parts = Object.fromEntries(r.parts_pending.map((p) => [p, "waiting" as PartStatus]));
      update((s) => ({
        ...s, status: r.parts_pending.length ? "overview" : "complete", data: r.profile, parts, timedOut: {}, ready: r.record,
      }));
      onOverviewRef.current?.(r);
    });
  }, [accept, update]);

  const runPart = useCallback((name: ProfileLatePart) => {
    const c = ctrl.current;
    const cur = lookup.current;
    if (!c || !cur) return;
    const have = (Object.entries(latest.current.parts) as Array<[ProfileLatePart, PartStatus]>)
      .filter(([p, st]) => st === "done" && p !== name).map(([p]) => p);
    const fail = () => update((s) => {
      const parts = { ...s.parts, [name]: "failed" as PartStatus };
      return { ...s, parts, status: settled(parts) ? "complete" : s.status };
    });
    fetchProfilePart(name, cur.token, have, c.signal).then((r) => {
      if (c.signal.aborted) return;
      if (r === "expired") {
        // The server stopped trusting this lookup (expired, or signed with an older key): one fresh Overview.
        if (!expiredOnce.current && queryKey) { expiredOnce.current = true; startOverview(queryKey, true); }
        else fail();
        return;
      }
      if (r === "failed") { fail(); return; }
      const newer = accept(r);
      update((s) => {
        const parts = { ...s.parts, [name]: "done" as PartStatus };
        return {
          ...s,
          data: newer ? r.profile : s.data,
          parts,
          timedOut: { ...s.timedOut, [name]: r.timed_out },
          status: settled(parts) ? "complete" : s.status,
        };
      });
    });
  }, [accept, queryKey, startOverview, update]);

  // A new lookup: start over (and abort the previous one's requests).
  useEffect(() => {
    expiredOnce.current = false;
    if (!queryKey) {
      ctrl.current?.abort();
      update(() => EMPTY);
      return;
    }
    startOverview(queryKey, false);
    return () => ctrl.current?.abort();
  }, [queryKey, startOverview, update]);

  // The Overview is in: once it has painted, ask the late parts.
  const recordId = state.ready;
  useEffect(() => {
    if (!recordId) return;
    const waiting = (Object.entries(latest.current.parts) as Array<[ProfileLatePart, PartStatus]>)
      .filter(([, st]) => st === "waiting").map(([p]) => p);
    return afterPaint(() => waiting.forEach(runPart));
    // Only when a new Overview arrives, not on every part.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recordId]);

  // Everything answered: hand the assembled Profile over once.
  const completed = useRef<string | null>(null);
  useEffect(() => {
    if (state.status !== "complete" || !state.data || !lookup.current) return;
    const id = `${lookup.current.record}:${lookup.current.version}`;
    if (completed.current === id) return;
    completed.current = id;
    onCompleteRef.current?.(state.data);
  }, [state.status, state.data]);

  const retryPart = useCallback((name: ProfileLatePart) => {
    update((s) => ({ ...s, status: "overview", parts: { ...s.parts, [name]: "waiting" } }));
    runPart(name);
  }, [runPart, update]);

  const retryAll = useCallback(() => { if (queryKey) startOverview(queryKey, true); }, [queryKey, startOverview]);

  return { ...state, retryPart, retryAll };
}
