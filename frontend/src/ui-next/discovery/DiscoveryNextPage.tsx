// Discovery in the new frame (brief "Discovery — Approved"; decision Item 104). It opens on the map of the city
// (Explore): every lot drawn as its shape and filled by one measure, five quick filters that dim the lots that don't
// match (the server evaluates them for the view), and "Search these lots". One search box takes an address, a
// community area or a description (the rule-based compiler; words it can't read are said). The goals are "Try"
// chips. After a search, one focus at a time: List (picture cards) or Map (matches only, as outlines). On a phone the
// map comes first and the list is a sheet over it. Same engine as today's page: useDiscoverySearch → /search.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowRight, ChevronDown, Circle, Hash, House, List, LoaderCircle, Map as MapIcon, MapPin, Maximize2, Palette,
  Receipt, Search, Shovel, Sprout, Store, Target, TrendingDown, TriangleAlert, X, type LucideIcon,
} from "lucide-react";
import { loadRegistry } from "../../discovery/registryClient";
import { useDiscoverySearch } from "../../discovery/useDiscoverySearch";
import { recipeStatus } from "../../discovery/recipeStatus";
import { chipLabel } from "../../discovery/chips";
import { COMMUNITY_AREAS } from "../../discovery/communityAreas";
import { HIDE_UNUSUAL } from "../../discovery/draftModel";
import { profileAddress } from "../../discovery/rowFigures";
import type { FilterDef, PanelState, Predicate, Registry, ResultRow, TopicDef } from "../../discovery/types";
import { getAutocomplete } from "../../lib/api";
import type { AddressSuggestion } from "../../lib/types";
import { track } from "../../lib/tracking";
import { useIsPhone } from "../../lib/useIsPhone";
import { AppFrame } from "../frame/AppFrame";
import { STROKE } from "../icons";
import { Pill } from "../ui/Blocks";
import { ExploreMap, type Ring, type ViewBox } from "./ExploreMap";
import { FilterBar } from "./FilterBar";
import { fetchParcelRow } from "../../discovery/searchClient";
import { LotCard } from "./LotCard";
import { useNeighborhoods, useViewMatches, type Hood } from "./discoveryData";
import {
  DEFAULT_MEASURE, LOTS_MIN_ZOOM, cardModel, foldComplexes, MEASURES, QUICK_FILTERS, RING_MILES, classifyQuery, parsePin, placeRegion,
  placeSuggestions,
  type Place as AreaPlace,
  ROOM_SORT, measureSteps, quickFromPanel, quickPanel, ringMiles, ringRegion, type MeasureId, type QuickId,
} from "./discoveryModel";

type Focus = "map" | "list";
interface Place { lat: number; lon: number; label: string; /** Set when the place is a lot found by PIN. */ pin?: string }

const numLocale = (lang: string) => (lang.startsWith("es") ? "es-MX" : "en-US");

