// Property Discovery page (08/09). Owns the raw inputs (panel state, free text, sort), runs
// the search, and renders summary + chips + results FROM response.cqs (INV-4). Premium-gated
// like the Site Explorer. The page never evaluates or filters — that is the backend's job.

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation("pages");
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
  // Mobile (below md): single column with a List|Map toggle (map stays mounted) + a
  // bottom-sheet filter drawer. No effect on the desktop split.
  const [mobileTab, setMobileTab] = useState<"list" | "map">("list");
  const [filtersOpen, setFiltersOpen] = useState(false);
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
      // PR9: free users RUN the search and hit the teaser (top 10 + wall), not a pre-search
      // wall. The server enforces the cap; the FE renders the teaser from result.gated.
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

  const onUpgrade = useCallback(() => setShowUpgrade(true), []);

  return (
    <div className="flex h-screen flex-col bg-dark-bg text-text-primary">
      <PageHeader sticky={false} maxWidthClass="max-w-[1920px]" />

      {registry && <CoverageBanner registry={registry} />}

      <div className="flex flex-1 flex-col overflow-hidden md:flex-row">
        {/* Inputs column (desktop left rail; mobile top controls) */}
        <div className="flex w-full flex-shrink-0 flex-col overflow-hidden border-r border-dark-border md:w-[420px] lg:w-[460px]">
          <div className="flex-shrink-0 space-y-3 border-b border-dark-border p-4">
            <div>
              <h1 className="text-section">{t("discovery.title")}</h1>
              <p className="text-micro text-text-muted">
                {t("discovery.subtitle")}
              </p>
            </div>
            <input
              type="text"
              value={text}
              onChange={(e) => onTextChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") runWith(panelState, text, sort, topicId);
              }}
              placeholder={t("discovery.searchPlaceholder")}
              aria-label={t("discovery.searchAria")}
              className="w-full rounded-lg border border-dark-border bg-dark-elevated px-3 py-2 text-body text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
            />
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => runWith(panelState, text, sort, topicId)}
                disabled={!registry || loading}
                className="rounded-lg bg-accent px-4 py-2 text-title text-text-on-accent transition-colors hover:bg-accent-hover disabled:opacity-50"
              >
                {loading ? t("discovery.searching") : t("discovery.search")}
              </button>
              {registry && sort && (
                <SortControl registry={registry} sort={sort} onChange={setSort} />
              )}
            </div>
            {/* Mobile-only: List|Map toggle + Edit-filters (opens the bottom sheet) */}
            <div className="flex items-center gap-2 md:hidden">
              <MobileTabToggle value={mobileTab} onChange={setMobileTab} />
              <button
                type="button"
                onClick={() => setFiltersOpen(true)}
                className="ml-auto rounded-lg border border-dark-border px-3 py-1.5 text-caption text-text-secondary transition-colors hover:border-dark-border-strong"
              >
                {t("discovery.editFilters")}
                {Object.keys(panelState).length > 0 && (
                  <span className="ml-1 text-accent">({Object.keys(panelState).length})</span>
                )}
              </button>
            </div>
          </div>

          {/* Mobile-only: recipes as a horizontal scroll-snap row */}
          {registry && (
            <div className="flex-shrink-0 border-b border-dark-border p-3 md:hidden">
              <RecipeShelf registry={registry} onPick={onPickRecipe} horizontal />
            </div>
          )}

          {/* Desktop-only: recipe shelf + the inline refinement drawer */}
          <div className="hidden flex-1 space-y-5 overflow-y-auto p-4 md:block">
            {registry ? (
              <>
                <RecipeShelf registry={registry} onPick={onPickRecipe} />
                <div>
                  <h3 className="mb-2 text-overline uppercase text-text-muted">
                    {t("discovery.refine")}
                  </h3>
                  <DiscoveryFilterPanel registry={registry} state={panelState} onChange={onPanelChange} />
                </div>
              </>
            ) : (
              <p className="text-body text-text-muted">{t("discovery.loadingFilters")}</p>
            )}
          </div>
        </div>

        {/* Results column: desktop always; mobile only when the List tab is active */}
        <div
          className={`${
            mobileTab === "list" ? "flex" : "hidden"
          } min-w-0 flex-1 flex-col overflow-hidden border-r border-dark-border md:flex md:w-[500px] md:flex-1 md:flex-shrink-0 lg:w-[560px]`}
        >
          {response && registry && (
            <div className="flex-shrink-0 space-y-2 border-b border-dark-border p-4">
              <p className="text-body text-text-secondary">{summarize(response.cqs, registry)}</p>
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
                exportLocked={!isPro}
                onUpgrade={onUpgrade}
              />
            )}
          </div>
        </div>

        {/* Map column: desktop always; mobile only when the Map tab is active. A SINGLE
            instance — hidden via CSS (not unmounted) when on List, so the GL context is
            preserved across toggles (mirrors MobileSidebarSheet's kept-mounted map). */}
        <div className={`${mobileTab === "map" ? "block" : "hidden"} min-w-0 flex-1 md:block`}>
          <DiscoveryMap
            points={mapPoints}
            truncated={mapTruncated}
            total={mapTotal}
            hoveredPin={hoveredPin}
            onHoverPin={setHoveredPin}
            onOpenParcel={onOpenParcel}
            colorBy={isPro ? "upside" : "land_use"}
            interactive={isPro}
          />
        </div>
      </div>

      {/* Mobile filter bottom sheet (full-height refinement drawer) */}
      {filtersOpen && registry && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label={t("discovery.filtersAria")}>
          <div className="absolute inset-0 bg-black/50" onClick={() => setFiltersOpen(false)} />
          <div className="absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto rounded-t-xl border-t border-dark-border bg-dark-surface p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-title">{t("discovery.filtersHeading")}</h3>
              <button
                type="button"
                onClick={() => setFiltersOpen(false)}
                className="rounded-lg bg-accent px-3 py-1.5 text-caption font-medium text-text-on-accent transition-colors hover:bg-accent-hover"
              >
                {t("common:done")}
              </button>
            </div>
            <DiscoveryFilterPanel registry={registry} state={panelState} onChange={onPanelChange} />
          </div>
        </div>
      )}

      {showUpgrade && (
        <UpgradePrompt feature={t("discovery.title")} onClose={() => setShowUpgrade(false)} />
      )}
    </div>
  );
}

