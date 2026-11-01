// Draft / applied / abort logic of the Discovery page (Phase 0 of the redesign).
//
//   draft    what the user is asking for: panel controls, text, sort. Edited freely; chips and
//            the "Update results" count are computed from it. Never requested on its own.
//   applied  the last response the server evaluated, and the inputs that produced it. The
//            summary sentence, the count and the rows describe THIS (INV-4), never the draft.
//
// A search is issued only by apply() (Search, Enter, "Update results") or a recipe pick, so a
// burst of edits costs one request. While one runs the previous results stay in place
// (the page dims them); a superseded request is aborted, and a response that is not from the
// latest issued request is ignored (Item 30). The list is canonical: pins are accepted only
// when data version, total and cardinality agree with it, otherwise the map is unavailable
// (the check stays even though one response now carries both).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { track } from "../lib/tracking";
import {
  diffDraft,
  inputsSignature,
  reconcileWithResponse,
  discardToApplied,
  removeFromDraft,
  restoreToDraft,
  type ChipItem,
  type DiscoveryDraft,
} from "./draftModel";
import { exportCsv, previewText, runPins, runSearch, type SearchInputs } from "./searchClient";
import { NEIGHBORHOOD_PREFIX } from "./communityAreas";
import { expandTopic } from "./topicCompiler";
import { compilePanel } from "./uiCompiler";
import type {
  FilterId,
  PinPoint,
  Predicate,
  Registry,
  ResultRow,
  SearchResponse,
  TopicDef,
} from "./types";

export type MapStatus = "idle" | "loading" | "ready" | "unavailable";

interface Applied {
  response: SearchResponse;
  /** The text that was sent with the search that produced `response`. */
  text: string;
}

const EMPTY_DRAFT: DiscoveryDraft = { panelState: {}, text: "", sort: null, topicId: null };

const now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());

// "Painted" = after the browser has had a frame with the committed results.
function afterPaint(fn: () => void) {
  if (typeof requestAnimationFrame === "function") requestAnimationFrame(() => fn());
  else fn();
}

function toInputs(draft: DiscoveryDraft, topicId: string | null = draft.topicId): SearchInputs {
  return { panelState: draft.panelState, text: draft.text, sort: draft.sort, topicId };
}

export interface DiscoverySearchOptions {
  /** Called when a response is committed (the user is now looking at it), with the inputs that produced it. */
  onCommit?: (inputs: SearchInputs, response: SearchResponse) => void;
}

