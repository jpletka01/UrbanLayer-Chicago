// The sections an admin reads (Overview, Usage and cost, Visitors, Answer quality, Requests), on the site's own
// blocks: one row of stat tiles with an icon each (the figure first), then blocks of charts. Charts are the existing
// admin charts; empty ones say so in a line instead of drawing an empty frame.
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity, ChartLine, ChartPie, ChevronRight, CircleDollarSign, Clock, Coins, Gauge, MessagesSquare, MousePointerClick,
  HeartPulse, PencilLine, Repeat, Route, Scale, Target, Timer, UserPlus, Users,
} from "lucide-react";
import {
  fetchAdminCodeCurrency, fetchAdminCorrections, fetchDataHealth,
  type AdminCodeCurrency, type DataHealth,
} from "../../lib/api";
import type {
  AdminOverview, BenchmarkResults, ConversationStats, EngagementMetrics, JudgeResults, LatencyPercentiles, RequestLogEntry,
  TimeseriesBucket,
} from "../../lib/types";
import type { PieSlice } from "../../lib/analytics";
import { STROKE } from "../icons";
import { Block, Pill, StatTile } from "../ui/Blocks";
import { ADMIN_SECTIONS, codeAttention, correctionsAttention, dataAttention, type Attention } from "./adminModel";
import { Empty, IconBadge, Tiles } from "./adminUi";
import { TimeSeriesChart } from "./TimeSeriesChart";
import { LatencyTable } from "./LatencyTable";
import { RequestsTable } from "./RequestsTable";
import { BenchmarkSection } from "./BenchmarkSection";
import { JudgeSection } from "./JudgeSection";
import { PieChart } from "./PieChart";
import { BarChart } from "./HBarChart";

const MODEL_COLORS: Record<string, string> = { "claude-sonnet-4-6": "#fe9179", "claude-haiku-4-5-20251001": "#72b0ab" };
const PHASE_COLORS: Record<string, string> = { conversation: "#72b0ab", router: "#fe9179", synthesizer: "#b89d47" };

function formatCost(n: number): string {
  return n < 0.01 && n > 0 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`;
}
function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}
const seconds = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`);
const shortenModel = (m: string) => (m.includes("sonnet") ? "Sonnet" : m.includes("haiku") ? "Haiku" : m);
const ICON_CLS = "h-5 w-5";

export interface PeriodData {
  overview: AdminOverview | null;
  timeseries: TimeseriesBucket[];
  latency: LatencyPercentiles[];
  engagement: EngagementMetrics | null;
}

function avgLatency(o: AdminOverview | null): number {
  if (!o || o.total_requests === 0) return 0;
  return Math.round(Object.values(o.by_phase).reduce((s, p) => s + p.avg_duration_ms, 0));
}

// ---------------------------------------------------------------- Overview

const SECTION_ICON = { data: HeartPulse, code: Scale, corrections: PencilLine } as const;

export function OverviewSection({ data }: { data: PeriodData }) {
  const [health, setHealth] = useState<DataHealth | null | undefined>(undefined);
  const [code, setCode] = useState<AdminCodeCurrency | null | undefined>(undefined);
  const [open, setOpen] = useState<number | null | undefined>(undefined);
  useEffect(() => {
    fetchDataHealth().then(setHealth);
    fetchAdminCodeCurrency().then(setCode);
    fetchAdminCorrections("new").then((d) => setOpen(d ? d.total : null));
  }, []);
  const o = data.overview;
  const e = data.engagement;
  const items: Attention[] = [dataAttention(health), codeAttention(code), correctionsAttention(open)];
  // Red first, then yellow, then the rest.
  const rank = { red: 0, yellow: 1, gray: 2, green: 3 } as const;
  items.sort((a, b) => rank[a.tone] - rank[b.tone]);
  return (
    <>
      <Tiles testId="admin-overview-tiles">
        <StatTile tone="a" icon={<Activity className={ICON_CLS} strokeWidth={STROKE} />} label="Requests" figure={(o?.total_requests ?? 0).toLocaleString()} />
        <StatTile tone="b" icon={<CircleDollarSign className={ICON_CLS} strokeWidth={STROKE} />} label="Model cost" figure={formatCost(o?.estimated_cost_usd ?? 0)} />
        <StatTile tone="b" icon={<Users className={ICON_CLS} strokeWidth={STROKE} />} label="Visitors" figure={(e?.unique_visitors ?? 0).toLocaleString()} />
        <StatTile tone="a" icon={<MessagesSquare className={ICON_CLS} strokeWidth={STROKE} />} label="Chat messages" figure={(e?.chat_messages ?? 0).toLocaleString()} />
      </Tiles>
      <Block title="Needs attention" icon={Gauge}>
        <ul className="flex flex-col divide-y divide-nx-ink/10" data-testid="admin-attention">
          {items.map((a) => {
            const label = ADMIN_SECTIONS.find((s) => s.id === a.section)!.label;
            return (
              <li key={a.section}>
                <Link to={`/admin/${a.section}`} className="flex items-center gap-3 py-2.5 hover:opacity-80" data-testid={`attention-${a.section}`}>
                  <IconBadge icon={SECTION_ICON[a.section as keyof typeof SECTION_ICON]} tone={a.tone} />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="font-medium">{a.words}</span>
                    <span className="text-caption nx-muted">{label}</span>
                  </span>
                  <ChevronRight aria-hidden className="h-4 w-4 nx-muted" strokeWidth={STROKE} />
                </Link>
              </li>
            );
          })}
        </ul>
      </Block>
    </>
  );
}

