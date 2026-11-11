// The new Property Profile (decision Item 76), behind ?ui=next on today's `/scorecard` URL and today's
// `/api/scorecard` response. The page's one map as the top band with the address over it, then a full-width tab
// bar that turns into one slim sticky bar once scrolled (short address, current tab, Ask / Sources / Export),
// then the tab. With no address it is the Search destination.
// Progressive loading: the page asks `/api/scorecard/first` (Item 82) beside the Overview part (Item 89,
// `useProfileParts`). The first answer (about 1–3 s) draws the screen: map with the lot, address, the district
// sentence, the four tiles in place saying what each waits for. The Overview then fills the same screen (one
// component, same key, so the map stays mounted), and the late parts fill in after it, each named while it waits
// (`PartsStatus`). Ask, Sources and Export read the whole Profile, so they turn on once every part has answered.
// A failed Overview keeps the first screen with Retry.
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import * as Tabs from "@radix-ui/react-tabs";
import { Expand, LoaderCircle, RotateCw, Shrink, TriangleAlert } from "lucide-react";
import type { ProfileLatePart, ScorecardFirst, ScorecardResponse } from "../../lib/api";
import type { ParcelQuery } from "../../lib/types";
import { useSelectedParcel } from "../../contexts/SelectedParcelContext";
import { computeVerdict } from "../../lib/scorecardVerdict";
import { useParcelChat } from "../../lib/useParcelChat";
import { setAddress as setTrackingAddress, track } from "../../lib/tracking";
import { buildFilenameSlug, buildScorecardCSV, downloadCSV } from "../../lib/csvExport";
import { humanizeShoutyCase } from "../../lib/format";
import { AddressInput } from "../../components/AddressInput";
import { NextMap, type LateState, type MapView } from "../map/NextMap";
import { AppFrame, ToolButton } from "../frame/AppFrame";
import { useUiVersion } from "../uiVersionContext";
import { AskDrawer } from "../ask/AskDrawer";
import { AskContext, type AskHandoff } from "../ask/askContext";
import { ICON } from "../icons";
import { OverviewTab, TileCard } from "./OverviewTab";
import { checkingTiles, firstSentence } from "./firstModel";
import { Pill } from "../ui/Blocks";
import { BuildTab } from "./BuildTab";
import { MoneyTab } from "./MoneyTab";
import { NeighborhoodTab } from "./NeighborhoodTab";
import { HistoryTab } from "./HistoryTab";
import { RecordsPanel } from "./RecordsPanel";
import type { BuildingFact } from "./historyModel";
import { PermitPanel } from "./PermitPanel";
import type { AddressPermit, ConstructionProject } from "../../lib/api";
import { sourceState } from "./neighborhoodModel";
import { ProgramPanel } from "./ProgramPanel";
import { RulePanel } from "./RulePanel";
import type { RuleKey } from "./ruleModel";
import { ruleChips } from "./profileModel";
import { incentiveChips, type IncentiveKey } from "./moneyModel";
import type { LateBlockState } from "./moneyModel";
import { SourcesDialog } from "./SourcesDialog";
import { PartsStatus } from "./PartsStatus";
import { useProfileParts, type PartStatus } from "./useProfileParts";

type TabId = "overview" | "build" | "money" | "neighborhood" | "history";

/** Each tab's camera and layers on the one map (map track M1): the Overview looks at the lot among its neighbors and
    recent sales; Build pulls back to the districts around it. Zoning is on in both (owner's review: it reads best
    fully on). The visitor's On / Off choices hold until the tab changes. */
