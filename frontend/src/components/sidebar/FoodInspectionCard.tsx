import type { FoodInspectionSummary } from "../../lib/types";
import { CollapsibleCard } from "./CollapsibleCard";

const ForkKnifeIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M12 8.25v-1.5m0 1.5c-1.355 0-2.697.056-4.024.166C6.845 8.51 6 9.473 6 10.608v2.513m6-4.871c1.355 0 2.697.056 4.024.166C17.155 8.51 18 9.473 18 10.608v2.513M15 8.25v-1.5m-6 1.5v-1.5m12 9.75l-1.5.75a3.354 3.354 0 01-3 0 3.354 3.354 0 00-3 0 3.354 3.354 0 01-3 0 3.354 3.354 0 00-3 0 3.354 3.354 0 01-3 0L3 16.5m15-3.379a48.474 48.474 0 00-6-.371c-2.032 0-4.034.126-6 .371m12 0c.39.049.777.102 1.163.16 1.07.16 1.837 1.094 1.837 2.175v5.169c0 .621-.504 1.125-1.125 1.125H4.125A1.125 1.125 0 013 20.625v-5.17c0-1.08.768-2.014 1.837-2.174A47.78 47.78 0 016 13.12M12.265 3.11a.375.375 0 11-.53 0L12 2.845l.265.265zm-3 0a.375.375 0 11-.53 0L9 2.845l.265.265zm6 0a.375.375 0 11-.53 0L15 2.845l.265.265z" />
  </svg>
);

function KV({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between items-baseline gap-2">
      <span className="text-text-muted text-[11px] truncate">{label}</span>
      <span className={`text-[11px] font-mono shrink-0 ${color ?? "text-text-primary"}`}>{value}</span>
    </div>
  );
}

function resultColor(result: string | null): string {
  if (!result) return "text-text-muted";
  const r = result.toLowerCase();
  if (r === "pass") return "text-green-400";
  if (r === "fail") return "text-red-400";
  if (r.includes("conditional") || r.includes("conditions")) return "text-yellow-400";
  return "text-text-secondary";
}

export function FoodInspectionCard({ data }: { data: FoodInspectionSummary }) {
  const results = Object.entries(data.by_result ?? {})
    .sort(([, a], [, b]) => b - a);

  const risks = Object.entries(data.by_risk ?? {})
    .sort(([, a], [, b]) => b - a);

  return (
    <CollapsibleCard title="Food Inspections" icon={ForkKnifeIcon}>
      <div className="space-y-2.5">
        <div className="flex justify-center gap-4 py-1">
          <div className="text-center">
            <div className="text-sm font-semibold text-text-primary">{data.total.toLocaleString()}</div>
            <div className="text-[10px] text-text-muted mt-0.5">Inspections (1yr)</div>
          </div>
          {data.fail_rate != null && (
            <div className="text-center">
              <div className={`text-sm font-semibold ${data.fail_rate > 15 ? "text-red-400" : "text-text-primary"}`}>
                {data.fail_rate}%
              </div>
              <div className="text-[10px] text-text-muted mt-0.5">Fail Rate</div>
            </div>
          )}
        </div>

        {results.length > 0 && (
          <div className="space-y-0.5">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">By Result</span>
            {results.map(([result, count]) => (
              <KV key={result} label={result} value={String(count)} color={resultColor(result)} />
            ))}
          </div>
        )}

        {risks.length > 0 && (
          <div className="space-y-0.5">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">By Risk Level</span>
            {risks.map(([risk, count]) => (
              <KV key={risk} label={risk} value={String(count)} />
            ))}
          </div>
        )}

        {data.recent_inspections?.length > 0 && (
          <div className="space-y-1.5">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">Recent Inspections</span>
            {data.recent_inspections.slice(0, 5).map((insp, i) => (
              <div key={i} className="text-[10px] leading-tight pl-1 border-l border-dark-border">
                <p className="text-text-primary">{insp.name}</p>
                <div className="flex gap-2 text-text-muted">
                  {insp.date && <span>{insp.date}</span>}
                  {insp.result && <span className={resultColor(insp.result)}>{insp.result}</span>}
                </div>
                {insp.facility_type && <p className="text-text-muted">{insp.facility_type}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </CollapsibleCard>
  );
}