export default function DiscoveryNextPage() {
  const { t, i18n } = useTranslation("next");
  const { t: tp } = useTranslation("pages");
  const navigate = useNavigate();
  const phone = useIsPhone();
  const fmt = useMemo(() => new Intl.NumberFormat(numLocale(i18n.language)), [i18n.language]);
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [registryFailed, setRegistryFailed] = useState(false);
  const search = useDiscoverySearch(registry, {
    includeAreaCounts: true,
    onCommit: (_inputs, response) => track("discovery_search", { total: response.result.total, source: "next" }),
  });
  useEffect(() => {
    loadRegistry().then((r) => (r ? setRegistry(r) : setRegistryFailed(true))).catch(() => setRegistryFailed(true));
  }, []);

  const response = search.applied;
  const hoods = useNeighborhoods();
  const [focus, setFocus] = useState<Focus>("map");
  const [measure, setMeasure] = useState<MeasureId>(DEFAULT_MEASURE);
  const [showZoning, setShowZoning] = useState(false);
  const [view, setView] = useState<ViewBox | null>(null);
  const [camera, setCamera] = useState<{ bbox?: [number, number, number, number]; center?: [number, number]; zoom?: number; seq: number } | null>(null);
  const moveTo = useCallback((c: Omit<NonNullable<typeof camera>, "seq">) => setCamera((p) => ({ ...c, seq: (p?.seq ?? 0) + 1 })), []);
  const [goalsFolded, setGoalsFolded] = useState(false);
  const [walkPreview, setWalkPreview] = useState<number | null>(null);
  const [barPending, setBarPending] = useState<PanelState | null>(null);
  const [place, setPlace] = useState<Place | null>(null);
  const [ring, setRing] = useState<Ring | null>(null);
  const [sheet, setSheet] = useState<"peek" | "half" | "full">("peek");

  // Explore's quick filters (no search yet): the server evaluates them for the view.
  const [quick, setQuick] = useState<Set<QuickId>>(new Set());
  const explorePanel = useMemo(() => (quick.size ? quickPanel(quick) : null), [quick]);
  const viewMatches = useViewMatches(registry, response ? null : explorePanel, view);

  // What the map outlines and labels.
  const searchPins = useMemo(
    () => (response?.pins?.points ?? search.map.points).map((p) => p.pin.replace(/-/g, "").slice(0, 10)),
    [response, search.map.points],
  );
  const matches = response ? searchPins : explorePanel ? viewMatches.data?.pins ?? [] : null;
  const areaCounts = response ? response.areaCounts ?? null : explorePanel ? viewMatches.data?.areaCounts ?? null : null;
  const lotZoom = !!view && view.zoom >= LOTS_MIN_ZOOM;
  const inView = useMemo(() => {
    if (!response || !view) return null;
    const [w, s, e, n] = view.bbox;
    return (response.pins?.points ?? search.map.points).filter((p) => p.lat != null && p.lon != null && p.lon >= w && p.lon <= e && p.lat >= s && p.lat <= n).length;
  }, [response, view, search.map.points]);

  // The search's quick filters mirror its panel (a goal can turn some on).
  const searchQuick = useMemo(() => quickFromPanel(search.draft.panelState), [search.draft.panelState]);
  const quickOn = response ? searchQuick : quick;
  const toggleQuick = (id: QuickId) => {
    const next = new Set(quickOn);
    if (next.has(id)) next.delete(id); else next.add(id);
    if (response) {
      search.startWith({ ...search.draft, panelState: quickPanel(next, search.draft.panelState), topicId: null });
    } else {
      setQuick(next);
    }
  };

  // Search these lots: the quick filters (or every lot) in the current view become a search.
  const searchView = () => {
    if (!registry) return;
    const scope = view && lotZoom ? { mode: "viewport" as const, bbox: view.bbox } : null;
    search.startWith({ panelState: quickPanel(quick), text: "", sort: { ...ROOM_SORT }, topicId: null, scope });
    setFocus(phone ? "map" : "list");
    setSheet("half");
  };
  const listInView = () => {
    if (!view) return;
    search.startWith({ ...search.draft, scope: { mode: "viewport", bbox: view.bbox } });
    setFocus("list");
    setSheet("full");
  };
  const startOver = () => {
    search.startOver();
    setQuick(new Set());
    setRing(null);
    setPlace(null);
    setFocus("map");
    setSheet("peek");
  };

  // The ring around an address: a radius filter the server evaluates (re-run after a resize settles).
  const ringTimer = useRef<number | undefined>(undefined);
  const searchRing = useCallback((r: Ring) => {
    if (!registry) return;
    const base = { ...(response ? search.draft.panelState : quickPanel(quick)) };
    delete base.neighborhood;
    search.startWith({
      panelState: { ...base, radius: { kind: "region", regions: [ringRegion(r.lat, r.lon, r.miles)] } as PanelState[string] },
      text: "", sort: { ...ROOM_SORT }, topicId: null, scope: null,
    });
    setFocus(phone ? "map" : "list");
    setSheet("half");
  }, [registry, response, search, quick, phone]);
  const ringActive = !!response && !!search.draft.panelState.radius;
  const resizeRing = (miles: number) => {
    if (!ring) return;
    const next = { ...ring, miles };
    setRing(next);
    if (ringActive) {
      window.clearTimeout(ringTimer.current);
      ringTimer.current = window.setTimeout(() => searchRing(next), 450);
    }
  };

  // The one search box.
  const [text, setText] = useState("");
  const submit = (raw = text) => {
    const kind = classifyQuery(raw, COMMUNITY_AREAS, hoods);
    if (kind.kind === "pin") { pickPin(kind.pin); return; }
    if (kind.kind === "address") {
      getAutocomplete(raw).then((s) => { if (s[0]) pickAddress(s[0]); });
      return;
    }
    if (kind.kind === "area" || kind.kind === "hood") { pickPlace(kind); return; }
    search.setText(raw);
    search.setSort({ ...ROOM_SORT });
    window.setTimeout(() => { search.apply(); setFocus(phone ? "map" : "list"); setSheet("half"); }, 0);
  };
  const pickAddress = (s: AddressSuggestion) => {
    setPlace({ lat: s.lat, lon: s.lon, label: s.address });
    setRing(null);
    moveTo({ center: [s.lon, s.lat], zoom: 16.4 });
    setFocus("map");
  };
  // A PIN goes straight to its lot (Item 110: a lot with no street address of its own is found by its PIN).
  const [pinMissing, setPinMissing] = useState<string | null>(null);
  const pickPin = (pin: string) => {
    setPinMissing(null);
    fetchParcelRow(pin, ROOM_SORT.key).then((row) => {
      if (!row || row.lat == null || row.lon == null) { setPinMissing(pin); return; }
      const label = row.address && !row.address.startsWith("~") ? cardModel(row).title : pin;
      setPlace({ lat: row.lat, lon: row.lon, label, pin: row.pin });
      setRing(null);
      moveTo({ center: [row.lon, row.lat], zoom: 17.5 });
      setFocus("map");
    }).catch(() => setPinMissing(pin));
  };
  // A neighborhood or community area narrows the search on screen (its filters stay), never replaces it.
  const pickPlace = (place: AreaPlace) => {
    if (!registry) return;
    const base = { ...(barPending ?? (response ? search.draft.panelState : quickPanel(quick))) };
    search.startWith({
      panelState: { ...base, neighborhood: { kind: "region", regions: [placeRegion(place)] } as PanelState[string] },
      text: "", sort: response ? search.draft.sort ?? { ...ROOM_SORT } : { ...ROOM_SORT }, topicId: null, scope: null,
    });
    setFocus(phone ? "map" : "list");
    setSheet("half");
  };
  const pickArea = (id: number) => pickPlace({ kind: "area", id, name: COMMUNITY_AREAS[id] ?? String(id) });

  // A new search frames its matches once (the visitor's own moves win after that); a view search keeps its view.
  const fit = useMemo(() => {
    if (!response || response.cqs.scope?.mode === "viewport" || response.cqs.filters.neighborhood) return null;  // a place frames itself
    const pts = (response.pins?.points ?? []).filter((p) => p.lat != null && p.lon != null);
    if (!pts.length) return null;
    let w = 180, s = 90, e = -180, n = -90;
    for (const p of pts) { w = Math.min(w, p.lon!); e = Math.max(e, p.lon!); s = Math.min(s, p.lat!); n = Math.max(n, p.lat!); }
    return { bbox: [w, s, e, n] as [number, number, number, number], key: response };
  }, [response]);

  const topics = (registry?.topics ?? []).map((topic) => ({ topic, status: recipeStatus(registry!, topic, tp) }));
  const chips = response
    ? Object.entries(response.cqs.filters).filter(([id, a]) => id !== HIDE_UNUSUAL && a.source !== "default")
    : [];
  const defOf = (id: string): FilterDef | undefined => registry?.filters.find((f) => f.id === id);
  const hoodNameOf = (slug: string | null | undefined) => (slug ? hoods.find((h) => h.slug === slug)?.name ?? null : null);
  const hoodName = (ref: string) => hoods.find((h) => `hood:${h.slug}` === ref)?.name ?? ref.slice(5).replace(/_/g, " ");
  const label = (id: string, p: Predicate) => {
    if (id === "neighborhood" && p.kind === "region" && p.regions.some((r) => r.startsWith("hood:"))) {
      return p.regions.map((r) => (r.startsWith("hood:") ? hoodName(r) : COMMUNITY_AREAS[Number(r.split(":")[1])] ?? r)).join(t("discovery.or"));
    }
    const mi = id === "radius" && p.kind === "region" ? ringMiles(p.regions[0]) : null;
    return mi != null ? t("discovery.ringChip", { mi: new Intl.NumberFormat(numLocale(i18n.language), { maximumFractionDigits: 2 }).format(mi) }) : chipLabel(id, p, defOf(id));
  };

  // The place the search is limited to, from the evaluated query (a pick, or "in Wicker Park" in a description).
  const highlight = useMemo(() => {
    const f = response?.cqs.filters.neighborhood?.predicate;
    if (!f || f.kind !== "region") return null;
    return f.regions.map((r) => r.startsWith("hood:")
      ? { kind: "hood" as const, geometry: hoods.find((h) => `hood:${h.slug}` === r)?.geometry ?? null }
      : { kind: "area" as const, id: Number(r.split(":")[1]) });
  }, [response, hoods]);

  const map = (
    <ExploreMap
      measure={measure}
      matches={matches}
      areaCounts={areaCounts}
      ring={ring}
      onRingChange={resizeRing}
      place={place}
      focus={camera}
      fit={fit}
      showZoning={showZoning}
      walkMiles={walkPreview}
      highlight={highlight}
      onView={setView}
      onPickArea={pickArea}
      sortKey={response?.cqs.sort.key ?? registry?.defaultSort.key ?? "lot_size"}
      className="absolute inset-0"
    />
  );

  const countLine = response
    ? response.result.total === 0
      ? t("discovery.none")
      : t("discovery.count", { count: response.result.total, total: fmt.format(response.result.total) })
    : null;

  const applyFilters = (panel: PanelState) => {
    if (!registry) return;
    search.startWith({ ...search.draft, panelState: panel, sort: response ? search.draft.sort ?? { ...ROOM_SORT } : { ...ROOM_SORT }, topicId: null, text: response ? search.draft.text : "" });
    setFocus(phone ? "map" : "list");
    setSheet("half");
  };
  const filterBar = registry ? (
    <FilterBar registry={registry} panel={response ? search.draft.panelState : quickPanel(quick)}
      scope={response ? search.draft.scope ?? null : null} onApply={applyFilters} onWalkPreview={setWalkPreview}
      onPending={setBarPending} compact={phone} />
  ) : null;
  const searchBox = (
    <div className="relative min-w-0 flex-1">
      <SearchBox text={text} setText={setText} onSubmit={submit} onAddress={pickAddress} onPlace={pickPlace} hoods={hoods} busy={search.loading} disabled={!registry} />
      {pinMissing && <p role="status" className="mt-1 text-caption nx-muted">{t("discovery.pinMissing", { pin: pinMissing })}</p>}
    </div>
  );
  const focusToggle = response && !phone ? (
    <div role="group" aria-label={t("discovery.focus.label")} className="flex shrink-0 rounded-xl bg-nx-ink/5 p-1">
      {(["list", "map"] as const).map((f) => {
        const Icon = f === "list" ? List : MapIcon;
        return (
          <button key={f} type="button" aria-pressed={focus === f} onClick={() => setFocus(f)}
            className={`inline-flex h-8 items-center gap-1.5 rounded-lg px-3 ${focus === f ? "bg-nx-page shadow-sm" : "hover:bg-nx-ink/5"}`}>
            <Icon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t(`discovery.focus.${f}`)}
          </button>
        );
      })}
    </div>
  ) : null;
  const goalsOpen = !response && !goalsFolded;

  return (
    <AppFrame
      fill
      crumbs={[t("discovery.crumb")]}
      bar={phone ? searchBox : (
        <div className="flex min-w-0 items-start gap-3">
          <div className="w-[18rem] shrink-0 xl:w-[22rem]">{searchBox}</div>
          <div className="min-w-0 flex-1">{filterBar}</div>
          {focusToggle}
        </div>
      )}
    >
      <h1 className="sr-only">{t("discovery.title")}</h1>
      <div className="flex min-h-0 flex-1 flex-col">
        {/* Below the bar only what a search needs: a phone's filter groups, what the search was, what it couldn't read. */}
        {(phone || response || search.textNotice || registryFailed || search.unavailable) && (
          <div className="z-20 flex flex-col gap-2 border-b border-nx-ink/10 bg-nx-page px-4 py-2 sm:px-7">
            {phone && filterBar}
            {search.textNotice && (
              <p role="status" className="flex flex-wrap items-center gap-2 text-caption">
                <Pill tone="yellow" icon={TriangleAlert}>{t("discovery.notUnderstood")}</Pill>
                <span className="nx-muted">{search.textNotice.words.join(", ")}</span>
              </p>
            )}
            {response && search.appliedText && (response.cqs.meta?.textResidual?.length ?? 0) > 0 && (
              <p role="status" className="flex flex-wrap items-center gap-2 text-caption">
                <Pill tone="yellow" icon={TriangleAlert}>{t("discovery.notUnderstood")}</Pill>
                <span className="nx-muted">{response.cqs.meta!.textResidual!.join(", ")}</span>
              </p>
            )}
            {response && (
              <div className="flex flex-wrap items-center gap-2 text-caption" data-testid="search-summary">
                <span className="font-semibold" role="status">{countLine}</span>
                {chips.map(([id, a]) => (
                  <span key={id} className="inline-flex items-center gap-1 rounded-full bg-nx-ink/5 py-1 pl-3 pr-1">
                    {label(id, a.predicate as Predicate)}
                    <button type="button" aria-label={t("discovery.removeFilter", { label: label(id, a.predicate as Predicate) })}
                      onClick={() => { const panel = { ...search.draft.panelState }; delete panel[id]; search.startWith({ ...search.draft, panelState: panel, text: "", topicId: null }); }}
                      className="grid h-6 w-6 place-items-center rounded-full hover:bg-nx-ink/10 touch-hit">
                      <X aria-hidden className="h-3 w-3" strokeWidth={STROKE} />
                    </button>
                  </span>
                ))}
                {response.cqs.scope?.mode === "viewport" && <Pill tone="gray" icon={MapIcon}>{t("discovery.inThisView")}</Pill>}
                <button type="button" onClick={startOver} className="ml-auto inline-flex items-center gap-1 rounded-lg px-2 py-1 underline underline-offset-2 hover:bg-nx-ink/5">
                  {t("discovery.newSearch")}
                </button>
              </div>
            )}
            {registryFailed && <p role="alert" className="text-caption nx-muted">{t("discovery.unavailable")}</p>}
            {search.unavailable && <p role="alert" className="text-caption nx-muted">{t("discovery.searchFailed")}</p>}
          </div>
        )}

        {/* The map, always mounted; List covers it on a desktop, a sheet sits over it on a phone. */}
        <div className="relative min-h-0 flex-1">
          {map}
          <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between gap-2 p-3">
            <div className="flex min-w-0 flex-col items-start gap-2">
              <QuickFilters on={quickOn} onToggle={toggleQuick} loading={!response && viewMatches.loading} />
              {!phone && !response && registry && (
                <GoalCard open={goalsOpen} onToggle={() => setGoalsFolded((f) => !f)} topics={topics} counts={registry.recipeCounts ?? {}} fmt={fmt}
                  onPick={(topic) => { search.pickRecipe(topic); setFocus("list"); }} />
              )}
            </div>
            <MeasureKey key={phone ? "phone" : "desk"} measure={measure} onMeasure={setMeasure} showZoning={showZoning} onZoning={setShowZoning} compact={phone} />
          </div>
          {place && <PlaceCard place={place} ring={ring} onRing={(miles) => { const r = { lat: place.lat, lon: place.lon, miles }; setRing(r); }}
            onSearchRing={() => ring && searchRing(ring)} ringActive={ringActive}
            onClose={() => { setPlace(null); setRing(null); }} />}

          {/* Explore's call to action, and Map focus's "N lots in view · List them". */}
          {!phone && focus === "map" && (
            <div className="pointer-events-none absolute inset-x-0 bottom-20 z-10 flex justify-center px-4">
              {!response ? (
                <button type="button" onClick={searchView} className="pointer-events-auto inline-flex items-center gap-2 rounded-full bg-nx-primary px-5 py-2.5 font-medium text-nx-primary-fg shadow-[0_6px_24px_rgb(0_0_0/0.18)]" data-testid="search-view">
                  <Search aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
                  {exploreLabel(t, fmt, explorePanel, viewMatches.data, lotZoom)}
                </button>
              ) : lotZoom && inView != null ? (
                <button type="button" onClick={listInView} className="pointer-events-auto inline-flex items-center gap-2 rounded-full bg-nx-primary px-5 py-2.5 font-medium text-nx-primary-fg shadow-[0_6px_24px_rgb(0_0_0/0.18)]" data-testid="list-in-view">
                  {t("discovery.inView", { count: inView, n: fmt.format(inView) })}
                  <span aria-hidden>·</span>{t("discovery.listThem")}
                </button>
              ) : null}
            </div>
          )}
          {(search.map.truncated || viewMatches.data?.truncated) && lotZoom && (
            <p className="absolute bottom-20 left-1/2 z-10 -translate-x-1/2 rounded-full bg-nx-page px-3 py-1 text-caption shadow">{t("discovery.capped")}</p>
          )}

          {!phone && focus === "list" && response && (
            <div className="absolute inset-0 z-20 overflow-y-auto bg-nx-page" data-testid="list-focus">
              <Results response={response} rows={search.rows} fmt={fmt} onMore={search.nextOffset != null && !response.result.gated ? () => void search.loadMore() : null}
                loadingMore={search.loadingMore} refreshing={search.refreshing} hiddenUnusual={response.diagnostics.hiddenUnusual ?? 0}
                onShowUnusual={() => search.setIncludeUnusual(true)} onOpen={(row) => openProfile(navigate, row)} hoodName={hoodNameOf} />
            </div>
          )}

          {phone && (
            <PhoneSheet state={sheet} setState={setSheet}
              head={response
                ? <span className="font-semibold">{countLine}</span>
                : <button type="button" onClick={searchView} className="inline-flex items-center gap-2 font-medium" data-testid="search-view">
                    <Search aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{exploreLabel(t, fmt, explorePanel, viewMatches.data, lotZoom)}
                  </button>}>
              {response ? (
                <Results response={response} rows={search.rows} fmt={fmt} onMore={search.nextOffset != null && !response.result.gated ? () => void search.loadMore() : null}
                  loadingMore={search.loadingMore} refreshing={search.refreshing} hiddenUnusual={response.diagnostics.hiddenUnusual ?? 0}
                  onShowUnusual={() => search.setIncludeUnusual(true)} onOpen={(row) => openProfile(navigate, row)} hoodName={hoodNameOf} />
              ) : registry ? (
                <div className="px-4 pb-4">
                  <GoalList topics={topics} counts={registry.recipeCounts ?? {}} fmt={fmt}
                    onPick={(topic) => { search.pickRecipe(topic); setSheet("half"); }} />
                </div>
              ) : null}
            </PhoneSheet>
          )}
        </div>
      </div>
    </AppFrame>
  );
}