export function useDiscoverySearch(registry: Registry | null, options: DiscoverySearchOptions = {}) {
  const onCommitRef = useRef(options.onCommit);
  useEffect(() => {
    onCommitRef.current = options.onCommit;
  });
  const [draft, setDraft] = useState<DiscoveryDraft>(EMPTY_DRAFT);
  const draftRef = useRef(draft);
  const updateDraft = useCallback((fn: (d: DiscoveryDraft) => DiscoveryDraft) => {
    const next = fn(draftRef.current);
    draftRef.current = next;
    setDraft(next);
  }, []);

  const [applied, setApplied] = useState<Applied | null>(null);
  const appliedRef = useRef<Applied | null>(null);
  const [rows, setRows] = useState<ResultRow[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [mapPoints, setMapPoints] = useState<PinPoint[]>([]);
  const [mapTruncated, setMapTruncated] = useState(false);
  const [mapTotal, setMapTotal] = useState(0);
  const [mapStatus, setMapStatus] = useState<MapStatus>("idle");
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  // First search failed, so there is nothing to keep on screen.
  const [unavailable, setUnavailable] = useState(false);
  // A refresh failed: the previous results are still shown.
  const [refreshFailed, setRefreshFailed] = useState(false);
  const [issuedSig, setIssuedSig] = useState<string | null>(null);
  // The text compiler understood none of a phrase and nothing else was set, so no search ran.
  const [textNotice, setTextNotice] = useState<{ text: string; words: string[] } | null>(null);
  const applySeqRef = useRef(0);

  const requestIdRef = useRef(0);
  const commitRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);
  const moreControllerRef = useRef<AbortController | null>(null);
  const issuedSigRef = useRef<string | null>(null);
  // What load-more and export re-issue: the inputs of the search the user is LOOKING at,
  // not of one still in flight.
  const committedInputsRef = useRef<SearchInputs | null>(null);
  const loadingMoreRef = useRef(false);

  // The sort control needs a value before the user touches it.
  useEffect(() => {
    if (registry && draftRef.current.sort === null) {
      updateDraft((d) => ({ ...d, sort: registry.defaultSort }));
    }
  }, [registry, updateDraft]);

  useEffect(
    () => () => {
      requestIdRef.current += 1;
      controllerRef.current?.abort();
      moreControllerRef.current?.abort();
    },
    [],
  );

  const issue = useCallback(
    async (inputs: SearchInputs) => {
      if (!registry) return;
      const sig = inputsSignature(inputs);
      // The same query is already on its way: nothing to supersede.
      if (issuedSigRef.current === sig) return;
      controllerRef.current?.abort();
      moreControllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      issuedSigRef.current = sig;
      setIssuedSig(sig);
      const requestId = ++requestIdRef.current;
      const startedAt = now();
      const hadPrevious = appliedRef.current !== null;

      setLoading(true);
      setLoadingMore(false);
      loadingMoreRef.current = false;
      setRefreshFailed(false);
      setUnavailable(false);
      // Previous rows, count, summary and dots stay put. Only a first search, which has
      // nothing to keep, shows an empty map state.
      if (!hadPrevious) {
        setMapStatus("loading");
        setMapPoints([]);
        setMapTruncated(false);
        setMapTotal(0);
      }

      try {
        // One request returns the list and the map's points from the same evaluation, so
        // they cannot disagree. A backend that predates `includePins` ignores it and sends
        // no points: then fall back to the separate pins request, so deploy order can never
        // break the map.
        const resp = await runSearch({ ...inputs, includePins: true }, registry, controller.signal);
        if (requestId !== requestIdRef.current) return;
        let pins = resp?.pins ?? null;
        if (resp && !pins) {
          pins = await runPins(inputs, registry, controller.signal).catch(() => null);
          if (requestId !== requestIdRef.current) return;
        }
        const report = () =>
          track("discovery_search", {
            topic_id: inputs.topicId ?? null,
            has_text: !!inputs.text,
            total: resp?.result.total ?? null,
            gated: resp?.result.gated ?? null,
            ms: Math.round(now() - startedAt),
          });

        if (!resp) {
          if (hadPrevious) {
            setRefreshFailed(true);
          } else {
            setUnavailable(true);
            setMapStatus("unavailable");
          }
          afterPaint(report);
          return;
        }

        const next: Applied = { response: resp, text: inputs.text ?? "" };
        appliedRef.current = next;
        committedInputsRef.current = inputs;
        commitRef.current += 1;
        setApplied(next);
        onCommitRef.current?.(inputs, resp);
        setRows(resp.result.rows);
        setNextOffset(resp.result.nextOffset);
        // No edits while it ran: the strip now shows exactly what the server evaluated.
        if (inputsSignature(draftRef.current) === sig) {
          updateDraft((d) => reconcileWithResponse(d, resp.cqs));
        }

        const pinsCardinalityMatches =
          pins && (pins.truncated ? pins.points.length <= pins.total : pins.points.length === pins.total);
        if (
          !pins ||
          pins.dataVersion !== resp.dataVersion ||
          pins.total !== resp.result.total ||
          !pinsCardinalityMatches
        ) {
          setMapPoints([]);
          setMapTruncated(false);
          setMapTotal(0);
          setMapStatus("unavailable");
        } else {
          setMapPoints(pins.points);
          setMapTruncated(pins.truncated);
          setMapTotal(resp.result.total);
          setMapStatus("ready");
        }
        afterPaint(report);
      } catch {
        if (requestId !== requestIdRef.current) return;
        if (hadPrevious) {
          setRefreshFailed(true);
        } else {
          setUnavailable(true);
          setMapStatus("unavailable");
        }
      } finally {
        if (requestId === requestIdRef.current) {
          setLoading(false);
          issuedSigRef.current = null;
          setIssuedSig(null);
        }
      }
    },
    [registry, updateDraft],
  );

  /** Search / Enter / Update results: send the draft as it is now.
   *
   * The text box is a rule-based compiler that silently drops what it does not recognize, so a
   * phrase it understands none of (and with no panel filters beside it) would search EVERY
   * parcel. Ask the compiler first (cheap, no index read); if it understood nothing, say so and
   * do not search. If it cannot be asked, search anyway: the gate must never be what breaks
   * search. A draft with panel filters, or no text, searches at once as before. */
  const apply = useCallback(() => {
    // The default sort is filled in by an effect after the registry arrives. A search issued before
    // that effect has run would go out with no sort, and the effect would then change the draft under
    // it, so the response would no longer match the draft and its filters would never be reconciled
    // (they showed as removed chips: the Discovery test flake of 2026-10-31). Fill it here first.
    if (registry && draftRef.current.sort === null) {
      updateDraft((d) => ({ ...d, sort: registry.defaultSort }));
    }
    const draftNow = draftRef.current;
    const text = draftNow.text.trim();
    const seq = ++applySeqRef.current;
    setTextNotice(null);
    if (!text || Object.keys(compilePanel(draftNow.panelState)).length > 0) {
      void issue(toInputs(draftNow));
      return;
    }
    void (async () => {
      const preview = await previewText(text).catch(() => null);
      if (seq !== applySeqRef.current) return; // a newer apply or edit superseded this one
      if (preview && preview.understood.length === 0) {
        setTextNotice({ text, words: preview.residual });
        return;
      }
      void issue(toInputs(draftNow));
    })();
  }, [issue, registry, updateDraft]);

  // Recipe click: replace the draft with the recipe's presets and run it (the click is the
  // explicit "search this"). The backend does not re-expand the topic; presets travel as
  // plain user filters and topicId is telemetry.
  const pickRecipe = useCallback(
    (topic: TopicDef) => {
      if (!registry) return;
      const next: DiscoveryDraft = {
        panelState: expandTopic(topic.id, registry),
        text: "",
        sort: topic.defaultSort ?? registry.defaultSort,
        topicId: topic.id,
      };
      applySeqRef.current += 1; // a recipe click supersedes a text check still in flight
      setTextNotice(null);
      draftRef.current = next;
      setDraft(next);
      void issue(toInputs(next));
    },
    [registry, issue],
  );

  // The other ways in from the Start panel. Each is an explicit "search this" like a recipe
  // click, so each replaces the draft and runs at once.
  const startWith = useCallback(
    (next: DiscoveryDraft) => {
      applySeqRef.current += 1;
      setTextNotice(null);
      draftRef.current = next;
      setDraft(next);
      void issue(toInputs(next));
    },
    [issue],
  );

  /** One community area, nothing else: the user then adds filters to it. */
  const pickNeighborhood = useCallback(
    (areaId: number) => {
      if (!registry) return;
      startWith({
        panelState: { neighborhood: { kind: "region", regions: [`${NEIGHBORHOOD_PREFIX}${areaId}`] } },
        text: "",
        sort: registry.defaultSort,
        topicId: null,
      });
    },
    [registry, startWith],
  );

  /** No filters: every parcel in the index. */
  const startAll = useCallback(() => {
    if (!registry) return;
    startWith({ panelState: {}, text: "", sort: registry.defaultSort, topicId: null });
  }, [registry, startWith]);

  /** Re-run the inputs of an earlier search (evaluated fresh; nothing stored is shown as a result). */
  const resume = useCallback(
    (saved: Pick<SearchInputs, "panelState" | "text" | "sort" | "topicId">) => {
      if (!registry) return;
      startWith({
        panelState: saved.panelState,
        text: saved.text ?? "",
        sort: saved.sort ?? registry.defaultSort,
        topicId: saved.topicId ?? null,
      });
    },
    [registry, startWith],
  );

  // --- draft edits: none of these request anything ---

  const editPanel = useCallback(
    (id: FilterId, predicate: Predicate | null) => {
      updateDraft((d) => {
        const panelState = { ...d.panelState };
        if (predicate === null) delete panelState[id];
        else panelState[id] = predicate;
        return { ...d, panelState, topicId: null };
      });
    },
    [updateDraft],
  );

  const setText = useCallback(
    (text: string) => {
      applySeqRef.current += 1; // an edit supersedes a text check still in flight
      setTextNotice(null);
      updateDraft((d) => ({ ...d, text, topicId: null }));
    },
    [updateDraft],
  );

  const setSort = useCallback(
    (sort: DiscoveryDraft["sort"]) => updateDraft((d) => ({ ...d, sort })),
    [updateDraft],
  );

  const removeFilter = useCallback(
    (id: FilterId) =>
      updateDraft((d) =>
        removeFromDraft(d, appliedRef.current?.response.cqs ?? null, appliedRef.current?.text ?? "", id),
      ),
    [updateDraft],
  );

  const restoreFilter = useCallback(
    (id: FilterId) =>
      updateDraft((d) => restoreToDraft(d, appliedRef.current?.response.cqs ?? null, id)),
    [updateDraft],
  );

  /** Back to the Start panel: drop what is on screen, abandon anything in flight, empty the draft.
   *  The last evaluated search stays saved in this browser (Resume offers it again). */
  const startOver = useCallback(() => {
    requestIdRef.current += 1; // a response still on its way is now stale
    controllerRef.current?.abort();
    moreControllerRef.current?.abort();
    applySeqRef.current += 1;
    issuedSigRef.current = null;
    setIssuedSig(null);
    appliedRef.current = null;
    committedInputsRef.current = null;
    commitRef.current += 1;
    loadingMoreRef.current = false;
    setApplied(null);
    setRows([]);
    setNextOffset(null);
    setMapPoints([]);
    setMapTruncated(false);
    setMapTotal(0);
    setMapStatus("idle");
    setLoading(false);
    setLoadingMore(false);
    setRefreshFailed(false);
    setUnavailable(false);
    setTextNotice(null);
    const next: DiscoveryDraft = { ...EMPTY_DRAFT, sort: registry?.defaultSort ?? null };
    draftRef.current = next;
    setDraft(next);
  }, [registry]);

  /** Put the draft back to the evaluated query (a draft-only change: nothing is requested). */
  const discardChanges = useCallback(() => {
    const current = appliedRef.current;
    if (!current) return;
    applySeqRef.current += 1;
    setTextNotice(null);
    updateDraft((d) => discardToApplied(d, current.response.cqs, current.text));
  }, [updateDraft]);

  /** A draft edit like any other: chips go struck-through and Update results applies it. */
  const clearAll = useCallback(
    () => updateDraft((d) => ({ ...d, panelState: {}, text: "", topicId: null })),
    [updateDraft],
  );

  // Infinite scroll: next window of the COMMITTED search, appended and deduped by pin.
  const loadMore = useCallback(async () => {
    const inputs = committedInputsRef.current;
    const current = appliedRef.current;
    if (!registry || !inputs || !current || nextOffset == null) return;
    if (loadingMoreRef.current || issuedSigRef.current !== null) return;
    const generation = commitRef.current;
    const controller = new AbortController();
    moreControllerRef.current = controller;
    loadingMoreRef.current = true;
    setLoadingMore(true);
    const resp = await runSearch({ ...inputs, offset: nextOffset }, registry, controller.signal);
    if (generation === commitRef.current && resp && resp.dataVersion === current.response.dataVersion) {
      setRows((prev) => {
        const seen = new Set(prev.map((r) => r.pin));
        return [...prev, ...resp.result.rows.filter((r) => !seen.has(r.pin))];
      });
      setNextOffset(resp.result.nextOffset);
    }
    if (generation === commitRef.current) {
      loadingMoreRef.current = false;
      setLoadingMore(false);
    }
  }, [registry, nextOffset]);

  // Full-match-set CSV of the search on screen (server-side, premium-gated).
  const exportApplied = useCallback(() => {
    if (registry && committedInputsRef.current) void exportCsv(committedInputsRef.current, registry);
  }, [registry]);

  const diff = useMemo(
    () => diffDraft(draft, applied?.response.cqs ?? null, applied?.text ?? ""),
    [draft, applied],
  );
  const chips: ChipItem[] = diff.chips;

  return {
    draft,
    applied: applied?.response ?? null,
    /** The text that was sent with the evaluated search (for wording what it understood). */
    appliedText: applied?.text ?? "",
    textNotice,
    rows,
    nextOffset,
    loading,
    loadingMore,
    /** A refresh is running over results that are already on screen. */
    refreshing: loading && applied !== null,
    unavailable,
    refreshFailed,
    /** The draft is exactly the search that is running, so Update results has nothing to add. */
    draftIsInFlight: loading && issuedSig !== null && issuedSig === inputsSignature(draft),
    chips,
    pendingCount: diff.pendingCount,
    map: { points: mapPoints, truncated: mapTruncated, total: mapTotal, status: mapStatus },
    apply,
    pickRecipe,
    pickNeighborhood,
    startAll,
    resume,
    editPanel,
    setText,
    setSort,
    removeFilter,
    restoreFilter,
    clearAll,
    discardChanges,
    startOver,
    loadMore,
    exportApplied,
  };
}