// ---------------------------------------------------------------- Usage and cost

export function UsageSection({ data }: { data: PeriodData }) {
  const o = data.overview;
  const series = useMemo(() => ({
    requests: [{ label: "Requests", values: data.timeseries.map((b) => ({ bucket: b.bucket, value: b.request_count })), color: "#fe9179" }],
    cost: [{ label: "Cost", values: data.timeseries.map((b) => ({ bucket: b.bucket, value: b.estimated_cost_usd })), color: "#b89d47" }],
    latency: [{ label: "Avg duration", values: data.timeseries.map((b) => ({ bucket: b.bucket, value: b.avg_duration_ms })), color: "#72b0ab" }],
  }), [data.timeseries]);
  const byModel = useMemo((): PieSlice[] => (o ? Object.entries(o.by_model).map(([m, u]) => ({ label: shortenModel(m), value: u.estimated_cost_usd, color: MODEL_COLORS[m] ?? "#8a8a8a" })) : []), [o]);
  const byPhase = useMemo((): PieSlice[] => (o ? Object.entries(o.by_phase).filter(([, u]) => u.count > 0)
    .map(([p, u]) => ({ label: p.charAt(0).toUpperCase() + p.slice(1), value: u.count, color: PHASE_COLORS[p] ?? "#8a8a8a" })) : []), [o]);
  const empty = data.timeseries.length === 0;
  const tokens = (o?.total_input_tokens ?? 0) + (o?.total_output_tokens ?? 0);
  return (
    <>
      <Tiles testId="admin-usage-tiles">
        <StatTile tone="a" icon={<Activity className={ICON_CLS} strokeWidth={STROKE} />} label="Requests" figure={(o?.total_requests ?? 0).toLocaleString()} />
        <StatTile tone="b" icon={<Coins className={ICON_CLS} strokeWidth={STROKE} />} label="Tokens" figure={formatTokens(tokens)}
          note={`${formatTokens(o?.total_input_tokens ?? 0)} in · ${formatTokens(o?.total_output_tokens ?? 0)} out`} />
        <StatTile tone="b" icon={<CircleDollarSign className={ICON_CLS} strokeWidth={STROKE} />} label="Model cost" figure={formatCost(o?.estimated_cost_usd ?? 0)} />
        <StatTile tone="a" icon={<Timer className={ICON_CLS} strokeWidth={STROKE} />} label="Answer time" figure={seconds(avgLatency(o))} note="All phases, average" />
      </Tiles>
      {empty ? (
        <Block title="Over time" icon={ChartLine}><Empty icon={ChartLine}>No requests or model calls in this period.</Empty></Block>
      ) : (
        <div className="nx-cq"><div className="nx-split nx-split-even">
          <Block title="Requests" icon={ChartLine}><TimeSeriesChart series={series.requests} /></Block>
          <Block title="Cost" icon={ChartLine}><TimeSeriesChart series={series.cost} formatValue={formatCost} /></Block>
          <Block title="Answer time" icon={Clock}><TimeSeriesChart series={series.latency} formatValue={seconds} /></Block>
          <Block title="Percentiles" icon={Timer}><LatencyTable rows={data.latency} /></Block>
        </div></div>
      )}
      {(byModel.length > 0 || byPhase.length > 0) && <div className="nx-cq"><div className="nx-split nx-split-even">
        <Block title="Cost by model" icon={ChartPie}>
          {byModel.length ? <div className="flex justify-center"><PieChart slices={byModel} size={160} /></div> : <Empty icon={ChartPie}>No model calls yet.</Empty>}
        </Block>
        <Block title="Calls by step" icon={ChartPie}>
          {byPhase.length ? <div className="flex justify-center"><PieChart slices={byPhase} size={160} /></div> : <Empty icon={ChartPie}>No model calls yet.</Empty>}
        </Block>
      </div></div>}
    </>
  );
}

// ---------------------------------------------------------------- Visitors

