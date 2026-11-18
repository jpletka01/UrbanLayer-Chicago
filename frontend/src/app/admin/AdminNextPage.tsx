// /admin, redesigned on the site's own pieces (owner's review 2026-11-17: "a clear line of hierarchy", icons over
// text). One section at a time at its own address (/admin/<id>); the sections are the page's own sidebar, built like
// the chat's list (owner's second review: collapsible to a strip, a sheet on a phone), each with a badge counting what
// waits there. Overview comes first: four figures and what needs
// attention, each in a few words with a link to its section. Every endpoint the old dashboard read is still read.
// Admins only: anyone else is sent home when sign-in is required, or told it needs admin access. English only.
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { PanelLeft, X } from "lucide-react";
import { AppFrame, ToolButton } from "../frame/AppFrame";
import { FrameOutline } from "../frame/FrameOutline";
import { useAuthContext } from "../../contexts/AuthContext";
import {
  fetchAdminEngagement, fetchAdminLatency, fetchAdminOverview, fetchAdminTimeseries, fetchBenchmarkResults,
  fetchConversationStats, fetchJudgeResults, fetchRequestLogs, fetchDataHealth, fetchAdminCodeCurrency, fetchAdminCorrections,
  type AdminCodeCurrency, type DataHealth,
} from "../../lib/api";
import type { BenchmarkResults, ConversationStats, JudgeResults, RequestLogEntry } from "../../lib/types";
import { STROKE } from "../icons";
import { ADMIN_SECTIONS, PERIOD_SECTIONS, adminSectionFrom, sectionBadges } from "./adminModel";
import { AdminNav, AdminNavStrip } from "./AdminNav";
import { OverviewSection, QualitySection, RequestsSection, UsageSection, VisitorsSection, type PeriodData } from "./WatchSections";
import { DataHealthSection } from "./DataHealthSection";
import { CorrectionsSection } from "./CorrectionsSection";
import { CodeCurrencySection } from "./CodeCurrencySection";
import { VouchersSection } from "./VouchersSection";

type Period = "today" | "7d" | "30d" | "all";
const PERIODS: { key: Period; label: string }[] = [
  { key: "today", label: "Today" }, { key: "7d", label: "7 days" }, { key: "30d", label: "30 days" }, { key: "all", label: "All time" },
];


export default function AdminNextPage() {
  const { isAuthenticated, authRequired, user, loading } = useAuthContext();
  if (loading) return <FrameOutline />;
  if (authRequired && !isAuthenticated) return <Navigate to="/" replace />;
  if (user?.tier !== "admin") {
    return (
      <AppFrame crumbs={["Admin"]}>
        <p className="px-4 py-24 text-center nx-muted sm:px-7" data-testid="admin-required">Admin access required.</p>
      </AppFrame>
    );
  }
  return <AdminDashboard />;
}

const NAV_KEY = "urbanlayer-next-adminnav";