const MAP_VIEWS: Record<TabId, MapView> = {
  overview: { id: "overview", zoom: 17, modes: { zoning: "on", parcels: "on", sales: "on", building: "off", transit: "on", streets: "on" } },
  build: { id: "build", zoom: 15.6, modes: { zoning: "on", parcels: "on", sales: "off", building: "off", transit: "on", streets: "on" } },
  // Money: the nearby market sales around the lot (brief: "market sales within ¼ mile"); zoning off so the sale pins
  // read (Item 99). It opens framed on the lot and its sales (`fit`), which a widened search can find half a mile out.
  money: { id: "money", zoom: 15.2, fit: "sales", modes: { zoning: "off", parcels: "on", sales: "on", building: "off", transit: "off", streets: "on" } },
  // Neighborhood: new construction within half a mile (the brief's map default for this tab, Item 102), framed on the
  // permits; zoning off so the pins read, transit on (getting around).
  neighborhood: { id: "neighborhood", zoom: 14.6, fit: "building", modes: { zoning: "off", parcels: "on", sales: "off", building: "on", transit: "on", streets: "on" } },
  // History: the lot alone (owner, Item 103), zoning on so its district (and a rezoning's) reads.
  history: { id: "history", zoom: 17.2, modes: { zoning: "on", parcels: "on", sales: "off", building: "off", transit: "off", streets: "on" } },
};
const TABS: TabId[] = ["overview", "build", "money", "neighborhood", "history"];

function queryFrom(params: URLSearchParams): ParcelQuery | null {
  const pin = params.get("pin");
  const address = params.get("address");
  const lat = params.get("lat");
  const lon = params.get("lon");
  if (pin) return { pin };
  if (address) return { address };
  if (lat && lon) return { lat: parseFloat(lat), lon: parseFloat(lon) };
  return null;
}

export default function ProfileNextPage() {
  const { t } = useTranslation("next");
  const [params, setParams] = useSearchParams();
  const { adopt } = useSelectedParcel();
  // The URL key this page last resolved to (after canonicalizing to ?pin=), so the replace doesn't refetch.
  const resolvedKey = useRef<string | null>(null);
  const query = queryFrom(params);
  const rawKey = query ? JSON.stringify(query) : null;
  const [activeKey, setActiveKey] = useState<string | null>(rawKey);
  // One per lookup: the screen's key, so the first answer and the parts share one mounted screen and map.
  const [lookupN, setLookupN] = useState(0);
  useEffect(() => {
    if (!rawKey) { setActiveKey(null); return; }
    if (rawKey === resolvedKey.current) return; // the URL was canonicalized to the parcel we already show
    setActiveKey(rawKey);
    setLookupN((n) => n + 1);
  }, [rawKey]);

  const parts = useProfileParts(activeKey, {
    onOverview: (ov) => {
      const result = ov.profile;
      track("scorecard_view", { confidence: result.resolved_confidence, pin_resolved: !!result.resolved_pin });
      if (result.address) setTrackingAddress(result.address);
      if (result.resolved_pin) {
        const next = new URLSearchParams({ pin: result.resolved_pin });
        const shown = result.address ?? params.get("address");
        if (shown) next.set("address", shown);
        resolvedKey.current = JSON.stringify({ pin: result.resolved_pin });
        setParams(next, { replace: true });
      } else {
        resolvedKey.current = activeKey;
      }
    },
    // Chat grounding and the rest of the app read the full Profile: hand it over once every part is in.
    onComplete: (data) => adopt(data),
  });

  useEffect(() => () => setTrackingAddress(null), []);

  const search = (text: string) => {
    if (!text.trim()) return;
    resolvedKey.current = null;
    setParams(new URLSearchParams({ address: text.trim() }));
  };

  // No address in the URL: the Search destination, whatever was shown before.
  const status = rawKey ? parts.status : "idle";
  const { data, first } = parts;
  if ((status === "overview" || status === "complete") && data) {
    return (
      <ProfileScreen
        key={lookupN}
        data={data}
        first={first}
        complete={status === "complete"}
        parts={parts.parts}
        timedOut={parts.timedOut}
        restFailed={false}
        onRetry={parts.retryAll}
        onRetryParts={(names) => names.forEach(parts.retryPart)}
        onSearch={search}
      />
    );
  }
  if ((status === "loading" || status === "failed") && first) {
    return (
      <ProfileScreen
        key={lookupN}
        data={null}
        first={first}
        complete={false}
        parts={{}}
        timedOut={{}}
        restFailed={status === "failed"}
        onRetry={parts.retryAll}
        onRetryParts={() => {}}
        onSearch={search}
      />
    );
  }

  if (status === "loading") {
    return (
      <AppFrame crumbs={[t("profile.crumb"), params.get("address") ?? t("profile.crumbLoading")]}>
        <ProfileSkeleton address={params.get("address")} />
      </AppFrame>
    );
  }

  return (
    <AppFrame crumbs={[t("profile.crumb"), status === "idle" ? t("profile.search.crumb") : (params.get("address") ?? t("profile.crumbLoading"))]}>
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10 sm:px-7 sm:py-16">
        <div className="flex flex-col gap-2">
          <h1 className="text-nx-figure">{t("profile.search.title")}</h1>
          <p className="nx-muted">{status === "notFound" || status === "failed" ? t("profile.search.notFound") : t("profile.search.lead")}</p>
        </div>
        <AddressInput variant="page" onSubmit={search} defaultValue={params.get("address") ?? ""} placeholder={t("profile.search.placeholder")} />
        <p className="text-caption nx-muted">
          {t("profile.search.try")}{" "}
          <button type="button" className="underline underline-offset-2" onClick={() => search("1601 N Milwaukee Ave")}>1601 N Milwaukee Ave</button>
        </p>

      </div>
    </AppFrame>
  );
}

