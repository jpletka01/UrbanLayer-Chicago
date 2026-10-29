// Property Discovery page (08/09). Renders the controls and the results; the draft / applied /
// abort logic lives in useDiscoverySearch. The summary sentence, count and rows come from the
// last EVALUATED response.cqs (INV-4); the chips strip is a control surface and renders from
// the draft. Edits change the draft only: a search runs when the user presses Search, Enter or
// "Update results". The page never evaluates or filters — that is the backend's job.

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuthContext } from "../contexts/AuthContext";
import PageHeader from "./../components/PageHeader";
import UpgradePrompt from "./../components/UpgradePrompt";
import { AddFilterMenu, type FilterPopoverView } from "./AddFilterMenu";
import { Chips } from "./chips";
import { CoverageBanner } from "./CoverageBanner";
import { DescribeBox } from "./DescribeBox";
import { DiscoveryMap } from "./DiscoveryMap";
import { DiscoveryResults } from "./DiscoveryResults";
import { IndexAsOf } from "./IndexAsOf";
import { draftFilters } from "./draftModel";
import { FILTER_POPOVER_ANCHOR } from "./filterMenu";
import { StartPanel, type StartChoice } from "./StartPanel";
import { TextFeedback } from "./TextFeedback";
import { clearLastSearch, loadLastSearch, saveLastSearch, type SavedSearch } from "./lastSearch";
import { track } from "../lib/tracking";
import { loadRegistry } from "./registryClient";
import { summarize, seamPrompt } from "./summary";
import { useDiscoverySearch } from "./useDiscoverySearch";
import type { Registry, SortSpec } from "./types";

