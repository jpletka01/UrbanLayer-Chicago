import type { ContextObject, PhaseTimings, RetrievalPlan } from "../lib/types";
import { SourceCitation } from "./SourceCitation";

interface Props {
  plan: RetrievalPlan | null;
  context: ContextObject | null;
  loading: boolean;
  timings?: PhaseTimings;
}

function fmtMs(ms?: number): string {
  if (ms === undefined) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`;
}

function Skeleton({ height = 24 }: { height?: number }) {
  return <div className="animate-pulse bg-slate-200 rounded" style={{ height }} />;
}

const SOURCE_LABELS: Record<string, string> = {
  crime_api: "CPD Crime API",
  "311_api": "311 Service Requests",
  permits_api: "Building Permits",
  violations_api: "Building Violations",
  business_api: "Business Licenses",
  vector_search: "Municipal Code (Qdrant)",
};

export function SidebarPanel({ plan, context, loading, timings }: Props) {
  const retrievalDelta =
    timings?.retrieval_ms !== undefined && timings?.router_ms !== undefined
      ? timings.retrieval_ms - timings.router_ms
      : undefined;
  const synthesisDelta =
    timings?.first_token_ms !== undefined && timings?.retrieval_ms !== undefined
      ? timings.first_token_ms - timings.retrieval_ms
      : undefined;
  return (
    <aside className="w-full md:w-2/5 h-full overflow-y-auto bg-slate-100 border-l border-slate-200 p-6 space-y-5">
      <header className="space-y-1">
        <h2 className="text-xs font-bold tracking-wider text-slate-400 uppercase">
          Context & Data Insights
        </h2>
        {context?.community_area_name && (
          <p className="text-sm text-slate-600">
            Resolved to <strong className="text-slate-900">{context.community_area_name}</strong>{" "}
            (CA {context.community_area})
          </p>
        )}
        {context?.data_lag_note && (
          <p className="text-xs text-amber-700">{context.data_lag_note}</p>
        )}
      </header>

      {timings && (timings.router_ms !== undefined || timings.total_ms !== undefined) && (
        <section className="p-3 rounded-xl bg-white border border-slate-200 shadow-sm">
          <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-2">
            Latency
          </h3>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
            <span className="text-slate-500">Router</span>
            <span className="text-right font-mono text-slate-900">{fmtMs(timings.router_ms)}</span>
            <span className="text-slate-500">Retrieval</span>
            <span className="text-right font-mono text-slate-900">{fmtMs(retrievalDelta)}</span>
            <span className="text-slate-500">Synthesis TTFT</span>
            <span className="text-right font-mono text-slate-900">{fmtMs(synthesisDelta)}</span>
            <span className="text-slate-500">Total</span>
            <span className="text-right font-mono text-slate-900">{fmtMs(timings.total_ms)}</span>
          </div>
        </section>
      )}

      <section>
        <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-2">
          Active Sources
        </h3>
        {plan ? (
          <div className="flex flex-wrap gap-2">
            {plan.sources.length === 0 && <span className="text-xs text-slate-500">None</span>}
            {plan.sources.map((s) => (
              <span
                key={s}
                className="px-2 py-1 rounded-md text-xs font-medium bg-sky-50 text-sky-700 border border-sky-200"
              >
                {SOURCE_LABELS[s] ?? s}
              </span>
            ))}
          </div>
        ) : (
          <Skeleton />
        )}
      </section>

      {loading && !context && (
        <section className="space-y-2">
          <Skeleton height={20} />
          <Skeleton height={80} />
          <Skeleton height={80} />
        </section>
      )}

      {context?.crime_last_90d && (
        <section className="p-4 rounded-xl bg-white border border-slate-200 shadow-sm space-y-2">
          <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase">
            Crime — last {plan?.time_range_days ?? 90} days
          </h3>
          <p className="text-sm">
            <strong className="text-slate-900">{context.crime_last_90d.total}</strong> incidents,{" "}
            arrest rate <strong>{Math.round(context.crime_last_90d.arrest_rate * 100)}%</strong>
          </p>
          <ul className="text-xs text-slate-600 space-y-0.5">
            {Object.entries(context.crime_last_90d.by_type).map(([k, v]) => (
              <li key={k} className="flex justify-between">
                <span>{k}</span>
                <span className="font-mono">{v}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {context?.open_311_requests && (
        <section className="p-4 rounded-xl bg-white border border-slate-200 shadow-sm space-y-2">
          <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase">311 — open requests</h3>
          <p className="text-sm">
            <strong className="text-slate-900">{context.open_311_requests.total}</strong> open
            {context.open_311_requests.oldest_open_days !== null && (
              <>, oldest is <strong>{context.open_311_requests.oldest_open_days} days</strong> old</>
            )}
          </p>
          <ul className="text-xs text-slate-600 space-y-0.5">
            {context.open_311_requests.top_types.slice(0, 6).map((t) => (
              <li key={t}>• {t}</li>
            ))}
          </ul>
        </section>
      )}

      {context?.permits && (
        <section className="p-4 rounded-xl bg-white border border-slate-200 shadow-sm space-y-2">
          <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase">Recent permits</h3>
          <p className="text-sm">
            <strong>{context.permits.total}</strong> issued, total est. ${context.permits.total_estimated_cost.toLocaleString()}
          </p>
        </section>
      )}

      {context && context.code_chunks.length > 0 && (
        <section className="space-y-3">
          <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase">
            Municipal code matches
          </h3>
          {context.code_chunks.map((c) => (
            <SourceCitation key={`${c.section}-${c.subsection ?? ""}`} chunk={c} />
          ))}
        </section>
      )}
    </aside>
  );
}
