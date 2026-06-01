import { useState } from "react";
import type { ViolationSummary } from "../../lib/types";
import { CollapsibleCard } from "./CollapsibleCard";

const AlertIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
  </svg>
);

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-baseline gap-2">
      <span className="text-text-muted text-[11px] truncate">{label}</span>
      <span className="text-text-primary text-[11px] font-mono shrink-0">{value}</span>
    </div>
  );
}

export function ViolationsCard({ data }: { data: ViolationSummary }) {
  const [showDescriptions, setShowDescriptions] = useState(false);

  const categories = Object.entries(data.by_category ?? {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8);

  return (
    <CollapsibleCard title="Violations" icon={AlertIcon}>
      <div className="space-y-2.5">
        <div className="grid grid-cols-2 gap-2 py-1">
          <div className="text-center">
            <div className="text-sm font-semibold text-text-primary">{data.total.toLocaleString()}</div>
            <div className="text-[10px] text-text-muted mt-0.5">Total</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-semibold text-amber-400">{data.open_count.toLocaleString()}</div>
            <div className="text-[10px] text-text-muted mt-0.5">Open</div>
          </div>
        </div>

        {categories.length > 0 && (
          <div className="space-y-0.5">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">By Category</span>
            {categories.map(([cat, count]) => (
              <KV key={cat} label={cat} value={String(count)} />
            ))}
          </div>
        )}

        {data.top_descriptions?.length > 0 && (
          <div>
            <button
              onClick={() => setShowDescriptions(s => !s)}
              className="flex items-center gap-1 text-[10px] text-text-muted hover:text-text-secondary transition-colors"
            >
              <svg
                className={`w-2.5 h-2.5 transition-transform duration-200 ${showDescriptions ? "" : "-rotate-90"}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
              Top Descriptions
            </button>
            {showDescriptions && (
              <ul className="mt-1 space-y-1">
                {data.top_descriptions.map((desc, i) => (
                  <li key={i} className="text-[10px] text-text-muted leading-tight pl-3">
                    {desc}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {data.capped && (
          <p className="text-[10px] text-text-muted italic">
            Showing first {data.total.toLocaleString()} — more may exist.
          </p>
        )}
      </div>
    </CollapsibleCard>
  );
}