/** Before the first screen (about 1–3 s): the Profile's own outline in its final sizes (the map band, the tab bar,
    the answer's line, the four tiles in their pale stat colors), so the first screen fills this exact shape instead
    of replacing a box (owner, Item 89). The address being looked up, with no time estimate or seconds counter. */
export function ProfileSkeleton({ address }: { address: string | null }) {
  const { t } = useTranslation("next");
  const bar = "block rounded bg-nx-ink/10 motion-safe:animate-pulse";
  return (
    <div data-testid="profile-loading" aria-busy="true">
      <div className="px-4 pt-5 sm:px-7 sm:pt-7">
        <div className="relative h-52 overflow-hidden rounded-2xl bg-nx-block sm:h-64 lg:h-72">
          <span className="absolute left-3 top-3 max-w-[calc(100%-6rem)] truncate rounded-xl bg-nx-page px-3 py-1.5 text-body font-semibold shadow-[0_1px_2px_rgb(0_0_0/0.08)]">
            {address ?? t("profile.crumbLoading")}
          </span>
        </div>
      </div>
      <div aria-hidden className="flex gap-5 px-4 pt-5 sm:px-7">
        <span className={`${bar} my-2 h-4 w-16`} />
        <span className={`${bar} my-2 h-4 w-10`} />
      </div>
      <div className="flex flex-col gap-7 px-4 pt-6 sm:px-7">
        <div className="flex flex-col gap-3">
          <p className="flex items-center gap-2" role="status" aria-live="polite">
            <LoaderCircle aria-hidden className="h-4 w-4 animate-spin" strokeWidth={1.5} />
            {address ? t("profile.loading.at", { address }) : t("profile.loading.plain")}
          </p>
          <span aria-hidden className={`${bar} h-6 w-full max-w-2xl`} />
        </div>
        <ul aria-hidden className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:grid-cols-[repeat(auto-fit,minmax(190px,1fr))] sm:gap-7" data-testid="skeleton-tiles">
          {[0, 1, 2, 3].map((i) => (
            <li key={i} className={`flex flex-col gap-3 rounded-2xl p-4 sm:p-6 ${i % 2 ? "bg-nx-stat-b" : "bg-nx-stat-a"}`}>
              <span className="block h-3 w-12 rounded bg-nx-card-ink/10 motion-safe:animate-pulse" />
              <span className="block h-4 w-24 rounded bg-nx-card-ink/10 motion-safe:animate-pulse" />
              <span className="block h-7 w-20 rounded bg-nx-card-ink/10 motion-safe:animate-pulse" />
              <span className="block h-3 w-28 rounded bg-nx-card-ink/10 motion-safe:animate-pulse" />
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ProfileScreen({
  data,
  first,
  complete,
  parts,
  timedOut,
  restFailed,
  onRetry,
  onRetryParts,
  onSearch,
}: {
  /** The Profile so far (the Overview, then each part as it lands); null while the first screen shows. */
  data: ScorecardResponse | null;
  first: ScorecardFirst | null;
  /** Every part answered: the tools that read the whole Profile (Ask, Sources, Export) turn on. */
  complete: boolean;
  parts: Partial<Record<ProfileLatePart, PartStatus>>;
  timedOut: Partial<Record<ProfileLatePart, string[]>>;
  restFailed: boolean;
  onRetry: () => void;
  onRetryParts: (names: ProfileLatePart[]) => void;
  onSearch: (text: string) => void;
}) {
  const { t, i18n } = useTranslation("next");
  const { t: tp } = useTranslation("pages");
  const previewOn = useUiVersion().version === "next";
  const verdict = useMemo(() => (data ? computeVerdict(data, tp) : null), [data, tp]);
  const [tab, setTab] = useState<TabId>("overview");
  // The right panel: the analyst or a program's page, one at a time (Item 99). Closing slides it out first, so the
  // last panel stays mounted (`shownPanel`) for the slide; `seq` remounts it for a new question or program, and
  // `instant` skips the slide when the panel was already open.
  type Panel = { kind: "ask"; text?: string } | { kind: "program"; program: IncentiveKey } | { kind: "rule"; rule: RuleKey }
    | { kind: "permit"; permit: ConstructionProject | AddressPermit } | { kind: "records"; fact?: BuildingFact };
  // "Show on the map" from a permit's page: the map flies to it and opens its card (Item 102).
  const [mapFocus, setMapFocus] = useState<{ permit: ConstructionProject; seq: number } | null>(null);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [shownPanel, setShownPanel] = useState<{ p: Panel; seq: number; instant: boolean } | null>(null);
  const openPanel = (p: Panel) => {
    setShownPanel((cur) => ({ p, seq: (cur?.seq ?? 0) + 1, instant: !!panel }));
    setPanel(p);
  };
  const closePanel = () => setPanel(null);
  // After a close, the panel leaves once its slide has run (a reopen within that time cancels this).
  useEffect(() => {
    if (panel || !shownPanel) return;
    const id = window.setTimeout(() => setShownPanel(null), 220);
    return () => window.clearTimeout(id);
  }, [panel, shownPanel]);
  const askOpen = panel?.kind === "ask";
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [mapFocused, setMapFocused] = useState(false);
  const mapButtonRef = useRef<HTMLButtonElement | null>(null);
  // Keep focus on the map's toggle across the switch (it moves between the band and the focused view).
  const mapToggled = useRef(false);
  useEffect(() => {
    if (!mapToggled.current) { mapToggled.current = true; return; } // not on first render
    mapButtonRef.current?.focus({ preventScroll: true });
  }, [mapFocused]);
  const askButtonRef = useRef<HTMLSpanElement | null>(null);
  const chat = useParcelChat(complete ? data : null, i18n.language);
  const ready = complete && !!data;
  const ctx = data?.context;
  const rawAddress = data?.address ?? first?.address ?? null;
  const address = rawAddress ? humanizeShoutyCase(rawAddress) : t("profile.unknownAddress");
  const identity = data
    ? (data.resolved_confidence === "authoritative" && !data.nearest_parcel_unverified ? "exact" : "approximate")
    : (first?.resolved_confidence === "authoritative" ? "exact" : "approximate");
  const map = {
    lat: data?.resolved_lat ?? data?.lat ?? first!.resolved_lat,
    lon: data?.resolved_lon ?? data?.lon ?? first!.resolved_lon,
    geometry: data
      ? ((ctx?.property?.parcel_geometry as GeoJSON.Geometry | null) ?? null)
      : (first?.lot?.parcel_geometry ?? null),
    confidence: data?.resolved_confidence ?? first!.resolved_confidence,
    shared: data ? !!ctx?.property?.shared_outline_with : !!first?.lot?.shared_outline_with,
  };

  // The lot's PIN10 marks its outline in the parcel layer; only for an exact match (a nearest parcel may be a neighbor).
  const resolvedPin = data?.resolved_pin ?? first?.resolved_pin ?? null;
  const mapPin10 = identity === "exact" && resolvedPin ? resolvedPin.replace(/\D/g, "").slice(0, 10) : null;
  // Recent sales come with the late `money` part: the map names them while they wait (Item 89's skeleton rule).
  const salesState: LateState = !data ? "loading"
    : parts.money === "waiting" ? "loading"
    : parts.money === "failed" ? "failed"
    : (timedOut.money ?? []).includes("comparables") ? "timedOut"
    : (data.comparables?.sales?.length ?? 0) > 0 ? "ready" : "absent";

  // Where each late part stands for the blocks that read it (Item 89's skeleton rule).
  const lateOf = (p: ProfileLatePart): LateBlockState =>
    !data || parts[p] === "waiting" ? "loading" : parts[p] === "failed" ? "failed" : (timedOut[p]?.length ?? 0) > 0 ? "timedOut" : "ready";
  // Construction nearby comes with the late `activity` part (the Neighborhood tab's map pins, Item 102).
  const buildingBlock = data ? sourceState(data, lateOf("activity"), "construction_within", timedOut.activity ?? []) : "loading";
  const buildingProjects = data?.next_ui?.construction_within?.projects ?? null;
  const buildingState: LateState = buildingBlock === "ready" ? (buildingProjects?.length ? "ready" : "absent") : buildingBlock;

  // The tab bar's height, for what sticks under it (the Neighborhood tab's jump links on a phone).
  const tabBarRef = useRef<HTMLDivElement | null>(null);
  const [tabBarH, setTabBarH] = useState(48);
  useEffect(() => {
    const el = tabBarRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setTabBarH(el.offsetHeight));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // The tab bar is sticky; once it is stuck it also shows the short address (the slim header).
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([e]) => setStuck(!e.isIntersecting && e.boundingClientRect.top < 0));
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // On a phone the tabs scroll sideways (and the slim header's tools take room): keep the open tab in view.
  const tabListRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    tabListRef.current?.querySelector('[data-state="active"]')?.scrollIntoView?.({ inline: "nearest", block: "nearest" });
  }, [tab, stuck]);

  const exportCsv = () => {
    if (!data || !ctx) return;
    const date = new Date().toISOString().slice(0, 10);
    downloadCSV(buildScorecardCSV(ctx, data.address ?? "", data.comparables, data.provenance), `${buildFilenameSlug(data.address || "property")}_profile_${date}.csv`);
  };

  const toolsFor = (where: "top" | "slim") => (
    <>
      <span ref={where === "top" ? askButtonRef : undefined} className="contents">
        <ToolButton label={ready ? t("tools.ask") : `${t("tools.ask")}: ${t("profile.first.toolsLater")}`} icon={ICON.ask} onClick={() => { track("investigate_click", { card_name: "next_ask_open" }); if (askOpen) closePanel(); else openPanel({ kind: "ask" }); }} pressed={askOpen} testId={`tool-ask-${where}`} disabled={!ready} />
      </span>
      <ToolButton label={ready ? t("tools.sources") : `${t("tools.sources")}: ${t("profile.first.toolsLater")}`} icon={ICON.sources} onClick={() => setSourcesOpen(true)} testId={`tool-sources-${where}`} disabled={!ready} />
      <ToolButton label={ready ? t("tools.export") : `${t("tools.export")}: ${t("profile.first.toolsLater")}`} icon={ICON.export} onClick={exportCsv} testId={`tool-export-${where}`} disabled={!ready} />
    </>
  );

  const ruleState = (rule: RuleKey) => {
    const chip = data && verdict ? ruleChips(data, verdict).find((c) => c.key === rule) : undefined;
    return { answer: chip?.answer ?? ("notChecked" as const), blocks: chip?.blocks ?? false };
  };
  const programAnswer = (program: IncentiveKey) =>
    (data ? incentiveChips(data, lateOf("incentives")).find((c) => c.key === program)?.answer : undefined) ?? "notChecked";

  const askHandoff: AskHandoff = {
    ready,
    address,
    open: (text: string) => {
      track("investigate_click", { card_name: "next_term_ask" });
      openPanel({ kind: "ask", text });
    },
    openProgram: (program) => { track("investigate_click", { card_name: `next_program_${program}` }); openPanel({ kind: "program", program }); },
    openRule: (rule) => { track("investigate_click", { card_name: `next_rule_${rule}` }); openPanel({ kind: "rule", rule }); },
    openPermit: (permit) => { track("investigate_click", { card_name: "next_permit" }); openPanel({ kind: "permit", permit }); },
    openRecords: (fact) => { track("investigate_click", { card_name: "next_building_records" }); openPanel({ kind: "records", fact }); },
  };

  const focusAsk = useRef<HTMLElement | null>(null);
  useEffect(() => {
    focusAsk.current = askButtonRef.current?.querySelector("button") ?? null;
  });

  return (
    <AppFrame
      crumbs={[t("profile.crumb"), address]}
      tools={toolsFor("top")}
      drawer={shownPanel && data ? (
        shownPanel.p.kind === "ask" ? (
          ready ? <AskDrawer key={shownPanel.seq} chat={chat} onClose={closePanel} returnFocusRef={focusAsk} tabLabel={t(`profile.tabs.${tab}`)} initialDraft={shownPanel.p.text} closing={!panel} instant={shownPanel.instant} /> : null
        ) : shownPanel.p.kind === "permit" ? (
          <PermitPanel key={shownPanel.seq} permit={shownPanel.p.permit} onClose={closePanel} closing={!panel} instant={shownPanel.instant}
            onShowOnMap={shownPanel.p.permit.distance_mi != null ? () => { const pm = (shownPanel.p as { permit: ConstructionProject }).permit; setMapFocus((f) => ({ permit: pm, seq: (f?.seq ?? 0) + 1 })); window.scrollTo({ top: 0, behavior: "smooth" }); } : undefined} />
        ) : shownPanel.p.kind === "records" ? (
          <RecordsPanel key={shownPanel.seq} data={data} fact={shownPanel.p.fact} onClose={closePanel} closing={!panel} instant={shownPanel.instant} />
        ) : shownPanel.p.kind === "rule" ? (
          <RulePanel key={shownPanel.seq} data={data} rule={shownPanel.p.rule} {...ruleState(shownPanel.p.rule)} onClose={closePanel} closing={!panel} instant={shownPanel.instant} />
        ) : (
          <ProgramPanel key={shownPanel.seq} data={data} program={shownPanel.p.program} answer={programAnswer(shownPanel.p.program)} reports={lateOf("incentives")} onRetry={() => onRetryParts(["incentives"])} onClose={closePanel} closing={!panel} instant={shownPanel.instant} />
        )
      ) : null}
    >
      <AskContext.Provider value={askHandoff}>
      <Tabs.Root value={tab} onValueChange={(v) => setTab(v as TabId)} className="flex flex-col" style={{ ["--nx-tabbar-h" as string]: `${tabBarH}px` }}>
        <div className="px-4 pt-5 sm:px-7 sm:pt-7">
          {/* The page's one map. "Expand map" makes it the focus of the screen; Escape or "Close" returns. */}
          <div
            role={mapFocused ? "dialog" : undefined}
            aria-modal={mapFocused || undefined}
            aria-label={mapFocused ? t("profile.map.focusedLabel", { address }) : undefined}
            onKeyDown={(e) => { if (mapFocused && e.key === "Escape") { e.stopPropagation(); setMapFocused(false); } }}
            className={mapFocused ? "fixed inset-0 z-50 bg-nx-page p-3 sm:p-6" : "relative h-52 sm:h-64 lg:h-72"}
            data-testid="map-band"
            data-focused={mapFocused || undefined}
          >
            <div className="relative h-full overflow-hidden rounded-2xl bg-nx-block">
              <NextMap
                lat={map.lat}
                lon={map.lon}
                geometry={map.geometry}
                approximate={identity !== "exact" || map.shared}
                pin10={mapPin10}
                view={MAP_VIEWS[tab]}
                sales={data?.comparables?.sales ?? null}
                salesState={salesState}
                onRetrySales={() => onRetryParts(["money"])}
                building={buildingProjects}
                buildingState={buildingState}
                onRetryBuilding={() => onRetryParts(["activity"])}
                focusBuilding={mapFocus}
                expanded={mapFocused}
                className="h-full"
              />
              <h1 className="pointer-events-none absolute left-3 top-3 max-w-[calc(100%-6rem)] truncate rounded-xl bg-nx-page px-3 py-1.5 text-body font-semibold shadow-[0_1px_2px_rgb(0_0_0/0.08)]">
                {address}
              </h1>
              {/* Icon only, in the bottom-right corner (owner: no +/- buttons; the key keeps the top-right corner). */}
              <button
                ref={mapButtonRef}
                type="button"
                onClick={() => setMapFocused((f) => !f)}
                aria-expanded={mapFocused}
                aria-label={mapFocused ? t("profile.map.close") : t("profile.map.expand")}
                title={mapFocused ? t("profile.map.close") : t("profile.map.expand")}
                data-testid="map-focus"
                className="absolute bottom-2 right-2 z-10 grid h-8 w-8 place-items-center rounded-lg bg-nx-page shadow-[0_1px_2px_rgb(0_0_0/0.15)] hover:bg-nx-block touch-target"
              >
                {mapFocused
                  ? <Shrink aria-hidden className="h-4 w-4" strokeWidth={1.5} />
                  : <Expand aria-hidden className="h-4 w-4" strokeWidth={1.5} />}
              </button>
            </div>
          </div>
        </div>

        <div ref={sentinelRef} aria-hidden className="h-px" />
        <div ref={tabBarRef} className={`sticky top-0 z-30 flex items-center gap-4 bg-nx-page px-4 sm:px-7 ${stuck ? "border-b border-nx-ink/10 py-2" : "pt-5"}`} data-testid="tab-bar" data-stuck={stuck || undefined}>
          {stuck && <span className="hidden max-w-[16rem] truncate font-semibold md:block">{address}</span>}
          <Tabs.List ref={tabListRef} aria-label={t("profile.tabsLabel")} className="flex min-w-0 flex-1 gap-5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {TABS.map((id) => (
              <Tabs.Trigger
                key={id}
                value={id}
                disabled={!data && id !== "overview"}
                className="whitespace-nowrap py-2 disabled:opacity-40 text-nx-ink/[0.64] hover:text-nx-ink data-[state=active]:font-semibold data-[state=active]:text-nx-ink data-[state=active]:shadow-[inset_0_-2px_0_rgb(var(--nx-ink))] touch-target"
              >
                {t(`profile.tabs.${id}`)}
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          {stuck && <div className="flex shrink-0 items-center gap-1">{toolsFor("slim")}</div>}
        </div>

        <div className="px-4 pb-10 pt-6 sm:px-7">
          <Tabs.Content value="overview" className="focus:outline-none">
            {data && verdict ? (
              <OverviewTab
                data={data}
                verdict={verdict}
                identity={identity}
                checkingCityLists={parts.history === "waiting"}
                buildingPending={parts.building === "waiting"}
                onOpenTab={(id) => { setTab(id); window.scrollTo({ top: 0 }); }}
              />
            ) : first ? (
              <FirstOverview first={first} identity={identity} restFailed={restFailed} onRetry={onRetry} />
            ) : null}
          </Tabs.Content>
          {data && verdict && (
            <Tabs.Content value="build" className="focus:outline-none">
              <BuildTab data={data} verdict={verdict} buildingPending={parts.building === "waiting"} />
            </Tabs.Content>
          )}

          {data && verdict && (
            <Tabs.Content value="money" className="focus:outline-none">
              <MoneyTab
                data={data}
                late={{ money: lateOf("money"), incentives: lateOf("incentives"), neighborhood: lateOf("neighborhood") }}
                onRetry={(p) => onRetryParts([p])}
              />
            </Tabs.Content>
          )}

          {data && verdict && (
            <Tabs.Content value="neighborhood" className="focus:outline-none">
              <NeighborhoodTab
                data={data}
                late={{ neighborhood: lateOf("neighborhood"), activity: lateOf("activity") }}
                timedOutActivity={timedOut.activity ?? []}
                onRetry={(p) => onRetryParts([p])}
              />
            </Tabs.Content>
          )}

          {data && verdict && (
            <Tabs.Content value="history" className="focus:outline-none">
              <HistoryTab
                data={data}
                late={lateOf("history")}
                timedOutHistory={timedOut.history ?? []}
                onRetry={() => onRetryParts(["history"])}
              />
            </Tabs.Content>
          )}

          {data && <PartsStatus parts={parts} timedOut={timedOut} onRetry={onRetryParts} />}

        </div>

        {/* "Look up another address", pinned to the bottom of the screen on every tab (owner, Item 89). It leaves room
            for the preview badge below it; the expanded map covers it; suggestions open upward. */}
        <div
          className={`sticky bottom-0 z-20 border-t border-nx-ink/10 bg-nx-page/95 px-4 pt-3 backdrop-blur sm:px-7 ${previewOn ? "pb-[calc(env(safe-area-inset-bottom)+4.25rem)]" : "pb-[calc(env(safe-area-inset-bottom)+0.75rem)]"}`}
          data-testid="search-again"
        >
          <div className="max-w-xl">
            <AddressInput variant="page" size="sm" dropUp onSubmit={onSearch} placeholder={t("profile.another")} label={t("profile.another")} />
          </div>
        </div>
      </Tabs.Root>
      </AskContext.Provider>
      {ready && <SourcesDialog data={data!} open={sourcesOpen} onOpenChange={setSourcesOpen} />}
    </AppFrame>
  );
}

/** The Overview while the full response loads (Item 82): the district sentence in the answer's place, the four
    tiles in their places saying what each waits for, and one line naming what is still on its way. No seconds
    counter. Until Phase 4 the rest arrives as one response, so the line names its contents, not its progress. */
export function FirstOverview({
  first,
  identity,
  restFailed,
  onRetry,
}: {
  first: ScorecardFirst;
  identity: "exact" | "approximate";
  restFailed: boolean;
  onRetry: () => void;
}) {
  const { t, i18n } = useTranslation("next");
  return (
    <div className="flex flex-col gap-7" data-testid="profile-first">
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
        <p className="text-nx-answer" data-testid="first-sentence">{firstSentence(first, t, i18n.language)}</p>
        {identity === "approximate" && <Pill tone="yellow" icon={TriangleAlert}>{t("profile.approximate")}</Pill>}
      </div>
      <ul
        className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:grid-cols-[repeat(auto-fit,minmax(190px,1fr))] sm:gap-7"
        data-testid="overview-tiles"
        aria-busy={!restFailed}
      >
        {checkingTiles(t).map((tile, i) => <TileCard key={tile.key} tile={tile} alt={i % 2 === 1} onOpenTab={() => {}} />)}
      </ul>
      {restFailed ? (
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1" role="alert" data-testid="first-rest-failed">
          <TriangleAlert aria-hidden className="h-4 w-4 shrink-0" strokeWidth={1.5} />
          {t("profile.first.restFailed")}
          <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 underline underline-offset-2 touch-target">
            <RotateCw aria-hidden className="h-3.5 w-3.5" strokeWidth={1.5} />
            {t("profile.first.retry")}
          </button>
        </p>
      ) : (
        <p className="flex items-start gap-2 text-caption nx-muted" role="status" data-testid="still-checking">
          <LoaderCircle aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin" strokeWidth={1.5} />
          {t("profile.first.stillChecking")}
        </p>
      )}
    </div>
  );
}
