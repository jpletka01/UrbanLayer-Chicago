import { useState, useEffect, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  fetchAdminEngagement,
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
  EngagementMetrics,
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
import { VouchersSection } from "./admin/VouchersSection";
import { PieChart } from "./sidebar/PieChart";
import { BarChart } from "./sidebar/BarChart";
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
  const [engagement, setEngagement] = useState<EngagementMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async (p: Period) => {
    setLoading(true);
    const bucket = p === "today" ? "hour" : "day";
    const [ov, ts, lat, cs, req, bm, jr, eng] = await Promise.all([
      fetchAdminOverview(p),
      fetchAdminTimeseries(p, bucket),
      fetchAdminLatency(p),
      fetchConversationStats(),
      fetchRequestLogs(50, 0),
      fetchBenchmarkResults(),
      fetchJudgeResults(),
      fetchAdminEngagement(p),
    ]);
    setOverview(ov);
    setTimeseries(ts);
    setLatency(lat);
    setConvStats(cs);
    setRequests(req);
    setRequestOffset(50);
    setBenchmark(bm);
    setJudgeResults(jr);
    setEngagement(eng);
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
      <header className="h-14 border-b border-dark-border flex items-center px-6">
        <h1 className="text-subtitle font-semibold tracking-tight">
          <Link to="/" className="text-accent hover:text-accent-hover transition-colors">UrbanLayer</Link>
          <span className="text-text-muted ml-2">Admin</span>
        </h1>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Period selector */}
        <div className="flex gap-2 mb-6">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={`px-3 py-1.5 rounded-lg text-body transition-colors ${
                period === p.key
                  ? "bg-action text-white"
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
                <h2 className="text-body font-semibold text-text-secondary mb-3">
                  Requests Over Time
                </h2>
                <TimeSeriesChart series={requestsSeries} />
              </section>
              <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                <h2 className="text-body font-semibold text-text-secondary mb-3">
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
                <h2 className="text-body font-semibold text-text-secondary mb-3">
                  Cost by Model
                </h2>
                {costByModelSlices.length > 0 ? (
                  <div className="flex justify-center">
                    <PieChart slices={costByModelSlices} size={180} />
                  </div>
                ) : (
                  <div className="text-text-muted text-body text-center py-8">
                    No data
                  </div>
                )}
              </section>
              <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                <h2 className="text-body font-semibold text-text-secondary mb-3">
                  Calls by Phase
                </h2>
                {costByPhaseSlices.length > 0 ? (
                  <div className="flex justify-center">
                    <PieChart slices={costByPhaseSlices} size={180} />
                  </div>
                ) : (
                  <div className="text-text-muted text-body text-center py-8">
                    No data
                  </div>
                )}
              </section>
            </div>

            {/* Row 4: Latency */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                <h2 className="text-body font-semibold text-text-secondary mb-3">
                  Latency Percentiles
                </h2>
                <LatencyTable rows={latency} />
              </section>
              <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                <h2 className="text-body font-semibold text-text-secondary mb-3">
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
                <h2 className="text-body font-semibold text-text-secondary mb-3">
                  Retrieval Quality
                </h2>
                <BenchmarkSection benchmark={benchmark} />
              </section>

              <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                <h2 className="text-body font-semibold text-text-secondary mb-3">
                  Synthesis Quality
                </h2>
                <JudgeSection results={judgeResults} />
              </section>
            </div>

            {/* Row 6: Conversations */}
            <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
              <h2 className="text-body font-semibold text-text-secondary mb-3">
                Conversations
              </h2>
              {convStats ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 py-4">
                  <div className="text-center">
                    <CountUp
                      to={convStats.total_conversations}
                      format={(n) => n.toLocaleString()}
                      className="text-section font-semibold text-text-primary"
                    />
                    <div className="text-caption text-text-muted mt-1">
                      Total Conversations
                    </div>
                  </div>
                  <div className="text-center">
                    <CountUp
                      to={convStats.total_messages}
                      format={(n) => n.toLocaleString()}
                      className="text-section font-semibold text-text-primary"
                    />
                    <div className="text-caption text-text-muted mt-1">
                      Total Messages
                    </div>
                  </div>
                  <div className="text-center">
                    <CountUp
                      to={convStats.avg_messages_per_conversation}
                      format={(n) => n.toFixed(1)}
                      className="text-section font-semibold text-text-primary"
                    />
                    <div className="text-caption text-text-muted mt-1">
                      Avg Msgs / Conv
                    </div>
                  </div>
                  <div className="text-center">
                    <CountUp
                      to={convStats.conversations_today}
                      format={(n) => n.toLocaleString()}
                      className="text-section font-semibold text-text-primary"
                    />
                    <div className="text-caption text-text-muted mt-1">
                      Today
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-text-muted text-body text-center py-8">
                  No data
                </div>
              )}
            </section>

            {/* Row 7: Engagement */}
            {engagement && (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                    <h2 className="text-body font-semibold text-text-secondary mb-3">
                      Acquisition Funnel
                    </h2>
                    {engagement.funnel?.some((s) => s.visitors > 0) ? (
                      <div className="space-y-2 py-1">
                        {engagement.funnel.map((s, i) => {
                          const base = engagement.funnel[0].visitors || 1;
                          const prev = i > 0 ? engagement.funnel[i - 1].visitors : null;
                          const stepRate =
                            prev != null && prev > 0 ? (s.visitors / prev) * 100 : null;
                          return (
                            <div key={s.step} className="flex items-center gap-2">
                              <span className="w-32 shrink-0 text-caption text-text-secondary capitalize">
                                {s.step.replace(/_/g, " ")}
                              </span>
                              <div className="flex-1 h-4 rounded bg-dark-elevated overflow-hidden">
                                <div
                                  className="h-full rounded bg-accent/80"
                                  style={{ width: `${Math.max(s.visitors > 0 ? 1 : 0, (s.visitors / base) * 100)}%` }}
                                />
                              </div>
                              <span className="w-10 shrink-0 text-right text-caption font-semibold text-text-primary">
                                {s.visitors}
                              </span>
                              <span className="w-12 shrink-0 text-right text-micro text-text-muted">
                                {i > 0 && stepRate != null ? `${stepRate.toFixed(0)}%` : ""}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="text-text-muted text-body text-center py-8">No data</div>
                    )}
                  </section>
                  <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                    <h2 className="text-body font-semibold text-text-secondary mb-3">
                      Acquisition Channels
                    </h2>
                    {engagement.channels && Object.keys(engagement.channels).length > 0 ? (
                      <BarChart
                        bars={Object.entries(engagement.channels).map(([label, value]) => ({ label, value }))}
                      />
                    ) : (
                      <div className="text-text-muted text-body text-center py-8">No data</div>
                    )}
                  </section>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <StatCard
                    label="Unique Visitors"
                    value={engagement.unique_visitors}
                    format={(n) => n.toLocaleString()}
                  />
                  <StatCard
                    label="Returning Visitors"
                    value={engagement.returning_visitors}
                    format={(n) => n.toLocaleString()}
                    subtitle={engagement.avg_days_between_visits != null
                      ? `Avg ${engagement.avg_days_between_visits}d between visits`
                      : undefined}
                  />
                  <StatCard
                    label="Scorecard → Chat"
                    value={engagement.scorecard_to_chat_rate ?? 0}
                    format={(n) => `${(n * 100).toFixed(1)}%`}
                  />
                  <StatCard
                    label="Chat Messages"
                    value={engagement.chat_messages}
                    format={(n) => n.toLocaleString()}
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                    <h2 className="text-body font-semibold text-text-secondary mb-3">
                      Investigate Clicks by Card
                    </h2>
                    {Object.keys(engagement.investigate_clicks).length > 0 ? (
                      <BarChart
                        bars={Object.entries(engagement.investigate_clicks).map(([label, value]) => ({ label, value }))}
                      />
                    ) : (
                      <div className="text-text-muted text-body text-center py-8">No data</div>
                    )}
                  </section>
                  <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                    <h2 className="text-body font-semibold text-text-secondary mb-3">
                      Return Rate by Behavior
                    </h2>
                    {Object.keys(engagement.return_rate_by_behavior).length > 0 ? (
                      <div className="space-y-3 py-2">
                        {Object.entries(engagement.return_rate_by_behavior).map(([behavior, data]) => (
                          <div key={behavior} className="flex items-center justify-between">
                            <span className="text-body text-text-primary capitalize">
                              {behavior.replace("_", " ")}
                            </span>
                            <div className="text-right">
                              <span className="text-body font-semibold text-text-primary">
                                {(data.rate * 100).toFixed(1)}%
                              </span>
                              <span className="text-caption text-text-muted ml-2">
                                ({data.returned}/{data.total})
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-text-muted text-body text-center py-8">No data</div>
                    )}
                    {engagement.report_cta_clicks > 0 && (
                      <div className="mt-3 pt-3 border-t border-dark-border flex items-center justify-between">
                        <span className="text-body text-text-secondary">Report CTA Clicks</span>
                        <div className="text-right">
                          <span className="text-body font-semibold text-text-primary">
                            {engagement.report_cta_clicks}
                          </span>
                          {engagement.report_purchases_count > 0 && (
                            <span className="text-caption text-text-muted ml-2">
                              → {engagement.report_purchases_count} purchased
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                    {engagement.sample_report_clicks > 0 && (
                      <div className="mt-3 pt-3 border-t border-dark-border flex items-center justify-between">
                        <span className="text-body text-text-secondary">Sample Report Clicks</span>
                        <span className="text-body font-semibold text-text-primary">
                          {engagement.sample_report_clicks}
                        </span>
                      </div>
                    )}
                  </section>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                    <h2 className="text-body font-semibold text-text-secondary mb-3">
                      Hero Entries
                    </h2>
                    {Object.keys(engagement.hero_address_submits).length > 0
                      || Object.keys(engagement.hero_librarian_clicks).length > 0 ? (
                      <BarChart
                        bars={[
                          ...Object.entries(engagement.hero_address_submits).map(
                            ([source, value]) => ({ label: `Address — ${source}`, value }),
                          ),
                          ...Object.entries(engagement.hero_librarian_clicks).map(
                            ([source, value]) => ({ label: `Librarian — ${source}`, value }),
                          ),
                        ]}
                      />
                    ) : (
                      <div className="text-text-muted text-body text-center py-8">No data</div>
                    )}
                  </section>
                  <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
                    <h2 className="text-body font-semibold text-text-secondary mb-3">
                      Scorecard Bridge Clicks
                    </h2>
                    {Object.keys(engagement.scorecard_bridge_clicks).length > 0 ? (
                      <BarChart
                        bars={Object.entries(engagement.scorecard_bridge_clicks).map(([label, value]) => ({ label, value }))}
                      />
                    ) : (
                      <div className="text-text-muted text-body text-center py-8">No data</div>
                    )}
                  </section>
                </div>
              </>
            )}

            {/* Row 8: Recent requests */}
            <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
              <h2 className="text-body font-semibold text-text-secondary mb-3">
                Recent Requests
              </h2>
              <RequestsTable
                rows={requests}
                onLoadMore={handleLoadMore}
                hasMore={requests.length >= requestOffset}
              />
            </section>

            {/* Row 9: Early-adopter access (voucher codes + email grants) */}
            <section className="bg-dark-surface border border-dark-border rounded-xl p-4">
              <h2 className="text-body font-semibold text-text-secondary mb-3">
                Early Access
              </h2>
              <VouchersSection />
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
