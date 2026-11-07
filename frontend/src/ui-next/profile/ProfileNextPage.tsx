// The new Property Profile (decision Item 76), behind ?ui=next on today's `/scorecard` URL and today's
// `/api/scorecard` response. The page's one map as the top band with the address over it, then a full-width tab
// bar that turns into one slim sticky bar once scrolled (short address, current tab, Ask / Sources / Export),
// then the tab. With no address it is the Search destination.
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import * as Tabs from "@radix-ui/react-tabs";
import { LoaderCircle } from "lucide-react";
import type { ScorecardResponse } from "../../lib/api";
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
import { OverviewTab } from "./OverviewTab";
import { BuildTab } from "./BuildTab";
import { SourcesDialog } from "./SourcesDialog";

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
  const { select } = useSelectedParcel();
  const [data, setData] = useState<ScorecardResponse | null>(null);
  const [fetchStatus, setStatus] = useState<"idle" | "loading" | "ready" | "notFound">("idle");
  const resolvedKey = useRef<string | null>(null);

  const query = queryFrom(params);
  const queryKey = query ? JSON.stringify(query) : null;
  const pending = useRef<string | null>(null);

  useEffect(() => {
    if (!queryKey) return;
    // The URL was canonicalized to the parcel we already show: nothing to fetch.
    if (queryKey === resolvedKey.current) return;
    pending.current = queryKey;
    setStatus("loading");
    select(JSON.parse(queryKey) as ParcelQuery).then((result) => {
      if (pending.current !== queryKey) return; // a newer lookup superseded this one
      if (!result) { setStatus("notFound"); setData(null); return; }
      setData(result);
      setStatus("ready");
      track("scorecard_view", { confidence: result.resolved_confidence, pin_resolved: !!result.resolved_pin });
      if (result.address) setTrackingAddress(result.address);
      if (result.resolved_pin) {
        const next = new URLSearchParams({ pin: result.resolved_pin });
        const shown = result.address ?? params.get("address");
        if (shown) next.set("address", shown);
        resolvedKey.current = JSON.stringify({ pin: result.resolved_pin });
        setParams(next, { replace: true });
      } else {
        resolvedKey.current = queryKey;
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryKey]);

  useEffect(() => () => setTrackingAddress(null), []);

  const search = (text: string) => {
    if (!text.trim()) return;
    resolvedKey.current = null;
    setParams(new URLSearchParams({ address: text.trim() }));
  };

  // No address in the URL: the Search destination, whatever was shown before.
  const status = queryKey ? fetchStatus : "idle";
  if (status === "ready" && data) return <ProfileLoaded key={data.resolved_pin ?? data.address ?? "parcel"} data={data} onSearch={search} />;

  return (
    <AppFrame crumbs={[t("profile.crumb"), status === "idle" ? t("profile.search.crumb") : (params.get("address") ?? t("profile.crumbLoading"))]}>
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10 sm:px-7 sm:py-16">
        {status === "loading" ? (
          <LoadingState address={params.get("address")} />
        ) : (
          <>
            <div className="flex flex-col gap-2">
              <h1 className="text-nx-figure">{t("profile.search.title")}</h1>
              <p className="nx-muted">{status === "notFound" ? t("profile.search.notFound") : t("profile.search.lead")}</p>
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

function LoadingState({ address }: { address: string | null }) {
  const { t } = useTranslation("next");
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <div className="flex flex-col gap-4" role="status" aria-live="polite" data-testid="profile-loading">
      <div className="h-48 animate-pulse rounded-2xl bg-nx-block" />
      <p className="flex items-center gap-2">
        <LoaderCircle aria-hidden className="h-4 w-4 animate-spin" strokeWidth={1.5} />
        {address ? t("profile.loading.at", { address }) : t("profile.loading.plain")}
      </p>
      <p className="text-caption nx-muted">{t("profile.loading.firstLookup", { seconds })}</p>
    </div>
  );
}

function ProfileLoaded({ data, onSearch }: { data: ScorecardResponse; onSearch: (text: string) => void }) {
  const { t, i18n } = useTranslation("next");
  const { t: tp } = useTranslation("pages");
  const verdict = useMemo(() => computeVerdict(data, tp), [data, tp]);
  const [tab, setTab] = useState<TabId>("overview");
  const [askOpen, setAskOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const askButtonRef = useRef<HTMLSpanElement | null>(null);
  const chat = useParcelChat(data, i18n.language);
  const ctx = data.context;
  const address = data.address ? humanizeShoutyCase(data.address) : t("profile.unknownAddress");
  const identity = data.resolved_confidence === "authoritative" && !data.nearest_parcel_unverified ? "exact" : "approximate";

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
    const date = new Date().toISOString().slice(0, 10);
    downloadCSV(buildScorecardCSV(ctx, data.address ?? "", data.comparables, data.provenance), `${buildFilenameSlug(data.address || "property")}_profile_${date}.csv`);
  };

  const toolsFor = (where: "top" | "slim") => (
    <>
      <span ref={where === "top" ? askButtonRef : undefined} className="contents">
        <ToolButton label={t("tools.ask")} icon={ICON.ask} onClick={() => { track("investigate_click", { card_name: "next_ask_open" }); setAskOpen((o) => !o); }} pressed={askOpen} testId={`tool-ask-${where}`} />
      </span>
      <ToolButton label={t("tools.sources")} icon={ICON.sources} onClick={() => setSourcesOpen(true)} testId={`tool-sources-${where}`} />
      <ToolButton label={t("tools.export")} icon={ICON.export} onClick={exportCsv} testId={`tool-export-${where}`} />
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
      drawer={askOpen ? (
        <AskDrawer chat={chat} onClose={() => setAskOpen(false)} returnFocusRef={focusAsk} tabLabel={t(`profile.tabs.${tab}`)} />
      ) : null}
    >
      <Tabs.Root value={tab} onValueChange={(v) => setTab(v as TabId)} className="flex flex-col">
        <div className="px-4 pt-5 sm:px-7 sm:pt-7">
          <div className="relative h-52 overflow-hidden rounded-2xl bg-nx-block sm:h-64 lg:h-72" data-testid="map-band">
            <ParcelMap
              variant="place"
              look="next"
              lat={data.resolved_lat ?? data.lat}
              lon={data.resolved_lon ?? data.lon}
              parcelGeometry={(ctx.property?.parcel_geometry as GeoJSON.Geometry | null) ?? null}
              profileKey={data.resolved_pin ?? data.address}
              parcelConfidence={data.resolved_confidence}
              outlineShared={!!ctx.property?.shared_outline_with}
              comps={data.comparables?.sales}
              showTransit
              className="h-full"
            />
            <h1 className="pointer-events-none absolute bottom-3 left-3 max-w-[calc(100%-1.5rem)] truncate rounded-xl bg-nx-page px-3 py-1.5 text-body font-semibold shadow-[0_1px_2px_rgb(0_0_0/0.08)]">
              {address}
            </h1>
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
                className="whitespace-nowrap py-2 text-nx-ink/[0.64] hover:text-nx-ink data-[state=active]:font-semibold data-[state=active]:text-nx-ink data-[state=active]:shadow-[inset_0_-2px_0_rgb(var(--nx-ink))] touch-target"
              >
                {t(`profile.tabs.${id}`)}
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          {stuck && <div className="flex shrink-0 items-center gap-1">{toolsFor("slim")}</div>}
        </div>

        <div className="px-4 pb-24 pt-6 sm:px-7">
          <Tabs.Content value="overview" className="focus:outline-none">
            <OverviewTab data={data} verdict={verdict} identity={identity} onOpenTab={(id) => { setTab(id); window.scrollTo({ top: 0 }); }} />
          </Tabs.Content>
          <Tabs.Content value="build" className="focus:outline-none">
            <BuildTab data={data} verdict={verdict} />
          </Tabs.Content>

          <div className="mt-12 max-w-xl border-t border-nx-ink/10 pt-6">
            <p className="mb-2 text-caption nx-muted">{t("profile.another")}</p>
            <AddressInput variant="page" size="sm" onSubmit={onSearch} placeholder={t("profile.search.placeholder")} />
          </div>
        </div>
      </Tabs.Root>
      <SourcesDialog data={data} open={sourcesOpen} onOpenChange={setSourcesOpen} />
    </AppFrame>
  );
}