function AdminDashboard() {
  const params = useParams<{ section?: string }>();
  const current = adminSectionFrom(params.section);
  const label = ADMIN_SECTIONS.find((s) => s.id === current)!.label;

  // The sections beside the panel, like the chat's list: shown on every visit to a wide screen; hiding them lasts for
  // this tab only. A sheet below `lg`.
  const [navShown, setNavShown] = useState(() => { try { return sessionStorage.getItem(NAV_KEY) !== "hidden"; } catch { return true; } });
  const [navSheet, setNavSheet] = useState(false);
  const showNav = (on: boolean) => {
    setNavShown(on);
    try { sessionStorage.setItem(NAV_KEY, on ? "shown" : "hidden"); } catch { /* per-viewer convenience only */ }
  };

  const [period, setPeriod] = useState<Period>("30d");
  const [loadedPeriod, setLoadedPeriod] = useState<{ period: Period; data: PeriodData } | null>(null);
  const periodData = loadedPeriod?.period === period ? loadedPeriod.data : null;
  const [conversations, setConversations] = useState<ConversationStats | null>(null);
  const [requests, setRequests] = useState<RequestLogEntry[]>([]);
  const [requestOffset, setRequestOffset] = useState(0);
  const [benchmark, setBenchmark] = useState<BenchmarkResults | null>(null);
  const [judge, setJudge] = useState<JudgeResults | null>(null);
  // What is waiting on a person (the badges and Overview's attention list), read once and again after a review.
  const [health, setHealth] = useState<DataHealth | null | undefined>(undefined);
  const [code, setCode] = useState<AdminCodeCurrency | null | undefined>(undefined);
  const [openReports, setOpenReports] = useState<number | null | undefined>(undefined);
  const recountReports = useCallback(() => { fetchAdminCorrections("new").then((d) => setOpenReports(d ? d.total : null)); }, []);

  useEffect(() => {
    let live = true;
    Promise.all([fetchAdminOverview(period), fetchAdminTimeseries(period, period === "today" ? "hour" : "day"), fetchAdminLatency(period), fetchAdminEngagement(period)])
      .then(([overview, timeseries, latency, engagement]) => { if (live) setLoadedPeriod({ period, data: { overview, timeseries, latency, engagement } }); });
    return () => { live = false; };
  }, [period]);
  useEffect(() => {
    fetchConversationStats().then(setConversations);
    fetchRequestLogs(50, 0).then((r) => { setRequests(r); setRequestOffset(50); });
    fetchBenchmarkResults().then(setBenchmark);
    fetchJudgeResults().then(setJudge);
    fetchDataHealth().then(setHealth);
    fetchAdminCodeCurrency().then(setCode);
    recountReports();
  }, [recountReports]);
  const loadMore = useCallback(async () => {
    const more = await fetchRequestLogs(50, requestOffset);
    setRequests((prev) => [...prev, ...more]);
    setRequestOffset((prev) => prev + 50);
  }, [requestOffset]);

  const badges = sectionBadges(health, code, openReports);
  const waiting = Object.keys(badges).length > 0;
  const usesPeriod = PERIOD_SECTIONS.has(current);
  const tools = (
    <span className="relative lg:hidden">
      <ToolButton label="Sections" icon={PanelLeft} onClick={() => setNavSheet(true)} testId="admin-nav-show" />
      {waiting && <span aria-hidden className="pointer-events-none absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-nx-pill-red" />}
    </span>
  );
  return (
    <AppFrame
      crumbs={[<Link key="a" to="/admin" className="nx-muted hover:text-nx-ink">Admin</Link>, label]}
      tools={tools}
      secondary={navShown
        ? <AdminNav current={current} badges={badges} onHide={() => showNav(false)} />
        : <AdminNavStrip current={current} badges={badges} onShow={() => showNav(true)} />}
    >
      <Dialog.Root open={navSheet} onOpenChange={setNavSheet}>
        <Dialog.Portal>
          <div className="ui-next">
            <Dialog.Overlay className="fixed inset-0 z-[65] bg-black/30" />
            <Dialog.Content className="fixed inset-y-0 left-0 z-[66] bg-nx-page text-body text-nx-ink shadow-[0_8px_32px_rgb(0_0_0/0.2)] focus:outline-none" data-testid="admin-nav-sheet">
              <Dialog.Title className="sr-only">Admin sections</Dialog.Title>
              <Dialog.Description className="sr-only">Pick a section</Dialog.Description>
              <Dialog.Close className="absolute right-3 top-4 grid h-8 w-8 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon" aria-label="Close sections">
                <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
              </Dialog.Close>
              <AdminNav current={current} badges={badges} onNavigate={() => setNavSheet(false)} />
            </Dialog.Content>
          </div>
        </Dialog.Portal>
      </Dialog.Root>
      <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-4 px-4 py-6 sm:px-8 sm:py-10" data-testid={`admin-${current}`}>
        <h1 className="sr-only">Admin</h1>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-[1.5rem] font-semibold tracking-[-0.02em]">{label}</h2>
          {usesPeriod && (
            <div role="group" aria-label="Period" className="inline-flex rounded-xl bg-nx-ink/5 p-1" data-testid="admin-period">
              {PERIODS.map((p) => (
                <button key={p.key} type="button" aria-pressed={period === p.key} onClick={() => setPeriod(p.key)}
                  className={`rounded-lg px-3 py-1 text-caption touch-target ${period === p.key ? "bg-nx-page font-semibold shadow-sm" : "nx-muted hover:text-nx-ink"}`}>
                  {p.label}
                </button>
              ))}
            </div>
          )}
        </div>
        {usesPeriod && !periodData ? (
          <p className="py-10 text-center nx-muted">Loading…</p>
        ) : (
          <>
            {current === "overview" && <OverviewSection data={periodData!} health={health} code={code} openReports={openReports} />}
            {current === "usage" && <UsageSection data={periodData!} />}
            {current === "visitors" && <VisitorsSection data={periodData!} conversations={conversations} />}
            {current === "quality" && <QualitySection benchmark={benchmark} judge={judge} />}
            {current === "requests" && <RequestsSection rows={requests} onMore={loadMore} hasMore={requests.length >= requestOffset} />}
            {current === "data" && <DataHealthSection />}
            {current === "corrections" && <CorrectionsSection onReviewed={recountReports} />}
            {current === "code" && <CodeCurrencySection />}
            {current === "access" && <VouchersSection />}
          </>
        )}
      </div>
    </AppFrame>
  );
}
