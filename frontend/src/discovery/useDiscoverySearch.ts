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
  removeFromDraft,
  restoreToDraft,
  type ChipItem,
  type DiscoveryDraft,
} from "./draftModel";
import { exportCsv, runPins, runSearch, type SearchInputs } from "./searchClient";
import { expandTopic } from "./topicCompiler";
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

export function useDiscoverySearch(registry: Registry | null) {
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

  /** Search / Enter / Update results: send the draft as it is now. */
  const apply = useCallback(() => {
    void issue(toInputs(draftRef.current));
  }, [issue]);

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
      draftRef.current = next;
      setDraft(next);
      void issue(toInputs(next));
    },
    [registry, issue],
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
    (text: string) => updateDraft((d) => ({ ...d, text, topicId: null })),
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
    editPanel,
    setText,
    setSort,
    removeFilter,
    restoreFilter,
    clearAll,
    loadMore,
    exportApplied,
  };
}
