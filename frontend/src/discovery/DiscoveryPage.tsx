// Property Discovery page (08/09). Owns the raw inputs (panel state, free text, sort), runs
// the search, and renders summary + chips + results FROM response.cqs (INV-4). Premium-gated
// like the Site Explorer. The page never evaluates or filters — that is the backend's job.

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthContext } from "../contexts/AuthContext";
import PageHeader from "./../components/PageHeader";
import UpgradePrompt from "./../components/UpgradePrompt";
import { Chips } from "./chips";
import { CoverageBanner } from "./CoverageBanner";
import { DiscoveryFilterPanel } from "./DiscoveryFilterPanel";
import { DiscoveryMap } from "./DiscoveryMap";
import { DiscoveryResults } from "./DiscoveryResults";
import { RecipeShelf } from "./RecipeShelf";
import { loadRegistry } from "./registryClient";
import { exportCsv, runPins, runSearch, type SearchInputs } from "./searchClient";
import { summarize } from "./summary";
import { expandTopic, panelFromCqs } from "./topicCompiler";
import type {
  PanelState,
  PinPoint,
  Predicate,
  Registry,
  ResultRow,
  SearchResponse,
  SortSpec,
  TopicDef,
} from "./types";

export default function DiscoveryPage() {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const isPro = user?.tier === "premium" || user?.tier === "admin";

  const [registry, setRegistry] = useState<Registry | null>(null);
  const [panelState, setPanelState] = useState<PanelState>({});
  const [text, setText] = useState("");
  const [sort, setSort] = useState<SortSpec | null>(null);
  // Active recipe id — telemetry only (sent as topicId; the backend never re-expands).
  // Cleared the moment the user edits the panel/text, so it never misreports the query.
  const [topicId, setTopicId] = useState<string | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  // The accumulated result-list window (page 0 + appended pages, deduped by pin). This is
  // the list ONLY — the map (PR6) fetches the full coord set separately; the list is never
  // the source of truth for the map.
  const [rows, setRows] = useState<ResultRow[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  // Map state — the FULL ordered coord set from /search/pins, fetched once per search
  // (NOT from the rows window). loadMore never touches this.
  const [mapPoints, setMapPoints] = useState<PinPoint[]>([]);
  const [mapTruncated, setMapTruncated] = useState(false);
  const [mapTotal, setMapTotal] = useState(0);
  const [hoveredPin, setHoveredPin] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [showUpgrade, setShowUpgrade] = useState(false);
  // The inputs of the *issued* search, so loadMore re-issues the same query (later page) —
  // independent of any edits the user makes to the panel before scrolling.
  const lastInputs = useRef<SearchInputs | null>(null);

  useEffect(() => {
    loadRegistry().then((reg) => {
      setRegistry(reg);
      if (reg) setSort(reg.defaultSort);
    });
  }, []);

  const runWith = useCallback(
    async (state: PanelState, txt: string, srt: SortSpec | null, tid: string | null = null) => {
      if (!registry) return;
      if (!isPro) {
        setShowUpgrade(true);
        return;
      }
      const inputs: SearchInputs = { panelState: state, text: txt, sort: srt, topicId: tid };
      lastInputs.current = inputs;
      setLoading(true);
      // List + map fetched in parallel: list is the paginated window; map is the full
      // ordered coord set. They share the same request envelope → sequence-consistent.
      const [resp, pins] = await Promise.all([runSearch(inputs, registry), runPins(inputs, registry)]);
      setResponse(resp);
      setRows(resp?.result.rows ?? []);
      setNextOffset(resp?.result.nextOffset ?? null);
      setMapPoints(pins?.points ?? []);
      setMapTruncated(pins?.truncated ?? false);
      setMapTotal(pins?.total ?? 0);
      setLoading(false);
    },
    [registry, isPro],
  );

  // Infinite scroll: fetch the next window, append + dedupe by pin, advance the cursor.
  const loadMore = useCallback(async () => {
    if (!registry || nextOffset == null || loadingMore || !lastInputs.current) return;
    setLoadingMore(true);
    const resp = await runSearch({ ...lastInputs.current, offset: nextOffset }, registry);
    if (resp) {
      setRows((prev) => {
        const seen = new Set(prev.map((r) => r.pin));
        return [...prev, ...resp.result.rows.filter((r) => !seen.has(r.pin))];
      });
      setNextOffset(resp.result.nextOffset);
    }
    setLoadingMore(false);
  }, [registry, nextOffset, loadingMore]);

  // Any manual panel edit means the query is no longer "the recipe" → drop the telemetry id.
  const onPanelChange = useCallback((id: string, predicate: Predicate | null) => {
    setTopicId(null);
    setPanelState((prev) => {
      const next = { ...prev };
      if (predicate === null) delete next[id];
      else next[id] = predicate;
      return next;
    });
  }, []);

  const onTextChange = useCallback((value: string) => {
    setTopicId(null);
    setText(value);
  }, []);

  // Recipe click (PR8): expand the topic's presets into panel state as plain user filters
  // (editable/removable), apply its sort, send topicId for telemetry, and search. The
  // backend does NOT re-expand — userFilters carries the expanded set.
  const onPickRecipe = useCallback(
    (topic: TopicDef) => {
      if (!registry) return;
      const presets = expandTopic(topic.id, registry);
      const srt = topic.defaultSort ?? registry.defaultSort;
      setPanelState(presets);
      setText("");
      setSort(srt);
      setTopicId(topic.id);
      runWith(presets, "", srt, topic.id);
    },
    [registry, runWith],
  );

  // One-tap re-issue (06): fold the evaluated CQS back into the panel (so text-derived
  // constraints persist + stay editable), drop the chosen filter, and re-search. Never
  // re-expands a topic; clears the telemetry id since the query is now user-edited.
  const onRelax = useCallback(
    (filterId: string) => {
      if (!response) return;
      const next = panelFromCqs(response.cqs);
      delete next[filterId];
      setPanelState(next);
      setText("");
      setTopicId(null);
      runWith(next, "", sort, null);
    },
    [response, sort, runWith],
  );

  // Full-match-set CSV of the issued query (server-side, premium-gated). loadMore's window
  // is irrelevant — the export re-runs the same envelope server-side.
  const onExport = useCallback(() => {
    if (registry && lastInputs.current) exportCsv(lastInputs.current, registry);
  }, [registry]);

  const onOpenParcel = useCallback(
    (pin: string) => navigate(`/scorecard?pin=${pin.replace(/\D/g, "")}`),
    [navigate],
  );

  return (
    <div className="flex h-screen flex-col bg-dark-bg text-text-primary">
      <PageHeader sticky={false} maxWidthClass="max-w-[1920px]" />

      {registry && <CoverageBanner registry={registry} />}

      <div className="flex flex-1 flex-col overflow-hidden md:flex-row">
        {/* Left: inputs */}
        <div className="flex w-full flex-shrink-0 flex-col overflow-hidden border-r border-dark-border md:w-[420px] lg:w-[460px]">
          <div className="flex-shrink-0 space-y-3 border-b border-dark-border p-4">
            <div>
              <h1 className="text-lg font-semibold tracking-tight">Property Discovery</h1>
              <p className="text-[11px] text-text-muted">
                Start with a goal or describe what you're looking for — then refine.
              </p>
            </div>
            <input
              type="text"
              value={text}
              onChange={(e) => onTextChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") runWith(panelState, text, sort, topicId);
              }}
              placeholder='Describe what you want — e.g. "vacant multifamily near the L, built after 1990"'
              className="w-full rounded-lg border border-dark-border bg-dark-elevated px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
            />
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => runWith(panelState, text, sort, topicId)}
                disabled={!registry || loading}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {loading ? "Searching…" : "Search"}
              </button>
              {registry && sort && (
                <SortControl registry={registry} sort={sort} onChange={setSort} />
              )}
            </div>
          </div>

          <div className="flex-1 space-y-5 overflow-y-auto p-4">
            {registry ? (
              <>
                <RecipeShelf registry={registry} onPick={onPickRecipe} />
                <div>
                  <h3 className="mb-2 text-[10px] uppercase tracking-wider text-text-muted">
                    Refine
                  </h3>
                  <DiscoveryFilterPanel registry={registry} state={panelState} onChange={onPanelChange} />
                </div>
              </>
            ) : (
              <p className="text-sm text-text-muted">Loading filters…</p>
            )}
          </div>
        </div>

        {/* Middle: summary + chips + results list */}
        <div className="flex min-w-0 flex-col overflow-hidden border-r border-dark-border md:w-[500px] md:flex-shrink-0 lg:w-[560px]">
          {response && registry && (
            <div className="flex-shrink-0 space-y-2 border-b border-dark-border p-4">
              <p className="text-sm text-text-secondary">{summarize(response.cqs, registry)}</p>
              <Chips cqs={response.cqs} registry={registry} onRemove={onRelax} />
            </div>
          )}
          <div className="min-h-0 flex-1">
            {registry && (
              <DiscoveryResults
                response={response}
                rows={rows}
                registry={registry}
                loading={loading}
                loadingMore={loadingMore}
                hasMore={nextOffset != null}
                onLoadMore={loadMore}
                onRelax={onRelax}
                onOpenParcel={onOpenParcel}
                hoveredPin={hoveredPin}
                onHoverPin={setHoveredPin}
                onExport={onExport}
              />
            )}
          </div>
        </div>

        {/* Right: results map (full coord set). Hidden on mobile — the mobile List|Map
            toggle is PR10; here the map is desktop-only so it doesn't stack giant. */}
        <div className="hidden min-w-0 flex-1 md:block">
          <DiscoveryMap
            points={mapPoints}
            truncated={mapTruncated}
            total={mapTotal}
            hoveredPin={hoveredPin}
            onHoverPin={setHoveredPin}
            onOpenParcel={onOpenParcel}
          />
        </div>
      </div>

      {showUpgrade && (
        <UpgradePrompt feature="Property Discovery" onClose={() => setShowUpgrade(false)} />
      )}
    </div>
  );
}

function SortControl({
  registry,
  sort,
  onChange,
}: {
  registry: Registry;
  sort: SortSpec;
  onChange: (s: SortSpec) => void;
}) {
  return (
    <div className="flex items-center gap-1.5 text-xs">
      <select
        value={sort.key}
        onChange={(e) => onChange({ ...sort, key: e.target.value })}
        className="rounded-md border border-dark-border bg-dark-elevated px-2 py-1.5 text-text-primary focus:border-accent focus:outline-none"
      >
        {registry.sortKeys.map((sk) => (
          <option key={sk.key} value={sk.key}>
            {sk.key.replace(/_/g, " ")}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={() => onChange({ ...sort, dir: sort.dir === "asc" ? "desc" : "asc" })}
        className="rounded-md border border-dark-border px-2 py-1.5 text-text-secondary transition-colors hover:border-text-muted"
        aria-label="Toggle sort direction"
      >
        {sort.dir === "asc" ? "↑" : "↓"}
      </button>
    </div>
  );
}
