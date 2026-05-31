import { useState, useEffect, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  fetchAdminOverview,
  fetchAdminTimeseries,
  fetchAdminLatency,
  fetchConversationStats,
  fetchRequestLogs,
  fetchBenchmarkResults,
  fetchJudgeResults,
} from "../lib/api";
import type {
  AdminOverview,
  TimeseriesBucket,
  LatencyPercentiles,
  ConversationStats,
  RequestLogEntry,
  BenchmarkResults,
  JudgeResults,
} from "../lib/types";
import type { PieSlice } from "../lib/analytics";
import { StatCard } from "./admin/StatCard";
import { TimeSeriesChart } from "./admin/TimeSeriesChart";
import { LatencyTable } from "./admin/LatencyTable";
import { RequestsTable } from "./admin/RequestsTable";
import { BenchmarkSection } from "./admin/BenchmarkSection";
import { JudgeSection } from "./admin/JudgeSection";
import { PieChart } from "./sidebar/PieChart";
import { CountUp } from "./CountUp";

type Period = "today" | "7d" | "30d" | "all";
const PERIODS: { key: Period; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "7d", label: "7 Days" },
  { key: "30d", label: "30 Days" },
  { key: "all", label: "All Time" },
];

const MODEL_COLORS: Record<string, string> = {
  "claude-sonnet-4-6": "#c96442",
  "claude-haiku-4-5-20251001": "#6b9bd2",
};

const PHASE_COLORS: Record<string, string> = {
  conversation: "#6b9bd2",
  router: "#c96442",
  synthesizer: "#4ade80",
};

