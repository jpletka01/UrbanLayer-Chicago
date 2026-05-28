import { motion } from "motion/react";
import { useEffect, useRef } from "react";
import type { ContextObject, DataSource, PhaseTimings, RetrievalPlan } from "../../lib/types";

interface Props {
  plan: RetrievalPlan | null;
  context: ContextObject | null;
  loading: boolean;
  timings?: PhaseTimings;
  highlightedDataSource?: DataSource | null;
}

function fmtMs(ms?: number): string {
  if (ms === undefined) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`;
}

function Skeleton({ height = 24, className = "" }: { height?: number; className?: string }) {
  return (
    <div
      className={`animate-pulse bg-dark-elevated rounded ${className}`}
      style={{ height }}
    />
  );
}

const SOURCE_CONFIG: Record<string, { label: string; icon: string }> = {
  crime_api: { label: "Crime Data", icon: "🚨" },
  "311_api": { label: "311 Requests", icon: "📞" },
  permits_api: { label: "Building Permits", icon: "🏗️" },
  violations_api: { label: "Violations", icon: "⚠️" },
  business_api: { label: "Business Licenses", icon: "🏪" },
  vector_search: { label: "Municipal Code", icon: "📜" },
};

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  highlighted?: boolean;
}

const GlassCard = ({ children, className = "", highlighted }: GlassCardProps) => {
  return (
    <div className={`rounded-xl bg-dark-surface/80 backdrop-blur-sm border p-4 transition-all duration-300 ${
      highlighted
        ? "border-accent/50 ring-2 ring-accent/30"
        : "border-dark-border"
    } ${className}`}>
      {children}
    </div>
  );
};

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-medium tracking-wider text-text-muted uppercase mb-3">
      {children}
    </h3>
  );
}

export function DataView({ plan, context, loading, timings, highlightedDataSource }: Props) {
  const crimeRef = useRef<HTMLDivElement>(null);
  const threeOneOneRef = useRef<HTMLDivElement>(null);
  const permitsRef = useRef<HTMLDivElement>(null);
  const violationsRef = useRef<HTMLDivElement>(null);
  const businessRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!highlightedDataSource) return;
    const refMap: Record<DataSource, React.RefObject<HTMLDivElement | null>> = {
      crime: crimeRef,
      "311": threeOneOneRef,
      permits: permitsRef,
      violations: violationsRef,
      business: businessRef,
    };
    const ref = refMap[highlightedDataSource];
    ref?.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightedDataSource]);
  const retrievalDelta =
    timings?.retrieval_ms !== undefined && timings?.router_ms !== undefined
      ? timings.retrieval_ms - timings.router_ms
      : undefined;
  const synthesisDelta =
    timings?.first_token_ms !== undefined && timings?.retrieval_ms !== undefined
      ? timings.first_token_ms - timings.retrieval_ms
      : undefined;

  return (
    <div className="space-y-5">
      <section>
        <SectionHeader>Active Sources</SectionHeader>
        <div className="flex flex-wrap gap-2">
          {plan ? (
            plan.sources.length === 0 ? (
              <span className="text-sm text-text-muted">None</span>
            ) : (
              plan.sources.map((s) => {
                const config = SOURCE_CONFIG[s] ?? { label: s, icon: "📊" };
                return (
                  <motion.span
                    key={s}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-accent-muted text-accent border border-accent/20"
                  >
                    <span>{config.icon}</span>
                    <span>{config.label}</span>
                  </motion.span>
                );
              })
            )
          ) : (
            <>
              <Skeleton height={28} className="w-24" />
              <Skeleton height={28} className="w-28" />
            </>
          )}
        </div>
      </section>

      {context?.data_lag_note && (
        <div className="px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400/90 text-xs">
          {context.data_lag_note}
        </div>
      )}

      {timings && (timings.router_ms !== undefined || timings.total_ms !== undefined) && (
        <GlassCard>
          <SectionHeader>Latency</SectionHeader>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <span className="text-text-muted">Router</span>
            <span className="text-right font-mono text-text-secondary">{fmtMs(timings.router_ms)}</span>
            <span className="text-text-muted">Retrieval</span>
            <span className="text-right font-mono text-text-secondary">{fmtMs(retrievalDelta)}</span>
            <span className="text-text-muted">Synthesis TTFT</span>
            <span className="text-right font-mono text-text-secondary">{fmtMs(synthesisDelta)}</span>
            <span className="text-text-muted">Total</span>
            <span className="text-right font-mono text-text-primary font-medium">{fmtMs(timings.total_ms)}</span>
          </div>
        </GlassCard>
      )}

      {loading && !context && (
        <div className="space-y-3">
          <Skeleton height={100} />
          <Skeleton height={80} />
        </div>
      )}

      {context?.crime_last_90d && (
        <div ref={crimeRef}>
        <GlassCard highlighted={highlightedDataSource === "crime"}>
          <SectionHeader>Crime — {plan?.time_range_days ?? 90} days</SectionHeader>
          <div className="space-y-3">
            <div className="flex items-baseline gap-3">
              <span className="text-2xl font-semibold text-text-primary">
                {context.crime_last_90d.total}
              </span>
              <span className="text-sm text-text-muted">incidents</span>
              <span className="ml-auto text-sm">
                <span className="text-text-muted">Arrests:</span>{" "}
                <span className="text-text-secondary font-medium">
                  {Math.round(context.crime_last_90d.arrest_rate * 100)}%
                </span>
              </span>
            </div>
            <div className="space-y-1.5">
              {Object.entries(context.crime_last_90d.by_type).map(([type, count]) => (
                <div key={type} className="flex items-center justify-between text-sm">
                  <span className="text-text-secondary truncate">{type}</span>
                  <span className="font-mono text-text-muted ml-2">{count}</span>
                </div>
              ))}
            </div>
          </div>
        </GlassCard>
        </div>
      )}

      {context?.open_311_requests && (
        <div ref={threeOneOneRef}>
        <GlassCard highlighted={highlightedDataSource === "311"}>
          <SectionHeader>311 — Open Requests</SectionHeader>
          <div className="space-y-3">
            <div className="flex items-baseline gap-3">
              <span className="text-2xl font-semibold text-text-primary">
                {context.open_311_requests.total}
              </span>
              <span className="text-sm text-text-muted">open</span>
              {context.open_311_requests.oldest_open_days !== null && (
                <span className="ml-auto text-sm text-text-muted">
                  Oldest: <span className="text-text-secondary">{context.open_311_requests.oldest_open_days}d</span>
                </span>
              )}
            </div>
            <div className="space-y-1">
              {context.open_311_requests.top_types.slice(0, 5).map((type) => (
                <div key={type} className="text-sm text-text-secondary flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-text-muted" />
                  <span className="truncate">{type}</span>
                </div>
              ))}
            </div>
          </div>
        </GlassCard>
        </div>
      )}

      {context?.permits && (
        <div ref={permitsRef}>
        <GlassCard highlighted={highlightedDataSource === "permits"}>
          <SectionHeader>Building Permits</SectionHeader>
          <div className="flex items-baseline gap-3">
            <span className="text-2xl font-semibold text-text-primary">{context.permits.total}</span>
            <span className="text-sm text-text-muted">issued</span>
            <span className="ml-auto text-sm text-text-secondary">
              ${context.permits.total_estimated_cost.toLocaleString()}
            </span>
          </div>
        </GlassCard>
        </div>
      )}

      {context?.violations && (
        <div ref={violationsRef}>
        <GlassCard highlighted={highlightedDataSource === "violations"}>
          <SectionHeader>Building Violations</SectionHeader>
          <div className="space-y-3">
            <div className="flex items-baseline gap-3">
              <span className="text-2xl font-semibold text-text-primary">{context.violations.total}</span>
              <span className="text-sm text-text-muted">total</span>
              <span className="ml-auto text-sm">
                <span className="text-text-muted">Open:</span>{" "}
                <span className="text-text-secondary font-medium">{context.violations.open_count}</span>
              </span>
            </div>
            {context.violations.top_descriptions.length > 0 && (
              <div className="space-y-1">
                {context.violations.top_descriptions.slice(0, 3).map((desc) => (
                  <div key={desc} className="text-sm text-text-secondary flex items-center gap-2">
                    <span className="w-1 h-1 rounded-full bg-text-muted" />
                    <span className="truncate">{desc}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </GlassCard>
        </div>
      )}

      {context?.businesses && (
        <div ref={businessRef}>
        <GlassCard highlighted={highlightedDataSource === "business"}>
          <SectionHeader>Business Licenses</SectionHeader>
          <div className="space-y-3">
            <div className="flex items-baseline gap-3">
              <span className="text-2xl font-semibold text-text-primary">{context.businesses.total}</span>
              <span className="text-sm text-text-muted">active</span>
            </div>
            {context.businesses.top_activities.length > 0 && (
              <div className="space-y-1">
                {context.businesses.top_activities.slice(0, 3).map((activity) => (
                  <div key={activity} className="text-sm text-text-secondary flex items-center gap-2">
                    <span className="w-1 h-1 rounded-full bg-text-muted" />
                    <span className="truncate">{activity}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </GlassCard>
        </div>
      )}
    </div>
  );
}