// ---------------------------------------------------------------- goals

/** Each goal's plain name and icon (the registry's recipes; presentation only). */
const GOAL_ICON: Record<string, LucideIcon> = {
  vacant_mf_transit: Sprout, teardown: Shovel, room_to_build: Maximize2, underused_commercial_tif: Store,
  fresh_comps: Receipt, undervalued_mf: TrendingDown, adu_2flats: House,
};
type TopicRow = { topic: TopicDef; status: ReturnType<typeof recipeStatus> };

function GoalList({ topics, counts, fmt, onPick }: { topics: TopicRow[]; counts: Record<string, number>; fmt: Intl.NumberFormat; onPick: (t: TopicDef) => void }) {
  const { t } = useTranslation("next");
  const { t: tp } = useTranslation("pages");
  return (
    <ul className="flex flex-col gap-1" aria-label={t("discovery.goals.title")} data-testid="goals">
      {topics.map(({ topic, status }) => {
        const Icon = GOAL_ICON[topic.id] ?? Search;
        return (
          <li key={topic.id}>
            <button type="button" disabled={!status.live} onClick={() => onPick(topic)}
              className="flex w-full items-start gap-3 rounded-xl px-2 py-2 text-left hover:bg-nx-ink/5 disabled:cursor-not-allowed disabled:opacity-50 touch-target">
              <Icon aria-hidden className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={STROKE} />
              <span className="min-w-0 flex-1">
                <span className="block text-caption font-medium">{t(`discovery.goal.${topic.id}`, { defaultValue: tp(`discovery.topic.${topic.id}.label`, { defaultValue: topic.label ?? topic.id }) })}</span>
                <span className="block text-[11px] nx-muted">{t(`discovery.goalHint.${topic.id}`, { defaultValue: "" })}</span>
              </span>
              <span className="shrink-0 text-caption tabular-nums nx-muted">
                {status.live && counts[topic.id] != null ? fmt.format(counts[topic.id]) : t("discovery.goalSoon")}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function GoalCard({ open, onToggle, ...rest }: { open: boolean; onToggle: () => void; topics: TopicRow[]; counts: Record<string, number>; fmt: Intl.NumberFormat; onPick: (t: TopicDef) => void }) {
  const { t } = useTranslation("next");
  return (
    <div className="pointer-events-auto w-[19rem] rounded-2xl bg-nx-page p-2 shadow-[0_4px_16px_rgb(0_0_0/0.14)]">
      <button type="button" aria-expanded={open} onClick={onToggle} className="flex w-full items-center gap-2 rounded-xl px-2 py-1.5 text-caption font-semibold hover:bg-nx-ink/5">
        <Target aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
        <span className="flex-1 text-left">{t("discovery.goals.title")}</span>
        <ChevronDown aria-hidden className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} strokeWidth={STROKE} />
      </button>
      {open && <GoalList {...rest} />}
    </div>
  );
}


function exploreLabel(
  t: (k: string, o?: Record<string, unknown>) => string, fmt: Intl.NumberFormat, panel: PanelState | null,
  data: { total: number } | null, lotZoom: boolean,
): string {
  if (!panel) return lotZoom ? t("discovery.searchTheseLots") : t("discovery.searchAllLots");
  if (!data) return t("discovery.searchTheseLots");
  return t(lotZoom ? "discovery.searchNInView" : "discovery.searchNCity", { count: data.total, n: fmt.format(data.total) });
}

function openProfile(navigate: ReturnType<typeof useNavigate>, row: ResultRow) {
  const q = new URLSearchParams({ pin: row.pin });
  const address = profileAddress(row);
  if (address) q.set("address", address);
  navigate(`/scorecard?${q}`);
}

// ---------------------------------------------------------------- the search box

function SearchBox({ text, setText, onSubmit, onAddress, onPlace, hoods, busy, disabled }: {
  text: string; setText: (s: string) => void; onSubmit: (s?: string) => void; onAddress: (s: AddressSuggestion) => void;
  onPlace: (p: AreaPlace) => void; hoods: Hood[]; busy: boolean; disabled: boolean;
}) {
  const { t } = useTranslation("next");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [found, setFound] = useState<{ q: string; list: AddressSuggestion[] }>({ q: "", list: [] });
  const pin = parsePin(text);
  const isAddress = !pin && /^\d+\s+\S/.test(text.trim());
  useEffect(() => {
    if (!isAddress) return;
    const q = text.trim();
    const timer = window.setTimeout(() => { getAutocomplete(q).then((s) => setFound({ q, list: s.slice(0, 4) })); }, 300);
    return () => window.clearTimeout(timer);
  }, [text, isAddress]);
  const addresses = isAddress ? found.list : [];
  const places = placeSuggestions(text, COMMUNITY_AREAS, hoods);
  type Opt = { key: string; icon: LucideIcon; label: string; hint: string; run: () => void };
  const opts: Opt[] = [
    ...(pin ? [{ key: `p${pin}`, icon: Hash, label: pin, hint: t("discovery.box.pin"), run: () => { setText(pin); onSubmit(pin); } }] : []),
    ...addresses.map((a) => ({ key: `a${a.address}`, icon: MapPin, label: a.address, hint: t("discovery.box.address"), run: () => { setText(a.address); onAddress(a); } })),
    ...places.map((p) => ({ key: p.kind === "hood" ? `h${p.slug}` : `n${p.id}`, icon: MapIcon, label: p.name,
      hint: t(p.kind === "hood" ? "discovery.box.hood" : "discovery.box.area"), run: () => { setText(p.name); onPlace(p); } })),
    ...(text.trim() && !/^\d/.test(text.trim()) ? [{ key: "d", icon: Search, label: text.trim(), hint: t("discovery.box.describe"), run: () => onSubmit(text) }] : []),
  ];
  const show = open && opts.length > 0;
  return (
    <form role="search" className="relative min-w-0 flex-1" onSubmit={(e) => { e.preventDefault(); setOpen(false); if (active >= 0 && opts[active]) opts[active].run(); else onSubmit(); }}>
      <label htmlFor="nx-discovery-q" className="sr-only">{t("discovery.label")}</label>
      <div className="flex h-11 items-center gap-2 rounded-xl bg-nx-ink/5 px-3">
        {busy ? <LoaderCircle aria-hidden className="h-4 w-4 shrink-0 animate-spin nx-muted" strokeWidth={STROKE} /> : <Search aria-hidden className="h-4 w-4 shrink-0 nx-muted" strokeWidth={STROKE} />}
        <input
          id="nx-discovery-q" type="search" value={text} disabled={disabled} autoComplete="off"
          role="combobox" aria-expanded={show} aria-controls="nx-discovery-options" aria-autocomplete="list"
          aria-activedescendant={show && active >= 0 ? `nx-opt-${active}` : undefined}
          onChange={(e) => { setText(e.target.value); setOpen(true); setActive(-1); }}
          onFocus={() => setOpen(true)} onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(opts.length - 1, i + 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(-1, i - 1)); }
            if (e.key === "Escape") setOpen(false);
          }}
          placeholder={t("discovery.placeholder")}
          className="h-11 min-w-0 flex-1 bg-transparent text-body text-nx-ink placeholder:text-nx-ink/[0.64] focus:outline-none"
        />
      </div>
      {show && (
        <ul id="nx-discovery-options" role="listbox" className="absolute inset-x-0 top-12 z-30 overflow-hidden rounded-xl bg-nx-page py-1 shadow-[0_8px_32px_rgb(0_0_0/0.18)]">
          {opts.map((o, i) => {
            const Icon = o.icon;
            return (
              <li key={o.key} id={`nx-opt-${i}`} role="option" aria-selected={i === active}
                onMouseDown={(e) => { e.preventDefault(); setOpen(false); o.run(); }}
                className={`flex cursor-pointer items-center gap-3 px-3 py-2.5 ${i === active ? "bg-nx-ink/5" : "hover:bg-nx-ink/5"}`}>
                <Icon aria-hidden className="h-4 w-4 shrink-0 nx-muted" strokeWidth={STROKE} />
                <span className="min-w-0 flex-1 truncate">{o.label}</span>
                <span className="shrink-0 text-caption nx-muted">{o.hint}</span>
              </li>
            );
          })}
        </ul>
      )}
    </form>
  );
}

// ---------------------------------------------------------------- map overlays

function QuickFilters({ on, onToggle, loading }: { on: ReadonlySet<QuickId>; onToggle: (id: QuickId) => void; loading: boolean }) {
  const { t } = useTranslation("next");
  return (
    <div className="pointer-events-auto -mx-1 flex min-w-0 items-center gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none]" role="group" aria-label={t("discovery.quick.label")} data-testid="quick-filters">
      {QUICK_FILTERS.map((q) => {
        const active = on.has(q.id);
        return (
          <button key={q.id} type="button" aria-pressed={active} onClick={() => onToggle(q.id)}
            className={`shrink-0 rounded-full px-3 py-1.5 text-caption shadow-[0_2px_8px_rgb(0_0_0/0.12)] touch-target ${active ? "bg-nx-ink text-nx-on-ink" : "bg-nx-page hover:bg-nx-block"}`}>
            {t(`discovery.quick.${q.id}`)}
          </button>
        );
      })}
      {loading && <LoaderCircle aria-label={t("discovery.quick.checking")} className="h-4 w-4 shrink-0 animate-spin" strokeWidth={STROKE} />}
    </div>
  );
}

function MeasureKey({ measure, onMeasure, showZoning, onZoning, compact }: {
  measure: MeasureId; onMeasure: (m: MeasureId) => void; showZoning: boolean; onZoning: (b: boolean) => void; compact: boolean;
}) {
  const { t } = useTranslation("next");
  // Open on a desktop, folded on a phone (the page remounts it when that changes: `key`).
  const [open, setOpen] = useState(!compact);
  const steps = measureSteps(measure);
  return (
    <div className={`pointer-events-auto shrink-0 rounded-2xl bg-nx-page text-caption shadow-[0_4px_16px_rgb(0_0_0/0.14)] ${open ? "w-[13.5rem] p-3" : "p-1"}`} data-testid="measure-key">
      <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)}
        aria-label={open ? undefined : t("discovery.measure.colorBy")}
        className={`flex items-center gap-2 font-medium ${open ? "w-full" : "h-9 rounded-xl px-2.5 touch-target"}`}>
        <Palette aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
        {(open || !compact) && <span className="flex-1 text-left">{t("discovery.measure.colorBy")}</span>}
      </button>
      {open && (
        <div className="mt-2 flex flex-col gap-2">
          <label className="sr-only" htmlFor="nx-measure">{t("discovery.measure.colorBy")}</label>
          <select id="nx-measure" value={measure} onChange={(e) => onMeasure(e.target.value as MeasureId)}
            className="h-9 w-full appearance-none rounded-lg bg-nx-ink/5 px-2">
            {MEASURES.map((m) => <option key={m} value={m}>{t(`discovery.measure.${m}.name`)}</option>)}
          </select>
          <ul className="flex flex-col gap-1">
            {steps.map((s) => (
              <li key={s.value} className="flex items-center gap-2">
                <span aria-hidden className="h-3 w-5 shrink-0 rounded-sm" style={{ background: s.color }} />
                <span>{t(`discovery.measure.${s.key}`)}</span>
              </li>
            ))}
            {measure === "zoning" && <li className="nx-muted">{t("discovery.measure.zoning.note")}</li>}
            <li className="flex items-center gap-2">
              <span aria-hidden className="h-3 w-5 shrink-0 rounded-sm border border-nx-ink/20 [background-image:radial-gradient(currentColor_1px,transparent_1.2px)] [background-size:5px_5px] opacity-70" />
              <span>{t("discovery.measure.unknown")}</span>
            </li>
            <li className="flex items-center gap-2">
              <span aria-hidden className="h-3 w-5 shrink-0 rounded-sm border-2 border-nx-ink" />
              <span>{t("discovery.measure.match")}</span>
            </li>
          </ul>
          {measure === "room" && <p className="nx-muted">{t("discovery.measure.room.note")}</p>}
          <label className="mt-1 flex items-center gap-2">
            <input type="checkbox" checked={showZoning} onChange={(e) => onZoning(e.target.checked)} className="h-4 w-4" />
            {t("discovery.measure.showZoning")}
          </label>
          <p className="nx-muted">{t("discovery.measure.zoomHint")}</p>
        </div>
      )}
    </div>
  );
}