function formatCost(n: number): string {
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function shortenModel(m: string): string {
  if (m.includes("sonnet")) return "Sonnet";
  if (m.includes("haiku")) return "Haiku";
  return m;
}

export function AdminDashboard() {
  const [period, setPeriod] = useState<Period>("30d");
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesBucket[]>([]);
  const [latency, setLatency] = useState<LatencyPercentiles[]>([]);
  const [convStats, setConvStats] = useState<ConversationStats | null>(null);
  const [requests, setRequests] = useState<RequestLogEntry[]>([]);
  const [requestOffset, setRequestOffset] = useState(0);
  const [benchmark, setBenchmark] = useState<BenchmarkResults | null>(null);
  const [judgeResults, setJudgeResults] = useState<JudgeResults | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async (p: Period) => {
    setLoading(true);
    const bucket = p === "today" ? "hour" : "day";
    const [ov, ts, lat, cs, req, bm, jr] = await Promise.all([
      fetchAdminOverview(p),
      fetchAdminTimeseries(p, bucket),
      fetchAdminLatency(p),
      fetchConversationStats(),
      fetchRequestLogs(50, 0),
      fetchBenchmarkResults(),
      fetchJudgeResults(),
    ]);
    setOverview(ov);
    setTimeseries(ts);
    setLatency(lat);
    setConvStats(cs);
    setRequests(req);
    setRequestOffset(50);
    setBenchmark(bm);
    setJudgeResults(jr);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadData(period);
  }, [period, loadData]);

  const handleLoadMore = useCallback(async () => {
    const more = await fetchRequestLogs(50, requestOffset);
    setRequests((prev) => [...prev, ...more]);
    setRequestOffset((prev) => prev + 50);
  }, [requestOffset]);

  const avgLatency = useMemo(() => {
    if (!overview || overview.total_requests === 0) return 0;
    const phases = Object.values(overview.by_phase);
    if (phases.length === 0) return 0;
    const totalAvg = phases.reduce((sum, p) => sum + p.avg_duration_ms, 0);
    return Math.round(totalAvg);
  }, [overview]);

  // Cost by model pie
  const costByModelSlices = useMemo((): PieSlice[] => {
    if (!overview) return [];
    return Object.entries(overview.by_model).map(([model, usage]) => ({
      label: shortenModel(model),
      value: usage.estimated_cost_usd,
      color: MODEL_COLORS[model] ?? "#888",
    }));
  }, [overview]);

  // Cost by phase pie
  const costByPhaseSlices = useMemo((): PieSlice[] => {
    if (!overview) return [];
    return Object.entries(overview.by_phase)
      .filter(([, usage]) => usage.count > 0)
      .map(([phase, usage]) => ({
        label: phase.charAt(0).toUpperCase() + phase.slice(1),
        value: usage.count,
        color: PHASE_COLORS[phase] ?? "#888",
      }));
  }, [overview]);

  // Usage timeseries
  const requestsSeries = useMemo(
    () => [
      {
        label: "Requests",
        values: timeseries.map((b) => ({ bucket: b.bucket, value: b.request_count })),
        color: "#c96442",
      },
    ],
    [timeseries],
  );

  const costSeries = useMemo(
    () => [
      {
        label: "Cost",
        values: timeseries.map((b) => ({ bucket: b.bucket, value: b.estimated_cost_usd })),
        color: "#4ade80",
      },
    ],
    [timeseries],
  );

  const latencySeries = useMemo(
    () => [
      {
        label: "Avg Duration",
        values: timeseries.map((b) => ({ bucket: b.bucket, value: b.avg_duration_ms })),
        color: "#6b9bd2",
      },
    ],
    [timeseries],
  );

  return (
    <div className="min-h-screen bg-dark-bg text-text-primary">
      {/* Header */}
      <header className="h-14 border-b border-dark-border flex items-center justify-between px-6">
        <h1 className="text-lg font-semibold tracking-tight">
          <span className="text-accent">UrbanLayer</span>
          <span className="text-text-muted ml-2">Admin</span>
        </h1>
        <Link
          to="/"
          className="text-sm text-text-muted hover:text-text-primary transition-colors"
        >
          &larr; Back to app
        </Link>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Period selector */}
        <div className="flex gap-2 mb-6">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                period === p.key
                  ? "bg-accent text-white"
                  : "bg-dark-surface text-text-secondary hover:text-text-primary border border-dark-border"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="text-text-muted text-center py-20">Loading...</div>
        ) : (
          <div className="space-y-6">
            {/* Row 1: Stat cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                label="Total Requests"
                value={overview?.total_requests ?? 0}
                format={(n) => n.toLocaleString()}
              />
              <StatCard
                label="Tokens Used"
                value={(overview?.total_input_tokens ?? 0) + (overview?.total_output_tokens ?? 0)}
                format={formatTokens}
                subtitle={`${formatTokens(overview?.total_input_tokens ?? 0)} in / ${formatTokens(overview?.total_output_tokens ?? 0)} out`}
              />
              <StatCard
                label="Estimated Cost"
                value={overview?.estimated_cost_usd ?? 0}
                format={formatCost}
              />
              <StatCard
                label="Avg Latency (sum)"
                value={avgLatency}
                format={(n) => `${(n / 1000).toFixed(1)}s`}
                subtitle="Sum of avg phase durations"
              />
            </div>

            {/* Row 2: Usage over time */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                <h2 className="text-sm font-semibold text-text-secondary mb-3">
                  Requests Over Time
                </h2>
                <TimeSeriesChart series={requestsSeries} />
              </section>
              <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                <h2 className="text-sm font-semibold text-text-secondary mb-3">
                  Cost Over Time
                </h2>
                <TimeSeriesChart
                  series={costSeries}
                  formatValue={formatCost}
                />
              </section>
            </div>

            {/* Row 3: Pie charts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                <h2 className="text-sm font-semibold text-text-secondary mb-3">
                  Cost by Model
                </h2>
                {costByModelSlices.length > 0 ? (
                  <div className="flex justify-center">
                    <PieChart slices={costByModelSlices} size={180} />
                  </div>
                ) : (
                  <div className="text-text-muted text-sm text-center py-8">
                    No data
                  </div>
                )}
              </section>
              <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                <h2 className="text-sm font-semibold text-text-secondary mb-3">
                  Calls by Phase
                </h2>
                {costByPhaseSlices.length > 0 ? (
                  <div className="flex justify-center">
                    <PieChart slices={costByPhaseSlices} size={180} />
                  </div>
                ) : (
                  <div className="text-text-muted text-sm text-center py-8">
                    No data
                  </div>
                )}
              </section>
            </div>

            {/* Row 4: Latency */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                <h2 className="text-sm font-semibold text-text-secondary mb-3">
                  Latency Percentiles
                </h2>
                <LatencyTable rows={latency} />
              </section>
              <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                <h2 className="text-sm font-semibold text-text-secondary mb-3">
                  Latency Over Time
                </h2>
                <TimeSeriesChart
                  series={latencySeries}
                  formatValue={(v) =>
                    v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${Math.round(v)}ms`
                  }
                />
              </section>
            </div>

            {/* Row 5: Eval quality (Retrieval + Synthesis) */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                <h2 className="text-sm font-semibold text-text-secondary mb-3">
                  Retrieval Quality
                </h2>
                <BenchmarkSection benchmark={benchmark} />
              </section>

              <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                <h2 className="text-sm font-semibold text-text-secondary mb-3">
                  Synthesis Quality
                </h2>
                <JudgeSection results={judgeResults} />
              </section>
            </div>

            {/* Row 6: Conversations */}
            <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
              <h2 className="text-sm font-semibold text-text-secondary mb-3">
                Conversations
              </h2>
              {convStats ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 py-4">
                  <div className="text-center">
                    <CountUp
                      to={convStats.total_conversations}
                      format={(n) => n.toLocaleString()}
                      className="text-2xl font-semibold text-text-primary"
                    />
                    <div className="text-xs text-text-muted mt-1">
                      Total Conversations
                    </div>
                  </div>
                  <div className="text-center">
                    <CountUp
                      to={convStats.total_messages}
                      format={(n) => n.toLocaleString()}
                      className="text-2xl font-semibold text-text-primary"
                    />
                    <div className="text-xs text-text-muted mt-1">
                      Total Messages
                    </div>
                  </div>
                  <div className="text-center">
                    <CountUp
                      to={convStats.avg_messages_per_conversation}
                      format={(n) => n.toFixed(1)}
                      className="text-2xl font-semibold text-text-primary"
                    />
                    <div className="text-xs text-text-muted mt-1">
                      Avg Msgs / Conv
                    </div>
                  </div>
                  <div className="text-center">
                    <CountUp
                      to={convStats.conversations_today}
                      format={(n) => n.toLocaleString()}
                      className="text-2xl font-semibold text-text-primary"
                    />
                    <div className="text-xs text-text-muted mt-1">
                      Today
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-text-muted text-sm text-center py-8">
                  No data
                </div>
              )}
            </section>

            {/* Row 7: Recent requests */}
            <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
              <h2 className="text-sm font-semibold text-text-secondary mb-3">
                Recent Requests
              </h2>
              <RequestsTable
                rows={requests}
                onLoadMore={handleLoadMore}
                hasMore={requests.length >= requestOffset}
              />
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
