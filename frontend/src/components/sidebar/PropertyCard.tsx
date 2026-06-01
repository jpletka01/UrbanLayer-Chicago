import { useState } from "react";
import type { PropertySummary } from "../../lib/types";
import { CollapsibleCard } from "./CollapsibleCard";

const BuildingIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z" />
  </svg>
);

function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString();
}

function fmtDollar(n: number | null | undefined): string {
  if (n == null) return "—";
  return `$${n.toLocaleString()}`;
}

function KV({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value || value === "—") return null;
  return (
    <div className="flex justify-between items-baseline gap-2">
      <span className="text-text-muted text-[11px] shrink-0">{label}</span>
      <span className="text-text-primary text-[11px] font-mono text-right">{value}</span>
    </div>
  );
}

function MiniTable({ headers, rows }: { headers: string[]; rows: (string | null)[][] }) {
  return (
    <table className="w-full text-[11px]">
      <thead>
        <tr className="text-text-muted border-b border-dark-border">
          {headers.map(h => (
            <th key={h} className="text-left pb-1.5 pr-2 font-medium">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className="border-t border-dark-border/50">
            {row.map((cell, j) => (
              <td key={j} className={`py-1 pr-2 ${j > 0 ? "font-mono" : ""} text-text-primary`}>
                {cell ?? "—"}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PropertyCard({ data }: { data: PropertySummary }) {
  const [showAssessments, setShowAssessments] = useState(false);
  const [showSales, setShowSales] = useState(false);

  const baths = [
    data.full_baths != null ? `${data.full_baths}F` : null,
    data.half_baths != null ? `${data.half_baths}H` : null,
  ].filter(Boolean).join(" / ") || null;

  const classLabel = [data.bldg_class, data.bldg_class_description].filter(Boolean).join(" — ");

  return (
    <CollapsibleCard title="Property" icon={BuildingIcon}>
      <div className="space-y-3">
        {/* Key-value grid */}
        <div className="space-y-1">
          <KV label="Address" value={data.address} />
          <KV label="PIN" value={data.pin14} />
          {classLabel && <KV label="Class" value={classLabel} />}
          <KV label="Building Sqft" value={fmt(data.bldg_sqft)} />
          <KV label="Land Sqft" value={fmt(data.land_sqft)} />
          <KV label="Stories" value={data.stories != null ? String(data.stories) : null} />
          <KV label="Units" value={data.units != null ? String(data.units) : null} />
          <KV label="Rooms" value={data.rooms != null ? String(data.rooms) : null} />
          <KV label="Bedrooms" value={data.bedrooms != null ? String(data.bedrooms) : null} />
          <KV label="Baths" value={baths} />
          <KV label="Building Age" value={data.bldg_age != null ? `${data.bldg_age} yrs` : null} />
          <KV label="Assessed Value" value={fmtDollar(data.total_assessed_value)} />
        </div>

        {/* Assessment History */}
        {data.assessment_history.length > 0 && (
          <div>
            <button
              onClick={() => setShowAssessments(a => !a)}
              className="flex items-center gap-1.5 text-[11px] text-text-muted hover:text-text-secondary transition-colors"
            >
              <svg
                className={`w-2.5 h-2.5 transition-transform duration-150 ${showAssessments ? "" : "-rotate-90"}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
              Assessment History ({data.assessment_history.length} yrs)
            </button>
            {showAssessments && (
              <div className="mt-1.5">
                <MiniTable
                  headers={["Year", "Land", "Building", "Total"]}
                  rows={data.assessment_history.map(a => [
                    a.year != null ? String(a.year) : null,
                    fmtDollar(a.land),
                    fmtDollar(a.building),
                    fmtDollar(a.total),
                  ])}
                />
              </div>
            )}
          </div>
        )}

        {/* Sales History */}
        {data.sales_history.length > 0 && (
          <div>
            <button
              onClick={() => setShowSales(s => !s)}
              className="flex items-center gap-1.5 text-[11px] text-text-muted hover:text-text-secondary transition-colors"
            >
              <svg
                className={`w-2.5 h-2.5 transition-transform duration-150 ${showSales ? "" : "-rotate-90"}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
              Sales History ({data.sales_history.length})
            </button>
            {showSales && (
              <div className="mt-1.5">
                <MiniTable
                  headers={["Date", "Price", "Deed"]}
                  rows={data.sales_history.map(s => [
                    s.date ? new Date(s.date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : null,
                    fmtDollar(s.price),
                    s.deed_type,
                  ])}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </CollapsibleCard>
  );
}
