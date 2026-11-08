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
import { ParcelMap } from "../../components/scorecard/ParcelMap";
import { AppFrame, ToolButton } from "../frame/AppFrame";
import { AskDrawer } from "../ask/AskDrawer";
import { ICON } from "../icons";
import { OverviewTab, TileCard } from "./OverviewTab";
import { checkingTiles, firstSentence } from "./firstModel";
import { Pill } from "../ui/Blocks";
import { BuildTab } from "./BuildTab";
import { SourcesDialog } from "./SourcesDialog";
import { PartsStatus } from "./PartsStatus";
import { useProfileParts, type PartStatus } from "./useProfileParts";

type TabId = "overview" | "build";
const TABS: TabId[] = ["overview", "build"];

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

  return (
    <AppFrame crumbs={[t("profile.crumb"), status === "idle" ? t("profile.search.crumb") : (params.get("address") ?? t("profile.crumbLoading"))]}>
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10 sm:px-7 sm:py-16">
        {status === "loading" ? (
          <LoadingState address={params.get("address")} />
        ) : (
          <>
            <div className="flex flex-col gap-2">
              <h1 className="text-nx-figure">{t("profile.search.title")}</h1>
              <p className="nx-muted">{status === "notFound" || status === "failed" ? t("profile.search.notFound") : t("profile.search.lead")}</p>
            </div>
            <AddressInput variant="page" onSubmit={search} defaultValue={params.get("address") ?? ""} placeholder={t("profile.search.placeholder")} />
            <p className="text-caption nx-muted">
              {t("profile.search.try")}{" "}
              <button type="button" className="underline underline-offset-2" onClick={() => search("1601 N Milwaukee Ave")}>1601 N Milwaukee Ave</button>
            </p>
          </>
        )}
      </div>
    </AppFrame>
  );
}

/** Before the first screen (about 1–3 s): the address being looked up. No time estimate and no seconds counter
    (Items 81, 89: the Overview now follows within seconds, so the old "15 to 40 seconds" line was wrong). */