export default function DiscoveryPage() {
  const { t } = useTranslation("pages");
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const isPro = user?.tier === "premium" || user?.tier === "admin";

  const [registry, setRegistry] = useState<Registry | null>(null);
  // What the viewer last searched in this browser (a convenience: re-run, never shown as a result).
  const [resumable, setResumable] = useState<SavedSearch | null>(() => loadLastSearch());
  const search = useDiscoverySearch(registry, {
    onCommit: (inputs, resp) => {
      if (!registry) return;
      saveLastSearch({
        inputs: { panelState: inputs.panelState, text: inputs.text ?? "", sort: inputs.sort ?? null, topicId: inputs.topicId ?? null },
        sentence: summarize(resp.cqs, registry),
      });
    },
  });
  const {
    draft, applied: response, rows, nextOffset, loading, loadingMore, refreshing, unavailable,
    refreshFailed, draftIsInFlight, chips, pendingCount, map,
  } = search;
  const [hoveredPin, setHoveredPin] = useState<string | null>(null);
  // Kept separate from row-origin hover/focus so only a Pro map hover may ask
  // an already-loaded result row to scroll into view.
  const [mapHoveredPin, setMapHoveredPin] = useState<string | null>(null);
  const [showUpgrade, setShowUpgrade] = useState(false);
  // The "+ Add filter" menu / in-place filter editor (null = closed).
  const [popover, setPopover] = useState<FilterPopoverView>(null);
  const closePopover = useCallback(() => setPopover(null), []);
  const filterValues = useMemo(() => draftFilters(draft, response?.cqs ?? null), [draft, response]);
  // Below xl: one List|Map content pane (map stays mounted). Phones also get the
  // bottom-sheet filter drawer; tablet widths retain the inline filter rail.
  const [mobileTab, setMobileTab] = useState<"list" | "map">("list");
  const [wideLayout, setWideLayout] = useState(
    () => typeof window !== "undefined" && window.matchMedia?.("(min-width: 1280px)").matches === true,
  );

  useEffect(() => {
    loadRegistry().then(setRegistry);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const query = window.matchMedia("(min-width: 1280px)");
    const update = () => setWideLayout(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  // Hover linkage refers to rows/dots that are about to be replaced: drop it while a search runs.
  useEffect(() => {
    if (loading) {
      setHoveredPin(null);
      setMapHoveredPin(null);
    }
  }, [loading]);

  // Nothing runs on arrival (redesign Phase 2, replacing the 2026-07-01 auto-run of the first
  // recipe): until the first search the Start panel is shown, and every way in from it is one
  // explicit "search this". The panel goes away when a search starts and does not come back.
  const showStart = !!registry && !response && !loading && !unavailable;
  const onStartChoice = useCallback(
    (choice: StartChoice) => {
      switch (choice.kind) {
        case "recipe":
          track("discovery_start_choice", { kind: "recipe", id: choice.topic.id });
          search.pickRecipe(choice.topic);
          break;
        case "neighborhood":
          track("discovery_start_choice", { kind: "neighborhood", id: choice.areaId });
          search.pickNeighborhood(choice.areaId);
          break;
        case "all":
          track("discovery_start_choice", { kind: "all" });
          search.startAll();
          break;
        case "resume":
          if (resumable) {
            track("discovery_start_choice", { kind: "resume", id: resumable.inputs.topicId ?? null });
            search.resume(resumable.inputs);
          }
          break;
      }
    },
    [search, resumable],
  );
  // Back to the Start panel. What was just searched was saved as it committed, so offer it again.
  const { startOver } = search;
  const onNewSearch = useCallback(() => {
    startOver();
    setPopover(null);
    setResumable(loadLastSearch());
  }, [startOver]);
  const onForgetResume = useCallback(() => {
    clearLastSearch();
    setResumable(null);
  }, []);

  const onOpenParcel = useCallback(
    (pin: string) => navigate(`/scorecard?pin=${pin.replace(/\D/g, "")}`),
    [navigate],
  );

  const onUpgrade = useCallback(() => setShowUpgrade(true), []);

  const onRowHoverPin = useCallback((pin: string | null) => {
    setMapHoveredPin(null);
    setHoveredPin(pin);
  }, []);

  const onMapHoverPin = useCallback((pin: string | null) => {
    setHoveredPin(pin);
    setMapHoveredPin(pin);
  }, []);

  // Discovery→chat seam (#6): hand the result set to the analyst as an UNGROUNDED
  // pre-filled question (area + filter intent as prose). No pin, no payload — the
  // chat's native area retrieval answers it; App.tsx clears grounding on open.
  const onAskArea = useCallback(() => {
    if (!response || !registry) return;
    navigate(`/?q=${encodeURIComponent(seamPrompt(response.cqs, registry))}`);
  }, [navigate, response, registry]);

  const showUpdate = pendingCount > 0 && !draftIsInFlight;

  const textFeedback = registry ? (
    <TextFeedback
      registry={registry}
      notice={search.textNotice}
      applied={response ? { cqs: response.cqs, text: search.appliedText } : null}
    />
  ) : null;

  return (
    <div className="flex h-screen flex-col bg-dark-bg text-text-primary">
      <PageHeader sticky={false} maxWidthClass="max-w-[1920px]" />

      {/* Two regions (Phase 3b; the 420 px filter rail is gone). The results column is the Start
          panel before the first search and the search header over the results after it; the map
          takes the rest. Below xl the header stays on top and a List|Map toggle picks the pane. */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden xl:flex-row">
        <div
          data-testid="discovery-results-column"
          className={`flex min-h-0 min-w-0 flex-col border-dark-border xl:w-[460px] xl:flex-none xl:border-r 2xl:w-[580px] ${
            !showStart && mobileTab === "map" ? "flex-none" : "flex-1"
          }`}
        >
          {showStart && registry && (
            <StartPanel
              registry={registry}
              resumable={resumable}
              onChoose={onStartChoice}
              onForgetResume={onForgetResume}
              text={draft.text}
              onTextChange={search.setText}
              onSubmitText={search.apply}
              textFeedback={textFeedback}
            />
          )}
          {showStart && !registry && (
            <p className="p-4 text-body text-text-muted">{t("discovery.loadingFilters")}</p>
          )}

          {!showStart && registry && (
            <div
              data-testid="discovery-header"
              className="relative flex-shrink-0 space-y-2 border-b border-dark-border p-4"
            >
              <h1 className="sr-only">{t("discovery.title")}</h1>
              <CoverageBanner registry={registry} />
              <DescribeBox value={draft.text} onChange={search.setText} onSubmit={search.apply} />
              {textFeedback}
              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={onNewSearch}
                  data-testid="discovery-new-search"
                  className="text-caption text-text-muted transition-colors hover:text-accent"
                >
                  <span aria-hidden>← </span>{t("discovery.newSearch")}
                </button>
                <div className="xl:hidden">
                  <MobileTabToggle value={mobileTab} onChange={setMobileTab} />
                </div>
              </div>

              {/* The strip: chips from the DRAFT (control surface), "+ Add filter", then Update. */}
              <Chips
                items={chips}
                registry={registry}
                onRemove={search.removeFilter}
                onRestore={search.restoreFilter}
                onEdit={(id) => setPopover({ kind: "edit", id })}
              >
                <button
                  type="button"
                  {...{ [FILTER_POPOVER_ANCHOR]: "" }}
                  aria-haspopup="dialog"
                  aria-expanded={popover !== null}
                  onClick={() => setPopover((p) => (p ? null : { kind: "menu" }))}
                  data-testid="discovery-add-filter"
                  className="inline-flex items-center gap-1 rounded-full border border-dashed border-dark-border-strong px-2.5 py-1 text-micro text-text-secondary transition-colors hover:border-accent hover:text-accent"
                >
                  <span aria-hidden>+</span> {t("discovery.addFilter.button")}
                </button>
              </Chips>
              {showUpdate && (
                <div className="flex items-center gap-3">
                  <UpdateResultsButton count={pendingCount} onClick={search.apply} />
                  {response && (
                    <button
                      type="button"
                      onClick={search.discardChanges}
                      data-testid="discovery-discard-changes"
                      className="text-caption text-text-muted transition-colors hover:text-accent"
                    >
                      {t("discovery.addFilter.discard")}
                    </button>
                  )}
                </div>
              )}
              {popover && (
                <AddFilterMenu
                  registry={registry}
                  view={popover}
                  values={filterValues}
                  onChange={search.editPanel}
                  onView={setPopover}
                  onClose={closePopover}
                />
              )}

              {/* Evaluated sentence (INV-4): dims with the rest of the previous results. Sort sits
                  here, next to the list it orders. */}
              {response && (
                <div className="flex items-start justify-between gap-3">
                  <p
                    className={`min-w-0 text-body text-text-secondary transition-opacity ${refreshing ? "opacity-[0.55]" : ""}`}
                    aria-busy={refreshing}
                    data-testid="discovery-summary"
                  >
                    {summarize(response.cqs, registry)}
                  </p>
                  {draft.sort && <SortControl registry={registry} sort={draft.sort} onChange={search.setSort} />}
                </div>
              )}
              {/* Quiet seam — subordinate to the ranked list; the chat door is secondary to it. */}
              {response && response.result.total > 0 && !refreshing && (
                <button
                  type="button"
                  onClick={onAskArea}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-dark-border bg-dark-surface px-2.5 py-1 text-caption text-text-secondary transition-colors hover:border-accent/50 hover:text-accent"
                >
                  {t("discovery.askAnalystArea")} <span aria-hidden>→</span>
                </button>
              )}
              <IndexAsOf registry={registry} />
            </div>
          )}

          {!showStart && (
            <div
              data-testid="discovery-list-pane"
              className={`${mobileTab === "list" ? "flex" : "hidden"} min-h-0 flex-1 flex-col xl:flex`}
            >
              <div className="min-h-0 flex-1">
                {registry && (
                  <DiscoveryResults
                    response={response}
                    rows={rows}
                    registry={registry}
                    loading={loading}
                    unavailable={unavailable}
                    refreshFailed={refreshFailed}
                    onRetry={search.apply}
                    loadingMore={loadingMore}
                    hasMore={nextOffset != null}
                    onLoadMore={search.loadMore}
                    onRelax={search.removeFilter}
                    onOpenParcel={onOpenParcel}
                    hoveredPin={hoveredPin}
                    scrollToPin={isPro ? mapHoveredPin : null}
                    onHoverPin={onRowHoverPin}
                    onExport={search.exportApplied}
                    exportLocked={!isPro}
                    onUpgrade={onUpgrade}
                    onAskArea={onAskArea}
                  />
                )}
              </div>
            </div>
          )}
        </div>

        {/* Map: always at xl; below xl only on the Map tab and never on the Start panel. A SINGLE
            instance stays mounted behind List so toggles preserve the GL context. */}
        <div
          className={`${!showStart && mobileTab === "map" ? "block" : "hidden"} min-h-0 min-w-0 flex-1 xl:block`}
          data-testid="discovery-map-pane"
        >
          <DiscoveryMap
            points={map.points}
            truncated={map.truncated}
            total={map.total}
            hoveredPin={hoveredPin}
            onHoverPin={onMapHoverPin}
            onOpenParcel={onOpenParcel}
            colorBy={isPro ? "upside" : "land_use"}
            interactive={isPro}
            status={map.status}
            stale={refreshing}
            visible={(!showStart && mobileTab === "map") || wideLayout}
          />
        </div>
      </div>

      {showUpgrade && (
        <UpgradePrompt feature={t("discovery.title")} onClose={() => setShowUpgrade(false)} />
      )}
    </div>
  );
}

function UpdateResultsButton({
  count,
  onClick,
  className = "",
}: {
  count: number;
  onClick: () => void;
  className?: string;
}) {
  const { t } = useTranslation("pages");
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid="discovery-update-results"
      className={`rounded-lg bg-action px-3 py-1.5 text-caption font-medium text-text-on-accent transition-colors hover:bg-action-hover ${className}`}
    >
      {t("discovery.updateResults", { count })}
    </button>
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