function PlaceCard({ place, ring, onRing, onSearchRing, ringActive, onClose }: {
  place: Place; ring: Ring | null; onRing: (miles: number) => void; onSearchRing: () => void; ringActive: boolean; onClose: () => void;
}) {
  const { t, i18n } = useTranslation("next");
  const navigate = useNavigate();
  const mi = (m: number) => new Intl.NumberFormat(numLocale(i18n.language), { maximumFractionDigits: 2 }).format(m);
  return (
    <div className="absolute left-3 top-16 z-10 w-[18rem] max-w-[calc(100%-1.5rem)] rounded-2xl bg-nx-page p-4 text-caption shadow-[0_8px_32px_rgb(0_0_0/0.18)]" data-testid="place-card">
      <button type="button" onClick={onClose} aria-label={t("discovery.map.close")} className="absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-lg hover:bg-nx-ink/5 touch-target">
        <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
      </button>
      <p className="flex items-center gap-2 pr-6 text-body font-semibold"><MapPin aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />{place.label}</p>
      <div className="mt-3 flex flex-col gap-2">
        <button type="button" onClick={() => navigate(`/scorecard?${new URLSearchParams(place.pin ? { pin: place.pin } : { address: place.label })}`)}
          className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-nx-primary font-medium text-nx-primary-fg">
          {t("discovery.place.profile")}<ArrowRight aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
        </button>
        {!ring ? (
          <button type="button" onClick={() => onRing(0.5)} className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-nx-ink/5 hover:bg-nx-ink/10">
            <Circle aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("discovery.place.around")}
          </button>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={t("discovery.place.size")}>
              {RING_MILES.map((m) => (
                <button key={m} type="button" aria-pressed={ring.miles === m} onClick={() => onRing(m)}
                  className={`rounded-full px-3 py-1 touch-target ${ring.miles === m ? "bg-nx-ink text-nx-on-ink" : "bg-nx-ink/5 hover:bg-nx-ink/10"}`}>
                  {t("discovery.place.miles", { mi: mi(m) })}
                </button>
              ))}
              {!RING_MILES.includes(ring.miles as (typeof RING_MILES)[number]) && <span className="nx-muted">{t("discovery.place.miles", { mi: mi(ring.miles) })}</span>}
            </div>
            <p className="nx-muted">{t("discovery.place.drag")}</p>
            {!ringActive && (
              <button type="button" onClick={onSearchRing} className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-nx-ink/5 hover:bg-nx-ink/10" data-testid="search-ring">
                <Search aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("discovery.place.searchRing", { mi: mi(ring.miles) })}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function PhoneSheet({ state, setState, head, children }: {
  state: "peek" | "half" | "full"; setState: (s: "peek" | "half" | "full") => void; head: React.ReactNode; children: React.ReactNode;
}) {
  const { t } = useTranslation("next");
  // The peek clears the preview badge pinned to the bottom of every page (52 px on touch screens, Item 99).
  const height = state === "peek" ? "9.5rem" : state === "half" ? "52%" : "92%";
  const start = useRef<number | null>(null);
  return (
    <section aria-label={t("discovery.sheet.label")} data-testid="phone-sheet" data-state={state}
      className="absolute inset-x-0 bottom-0 z-20 flex flex-col rounded-t-3xl bg-nx-page shadow-[0_-8px_32px_rgb(0_0_0/0.18)] transition-[height] duration-200 motion-reduce:transition-none"
      style={{ height }}>
      <div
        onPointerDown={(e) => { start.current = e.clientY; }}
        onPointerUp={(e) => {
          if (start.current == null) return;
          const dy = e.clientY - start.current;
          start.current = null;
          if (dy < -30) setState(state === "peek" ? "half" : "full");
          else if (dy > 30) setState(state === "full" ? "half" : "peek");
        }}
        className="flex shrink-0 touch-none flex-col items-center gap-2 px-4 pb-2 pt-2">
        <button type="button" aria-label={state === "full" ? t("discovery.sheet.less") : t("discovery.sheet.more")}
          onClick={() => setState(state === "full" ? "peek" : state === "peek" ? "half" : "full")}
          className="grid h-6 w-16 place-items-center touch-target">
          <span aria-hidden className="h-1.5 w-10 rounded-full bg-nx-ink/20" />
        </button>
        <div className="flex w-full items-center justify-between gap-2 text-body">{head}</div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">{state !== "peek" && children}</div>
    </section>
  );
}

// ---------------------------------------------------------------- the list

function Results({ response, rows, fmt, onMore, loadingMore, refreshing, hiddenUnusual, onShowUnusual, onOpen, hoodName }: {
  response: NonNullable<ReturnType<typeof useDiscoverySearch>["applied"]>; rows: ResultRow[]; fmt: Intl.NumberFormat;
  onMore: (() => void) | null; loadingMore: boolean; refreshing: boolean; hiddenUnusual: number; onShowUnusual: () => void;
  onOpen: (row: ResultRow) => void; hoodName: (slug: string | null | undefined) => string | null;
}) {
  const { t } = useTranslation("next");
  return (
    <section aria-labelledby="nx-results" aria-busy={refreshing || undefined} className={`nx-cq px-4 pb-8 pt-4 sm:px-7 ${refreshing ? "opacity-60" : ""}`}>
      <h2 id="nx-results" className="sr-only">{t("discovery.resultsTitle")}</h2>
      {response.result.gated && response.result.total > rows.length && (
        <p className="mb-4 text-caption nx-muted" data-testid="gated">{t("discovery.topOf", { shown: rows.length, total: fmt.format(response.result.total) })}</p>
      )}
      {response.result.total === 0 && <p className="nx-muted">{t("discovery.noneHint")}</p>}
      <ul className="nx-cards grid gap-4" data-testid="next-results">
        {foldComplexes(rows).map(({ row, more }) => (
          <LotCard key={row.pin} row={row} moreInComplex={more} hoodName={hoodName(row.hood)} onOpen={() => onOpen(row)} />
        ))}
      </ul>
      {hiddenUnusual > 0 && (
        <p className="mt-4 text-caption nx-muted">
          {t("discovery.hiddenUnusual", { count: hiddenUnusual, n: fmt.format(hiddenUnusual) })}{" "}
          <button type="button" onClick={onShowUnusual} className="underline underline-offset-2">{t("discovery.show")}</button>
        </p>
      )}
      {onMore && (
        <button type="button" onClick={onMore} disabled={loadingMore} className="mt-6 inline-flex items-center gap-1.5 rounded-xl bg-nx-ink/5 px-4 py-2 hover:bg-nx-ink/10 disabled:opacity-50">
          {loadingMore && <LoaderCircle aria-hidden className="h-4 w-4 animate-spin" strokeWidth={STROKE} />}
          {t("discovery.more")}
        </button>
      )}
    </section>
  );
}