function LoadingState({ address }: { address: string | null }) {
  const { t } = useTranslation("next");
  return (
    <div className="flex flex-col gap-4" role="status" aria-live="polite" data-testid="profile-loading">
      <div className="h-48 animate-pulse rounded-2xl bg-nx-block" />
      <p className="flex items-center gap-2">
        <LoaderCircle aria-hidden className="h-4 w-4 animate-spin" strokeWidth={1.5} />
        {address ? t("profile.loading.at", { address }) : t("profile.loading.plain")}
      </p>
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
  const verdict = useMemo(() => (data ? computeVerdict(data, tp) : null), [data, tp]);
  const [tab, setTab] = useState<TabId>("overview");
  const [askOpen, setAskOpen] = useState(false);
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
  // The map's identity stays the first answer's for this lookup, so the full response doesn't remount it.
  const mapKey = first ? (first.resolved_pin ?? first.address) : (data?.resolved_pin ?? data?.address ?? null);
  const map = {
    lat: data?.resolved_lat ?? data?.lat ?? first!.resolved_lat,
    lon: data?.resolved_lon ?? data?.lon ?? first!.resolved_lon,
    geometry: data
      ? ((ctx?.property?.parcel_geometry as GeoJSON.Geometry | null) ?? null)
      : (first?.lot?.parcel_geometry ?? null),
    confidence: data?.resolved_confidence ?? first!.resolved_confidence,
    shared: data ? !!ctx?.property?.shared_outline_with : !!first?.lot?.shared_outline_with,
  };

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

  const exportCsv = () => {
    if (!data || !ctx) return;
    const date = new Date().toISOString().slice(0, 10);
    downloadCSV(buildScorecardCSV(ctx, data.address ?? "", data.comparables, data.provenance), `${buildFilenameSlug(data.address || "property")}_profile_${date}.csv`);
  };

  const toolsFor = (where: "top" | "slim") => (
    <>
      <span ref={where === "top" ? askButtonRef : undefined} className="contents">
        <ToolButton label={ready ? t("tools.ask") : `${t("tools.ask")}: ${t("profile.first.toolsLater")}`} icon={ICON.ask} onClick={() => { track("investigate_click", { card_name: "next_ask_open" }); setAskOpen((o) => !o); }} pressed={askOpen} testId={`tool-ask-${where}`} disabled={!ready} />
      </span>
      <ToolButton label={ready ? t("tools.sources") : `${t("tools.sources")}: ${t("profile.first.toolsLater")}`} icon={ICON.sources} onClick={() => setSourcesOpen(true)} testId={`tool-sources-${where}`} disabled={!ready} />
      <ToolButton label={ready ? t("tools.export") : `${t("tools.export")}: ${t("profile.first.toolsLater")}`} icon={ICON.export} onClick={exportCsv} testId={`tool-export-${where}`} disabled={!ready} />
    </>
  );

  const focusAsk = useRef<HTMLElement | null>(null);
  useEffect(() => {
    focusAsk.current = askButtonRef.current?.querySelector("button") ?? null;
  });

  return (
    <AppFrame
      crumbs={[t("profile.crumb"), address]}
      tools={toolsFor("top")}
      drawer={askOpen && ready ? (
        <AskDrawer chat={chat} onClose={() => setAskOpen(false)} returnFocusRef={focusAsk} tabLabel={t(`profile.tabs.${tab}`)} />
      ) : null}
    >
      <Tabs.Root value={tab} onValueChange={(v) => setTab(v as TabId)} className="flex flex-col">
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
              <ParcelMap
                variant="place"
                look="next"
                lat={map.lat}
                lon={map.lon}
                parcelGeometry={map.geometry}
                profileKey={mapKey}
                parcelConfidence={map.confidence}
                outlineShared={map.shared}
                comps={data?.comparables?.sales}
                showTransit
                className="h-full"
              />
              <h1 className="pointer-events-none absolute left-3 top-3 max-w-[calc(100%-6rem)] truncate rounded-xl bg-nx-page px-3 py-1.5 text-body font-semibold shadow-[0_1px_2px_rgb(0_0_0/0.08)]">
                {address}
              </h1>
              {/* Icon only, bottom-right beside Mapbox's zoom buttons with a gap (owner's call; the key keeps the top-right corner). */}
              <button
                ref={mapButtonRef}
                type="button"
                onClick={() => setMapFocused((f) => !f)}
                aria-expanded={mapFocused}
                aria-label={mapFocused ? t("profile.map.close") : t("profile.map.expand")}
                title={mapFocused ? t("profile.map.close") : t("profile.map.expand")}
                data-testid="map-focus"
                className="absolute bottom-2.5 right-12 z-10 grid h-8 w-8 place-items-center rounded-lg bg-nx-page shadow-[0_1px_2px_rgb(0_0_0/0.15)] hover:bg-nx-block touch-target"
              >
                {mapFocused
                  ? <Shrink aria-hidden className="h-4 w-4" strokeWidth={1.5} />
                  : <Expand aria-hidden className="h-4 w-4" strokeWidth={1.5} />}
              </button>
            </div>
          </div>
        </div>

        <div ref={sentinelRef} aria-hidden className="h-px" />
        <div className={`sticky top-0 z-30 flex items-center gap-4 bg-nx-page px-4 sm:px-7 ${stuck ? "border-b border-nx-ink/10 py-2" : "pt-5"}`} data-testid="tab-bar" data-stuck={stuck || undefined}>
          {stuck && <span className="hidden max-w-[16rem] truncate font-semibold md:block">{address}</span>}
          <Tabs.List aria-label={t("profile.tabsLabel")} className="flex min-w-0 flex-1 gap-5 overflow-x-auto">
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

        <div className="px-4 pb-24 pt-6 sm:px-7">
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

          {data && <PartsStatus parts={parts} timedOut={timedOut} onRetry={onRetryParts} />}

          <div className="mt-12 max-w-xl border-t border-nx-ink/10 pt-6">
            <p className="mb-2 text-caption nx-muted">{t("profile.another")}</p>
            <AddressInput variant="page" size="sm" onSubmit={onSearch} placeholder={t("profile.search.placeholder")} />
          </div>
        </div>
      </Tabs.Root>
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
