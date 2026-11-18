// /admin, redesigned on the site's own pieces (owner's review 2026-11-17: "a clear line of hierarchy", icons over
// text). Like Settings (design B): the sections on the left, one at a time at its own address (/admin/<id>); on a
// phone /admin is the list and each section opens on its own. Overview comes first: four figures and what needs
// attention, each in a few words with a link to its section. Every endpoint the old dashboard read is still read.
// Admins only: anyone else is sent home when sign-in is required, or told it needs admin access. English only.
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import {
  Activity, BadgeCheck, ChevronLeft, ChevronRight, HeartPulse, LayoutDashboard, ListTree, PencilLine, Scale, Ticket, Users,
  type LucideIcon,
} from "lucide-react";
import { AppFrame } from "../frame/AppFrame";
import { FrameOutline } from "../frame/FrameOutline";
import { useAuthContext } from "../../contexts/AuthContext";
import {
  fetchAdminEngagement, fetchAdminLatency, fetchAdminOverview, fetchAdminTimeseries, fetchBenchmarkResults,
  fetchConversationStats, fetchJudgeResults, fetchRequestLogs,
} from "../../lib/api";
import type { BenchmarkResults, ConversationStats, JudgeResults, RequestLogEntry } from "../../lib/types";
import { STROKE } from "../icons";
import { ADMIN_SECTIONS, PERIOD_SECTIONS, adminSectionFrom, type AdminSectionId } from "./adminModel";
import { OverviewSection, QualitySection, RequestsSection, UsageSection, VisitorsSection, type PeriodData } from "./WatchSections";
import { DataHealthSection } from "./DataHealthSection";
import { CorrectionsSection } from "./CorrectionsSection";
import { CodeCurrencySection } from "./CodeCurrencySection";
import { VouchersSection } from "./VouchersSection";

type Period = "today" | "7d" | "30d" | "all";
const PERIODS: { key: Period; label: string }[] = [
  { key: "today", label: "Today" }, { key: "7d", label: "7 days" }, { key: "30d", label: "30 days" }, { key: "all", label: "All time" },
];

const SECTION_ICON: Record<AdminSectionId, LucideIcon> = {
  overview: LayoutDashboard, usage: Activity, visitors: Users, quality: BadgeCheck, requests: ListTree,
  data: HeartPulse, corrections: PencilLine, code: Scale, access: Ticket,
};

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

function AdminDashboard() {
  const params = useParams<{ section?: string }>();
  const current = adminSectionFrom(params.section);
  const onList = !params.section; // a phone shows the list at /admin
  const label = ADMIN_SECTIONS.find((s) => s.id === current)!.label;

  const [period, setPeriod] = useState<Period>("30d");
  const [loadedPeriod, setLoadedPeriod] = useState<{ period: Period; data: PeriodData } | null>(null);
  const periodData = loadedPeriod?.period === period ? loadedPeriod.data : null;
  const [conversations, setConversations] = useState<ConversationStats | null>(null);
  const [requests, setRequests] = useState<RequestLogEntry[]>([]);
  const [requestOffset, setRequestOffset] = useState(0);
  const [benchmark, setBenchmark] = useState<BenchmarkResults | null>(null);
  const [judge, setJudge] = useState<JudgeResults | null>(null);

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
  }, []);
  const loadMore = useCallback(async () => {
    const more = await fetchRequestLogs(50, requestOffset);
    setRequests((prev) => [...prev, ...more]);
    setRequestOffset((prev) => prev + 50);
  }, [requestOffset]);

  const usesPeriod = PERIOD_SECTIONS.has(current);
  return (
    <AppFrame crumbs={onList ? ["Admin"] : [<Link key="a" to="/admin" className="nx-muted hover:text-nx-ink">Admin</Link>, label]}>
      <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-6 sm:px-8 sm:py-10" data-testid="admin">
        <h1 className={`text-[1.875rem] font-semibold tracking-[-0.02em] ${onList ? "" : "hidden md:block"}`}>Admin</h1>

        <div className="flex flex-wrap items-start gap-8">
          <nav aria-label="Admin sections" className="hidden w-[200px] shrink-0 flex-col gap-0.5 md:flex" data-testid="admin-nav">
            {ADMIN_SECTIONS.map((s, i) => (
              <div key={s.id}>
                {i > 0 && ADMIN_SECTIONS[i - 1].group !== s.group && <div className="my-2 border-t border-nx-ink/10" />}
                <SectionLink id={s.id} label={s.label} current={s.id === current} />
              </div>
            ))}
          </nav>

          {onList && (
            <nav aria-label="All admin sections" className="w-full overflow-hidden rounded-2xl bg-nx-block md:hidden" data-testid="admin-phone-list">
              {ADMIN_SECTIONS.map((s, i) => {
                const Icon = SECTION_ICON[s.id];
                return (
                  <Link key={s.id} to={`/admin/${s.id}`} className={`flex min-h-[52px] items-center gap-3 px-4 ${i ? "border-t border-nx-ink/10" : ""}`}>
                    <Icon aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />
                    <span className="flex-1">{s.label}</span>
                    <ChevronRight aria-hidden className="h-4 w-4 nx-muted" strokeWidth={STROKE} />
                  </Link>
                );
              })}
            </nav>
          )}

          <div className={`min-w-0 flex-[999_1_420px] flex-col gap-4 ${onList ? "hidden md:flex" : "flex"}`} data-testid={`admin-${current}`}>
            <Link to="/admin" className="inline-flex items-center gap-1 self-start text-caption font-medium nx-muted md:hidden touch-target">
              <ChevronLeft aria-hidden className="h-4 w-4" strokeWidth={STROKE} />Admin
            </Link>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-[1.5rem] font-semibold tracking-[-0.02em]">{label}</h2>
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
                {current === "overview" && <OverviewSection data={periodData!} />}
                {current === "usage" && <UsageSection data={periodData!} />}
                {current === "visitors" && <VisitorsSection data={periodData!} conversations={conversations} />}
                {current === "quality" && <QualitySection benchmark={benchmark} judge={judge} />}
                {current === "requests" && <RequestsSection rows={requests} onMore={loadMore} hasMore={requests.length >= requestOffset} />}
                {current === "data" && <DataHealthSection />}
                {current === "corrections" && <CorrectionsSection />}
                {current === "code" && <CodeCurrencySection />}
                {current === "access" && <VouchersSection />}
              </>
            )}
          </div>
        </div>
      </div>
    </AppFrame>
  );
}

function SectionLink({ id, label, current }: { id: AdminSectionId; label: string; current: boolean }) {
  const Icon = SECTION_ICON[id];
  return (
    <Link to={`/admin/${id}`} aria-current={current ? "page" : undefined}
      className={`flex h-9 items-center gap-2.5 rounded-xl px-2.5 ${current ? "bg-nx-ink/5 font-semibold" : "hover:bg-nx-ink/5"}`}>
      <Icon aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />{label}
    </Link>
  );
}