function MobileTabToggle({
  value,
  onChange,
}: {
  value: "list" | "map";
  onChange: (v: "list" | "map") => void;
}) {
  const { t } = useTranslation("pages");
  const opts: Array<"list" | "map"> = ["list", "map"];
  return (
    <div role="group" aria-label={t("discovery.viewAria")} className="inline-flex rounded-md border border-dark-border">
      {opts.map((opt) => (
        <button
          key={opt}
          type="button"
          aria-pressed={value === opt}
          onClick={() => onChange(opt)}
          className={`px-3 py-1.5 text-caption transition-colors ${
            value === opt ? "bg-accent/15 text-accent" : "text-text-secondary hover:text-text-primary"
          } ${opt === "list" ? "rounded-l-md" : "rounded-r-md"}`}
        >
          {opt === "list" ? t("discovery.viewList") : t("discovery.viewMap")}
        </button>
      ))}
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
  const { t } = useTranslation("pages");
  return (
    <div className="flex items-center gap-1.5 text-caption">
      <select
        value={sort.key}
        onChange={(e) => onChange({ ...sort, key: e.target.value })}
        className="rounded-lg border border-dark-border bg-dark-elevated px-2 py-1.5 text-text-primary focus:border-accent focus:outline-none"
      >
        {registry.sortKeys.map((sk) => (
          <option key={sk.key} value={sk.key}>
            {t(`discovery.sort.${sk.key}`, sk.key.replace(/_/g, " "))}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={() => onChange({ ...sort, dir: sort.dir === "asc" ? "desc" : "asc" })}
        className="rounded-lg border border-dark-border px-2 py-1.5 text-text-secondary transition-colors hover:border-dark-border-strong"
        aria-label={t("discovery.toggleSortAria")}
      >
        {sort.dir === "asc" ? "↑" : "↓"}
      </button>
    </div>
  );
}