export function VisitorsSection({ data, conversations }: { data: PeriodData; conversations: ConversationStats | null }) {
  const e = data.engagement;
  const bars = (rec: Record<string, number> | undefined) => Object.entries(rec ?? {}).map(([label, value]) => ({ label, value }));
  const funnel = e?.funnel ?? [];
  const hero = e ? [
    ...Object.entries(e.hero_address_submits).map(([s, value]) => ({ label: `Address · ${s}`, value })),
    ...Object.entries(e.hero_librarian_clicks).map(([s, value]) => ({ label: `Librarian · ${s}`, value })),
  ] : [];
  return (
    <>
      <Tiles testId="admin-visitor-tiles">
        <StatTile tone="a" icon={<Users className={ICON_CLS} strokeWidth={STROKE} />} label="Visitors" figure={(e?.unique_visitors ?? 0).toLocaleString()} />
        <StatTile tone="b" icon={<Repeat className={ICON_CLS} strokeWidth={STROKE} />} label="Came back" figure={(e?.returning_visitors ?? 0).toLocaleString()}
          note={e?.avg_days_between_visits != null ? `Every ${e.avg_days_between_visits} days` : undefined} />
        <StatTile tone="b" icon={<MousePointerClick className={ICON_CLS} strokeWidth={STROKE} />} label="Profile to chat" figure={`${((e?.scorecard_to_chat_rate ?? 0) * 100).toFixed(1)}%`} />
        <StatTile tone="a" icon={<MessagesSquare className={ICON_CLS} strokeWidth={STROKE} />} label="Chats" figure={(conversations?.total_conversations ?? 0).toLocaleString()}
          note={conversations ? `${conversations.avg_messages_per_conversation.toFixed(1)} messages each · ${conversations.conversations_today} today` : undefined} />
      </Tiles>
      <div className="nx-cq"><div className="nx-split nx-split-even">
        <Block title="Funnel" icon={UserPlus}>
          {funnel.some((s) => s.visitors > 0) ? (
            <ol className="flex flex-col gap-2">
              {funnel.map((s, i) => {
                const base = funnel[0].visitors || 1;
                const prev = i > 0 ? funnel[i - 1].visitors : null;
                const rate = prev ? Math.round((s.visitors / prev) * 100) : null;
                return (
                  <li key={s.step} className="grid grid-cols-[8rem,1fr,auto] items-center gap-2 text-caption">
                    <span className="capitalize nx-muted">{s.step.replace(/_/g, " ")}</span>
                    <span className="h-2 overflow-hidden rounded bg-nx-ink/5"><span className="block h-full rounded bg-nx-chart-1" style={{ width: `${Math.max(s.visitors > 0 ? 2 : 0, (s.visitors / base) * 100)}%` }} /></span>
                    <span className="tabular-nums"><span className="font-semibold">{s.visitors}</span>{rate != null && <span className="nx-muted"> · {rate}%</span>}</span>
                  </li>
                );
              })}
            </ol>
          ) : <Empty icon={UserPlus}>No visits yet.</Empty>}
        </Block>
        <Block title="Where they came from" icon={Route}>
          {bars(e?.channels).length ? <BarChart bars={bars(e?.channels)} /> : <Empty icon={Route}>No visits yet.</Empty>}
        </Block>
        <Block title="Profile clicks" icon={MousePointerClick}>
          {bars(e?.investigate_clicks).length || bars(e?.scorecard_bridge_clicks).length
            ? <BarChart bars={[...bars(e?.investigate_clicks), ...bars(e?.scorecard_bridge_clicks).map((b) => ({ ...b, label: `Chat · ${b.label}` }))]} />
            : <Empty icon={MousePointerClick}>No clicks yet.</Empty>}
        </Block>
        <Block title="Who comes back" icon={Repeat}>
          {e && Object.keys(e.return_rate_by_behavior).length ? (
            <ul className="flex flex-col gap-1.5">
              {Object.entries(e.return_rate_by_behavior).map(([b, d]) => (
                <li key={b} className="flex items-center justify-between gap-2">
                  <span className="capitalize">{b.replace(/_/g, " ")}</span>
                  <span className="tabular-nums"><span className="font-semibold">{(d.rate * 100).toFixed(0)}%</span> <span className="text-caption nx-muted">{d.returned} of {d.total}</span></span>
                </li>
              ))}
            </ul>
          ) : <Empty icon={Repeat}>No returns yet.</Empty>}
          {hero.length > 0 && <BarChart bars={hero} />}
        </Block>
      </div></div>
    </>
  );
}

// ---------------------------------------------------------------- Answer quality and requests

export function QualitySection({ benchmark, judge }: { benchmark: BenchmarkResults | null; judge: JudgeResults | null }) {
  return (
    <div className="nx-cq"><div className="nx-split nx-split-even">
      <Block title="Finding the right code" icon={Target} aside={<Pill>Retrieval</Pill>}><BenchmarkSection benchmark={benchmark} /></Block>
      <Block title="Writing the answer" icon={MessagesSquare} aside={<Pill>Judge</Pill>}><JudgeSection results={judge} /></Block>
    </div></div>
  );
}

export function RequestsSection({ rows, onMore, hasMore }: { rows: RequestLogEntry[]; onMore: () => void; hasMore: boolean }) {
  return (
    <Block title="Latest requests" icon={Activity}>
      {rows.length ? <RequestsTable rows={rows} onLoadMore={onMore} hasMore={hasMore} /> : <Empty icon={Activity}>No requests yet.</Empty>}
    </Block>
  );
}
