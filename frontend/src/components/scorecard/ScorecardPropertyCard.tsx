// Page-scale Property card. The chat sidebar's PropertyCard is built for a ~350px
// rail (micro type, label/value ledger rows); this is the Scorecard-page version:
// body-size type, stat-first layout, and the history/tax numbers drawn as marks
// (sparkline + bars) instead of hidden behind disclosure tables. Data shape is
// identical — presentation only. Chart specs follow the dataviz method: 2px line,
// ≥8px end markers with a 2px surface ring, ≤24px bars with a rounded data-end,
// area wash at 10%, text in text tokens (never the series color).
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { PropertySummary } from "../../lib/types";
import { formatDate } from "../../lib/format";
import { Card } from "../ui/Card";

function fmtDollar(n: number | null | undefined): string {
  if (n == null) return "—";
  return `$${n.toLocaleString()}`;
}

function fmtCompact(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n)}`;
}

const BuildingIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z" />
  </svg>
);

/** Assessment-history sparkline: single series → one hue (accent), no legend;
    endpoint marker + selective labels (first/last year) only. */
function AssessmentSparkline({ history }: { history: PropertySummary["assessment_history"] }) {
  const pts = history
    .filter((a): a is { year: number; land: number | null; building: number | null; total: number } =>
      a.year != null && a.total != null && a.total > 0)
    .sort((a, b) => a.year - b.year);
  if (pts.length < 2) return null;

  const W = 560, H = 56, PX = 4, PY = 6;
  const xs = pts.map((p) => p.year);
  const ys = pts.map((p) => p.total);
  const minX = xs[0], maxX = xs[xs.length - 1];
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const x = (yr: number) => PX + ((yr - minX) / (maxX - minX)) * (W - 2 * PX);
  const y = (v: number) => (maxY === minY ? H / 2 : PY + (1 - (v - minY) / (maxY - minY)) * (H - 2 * PY));
  const line = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${x(p.year).toFixed(1)} ${y(p.total).toFixed(1)}`).join(" ");
  const area = `${line} L ${x(maxX).toFixed(1)} ${H} L ${x(minX).toFixed(1)} ${H} Z`;
  const last = pts[pts.length - 1];

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-14" aria-hidden>
        <path d={area} fill="rgb(var(--accent) / 0.10)" />
        <path d={line} fill="none" stroke="rgb(var(--accent))" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {pts.map((p) => (
          <circle key={p.year} cx={x(p.year)} cy={y(p.total)} r="4"
            fill="rgb(var(--accent))" stroke="rgb(var(--surface))" strokeWidth="2">
            <title>{`${p.year} · ${fmtDollar(p.total)}`}</title>
          </circle>
        ))}
      </svg>
      <div className="flex justify-between text-caption text-text-muted mt-1">
        <span>{pts[0].year} · {fmtCompact(pts[0].total)}</span>
        <span className="text-text-secondary">{last.year} · {fmtCompact(last.total)}</span>
      </div>
    </div>
  );
}

/** Tax-breakdown bars: magnitude of parts → one hue; top agencies + Other;
    ≤24px thick, rounded data-end, square baseline, value at the tip. */
function TaxBars({ breakdown }: { breakdown: PropertySummary["tax_breakdown"] }) {
  const { t } = useTranslation("data");
  const sorted = [...breakdown].sort((a, b) => b.amount - a.amount);
  const top = sorted.slice(0, 4);
  const rest = sorted.slice(4);
  const rows = [
    ...top.map((b) => ({ label: b.agency, amount: b.amount })),
    ...(rest.length > 0
      ? [{ label: t("property.otherAgencies", { count: rest.length }), amount: rest.reduce((s, b) => s + b.amount, 0) }]
      : []),
  ];
  const max = Math.max(...rows.map((r) => r.amount));
  if (!(max > 0)) return null;
  return (
    <div className="space-y-1.5">
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[minmax(0,42%)_1fr] items-center gap-x-3">
          <div className="text-caption text-text-secondary truncate" title={r.label}>{r.label}</div>
          <div className="flex items-center gap-2 min-w-0">
            <div className="h-2.5 rounded-r bg-accent shrink-0" style={{ width: `${Math.max((r.amount / max) * 100 * 0.8, 1.5)}%` }} />
            <span className="text-caption text-text-primary whitespace-nowrap">{fmtCompact(r.amount)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value || value === "—") return null;
  return (
    <div>
      <dt className="text-caption text-text-muted">{label}</dt>
      <dd className="text-body text-text-primary mt-0.5">{value}</dd>
    </div>
  );
}

export function ScorecardPropertyCard({ data }: { data: PropertySummary }) {
  const { t } = useTranslation("data");
  const [showRecords, setShowRecords] = useState(false);

  const assessed = data.total_assessed_value;
  const tax = data.estimated_annual_tax;
  const effectiveRate = assessed && assessed > 0 && tax && tax > 0
    ? `${((tax / (assessed / 0.10)) * 100).toFixed(2)}%`
    : null;

  const baths = [
    data.full_baths ? `${data.full_baths}F` : null,
    data.half_baths ? `${data.half_baths}H` : null,
  ].filter(Boolean).join(" / ") || null;
  const classLabel = [data.bldg_class, data.bldg_class_description].filter(Boolean).join(" — ");

  const firstAssessment = data.assessment_history.filter((a) => a.year != null && a.total != null && a.total > 0)
    .sort((a, b) => (a.year! - b.year!))[0];
  const deltaPct = firstAssessment?.total && assessed
    ? Math.round(((assessed - firstAssessment.total) / firstAssessment.total) * 100)
    : null;

  return (
    <Card title={t("property.title")} icon={BuildingIcon} divider>
      <div className="space-y-5">
        {/* The three numbers this card exists for */}
        {(assessed != null || tax != null) && (
          <div className="grid grid-cols-3 gap-3">
            {assessed != null && (
              <div>
                <div className="text-subtitle text-text-primary">{fmtDollar(assessed)}</div>
                <div className="text-caption text-text-muted mt-0.5">{t("property.assessedValue")}</div>
              </div>
            )}
            {tax != null && (
              <div>
                <div className="text-subtitle text-text-primary">{fmtDollar(tax)}</div>
                <div className="text-caption text-text-muted mt-0.5">{t("property.annualTax")}</div>
              </div>
            )}
            {effectiveRate && (
              <div>
                <div className="text-subtitle text-text-primary">{effectiveRate}</div>
                <div className="text-caption text-text-muted mt-0.5">{t("property.effectiveRate")}</div>
              </div>
            )}
          </div>
        )}

        {/* Assessment trajectory — drawn, not a hidden table */}
        {data.assessment_history.length >= 2 && (
          <div>
            <div className="flex items-baseline justify-between mb-1">
              <span className="text-overline uppercase tracking-wider text-text-muted">
                {t("property.assessmentHistory")}
              </span>
              {deltaPct != null && deltaPct !== 0 && (
                <span className={`text-caption ${deltaPct > 0 ? "text-state-positive" : "text-state-negative"}`}>
                  {deltaPct > 0 ? "+" : ""}{deltaPct}%
                </span>
              )}
            </div>
            <AssessmentSparkline history={data.assessment_history} />
          </div>
        )}

        {/* Where the tax bill goes */}
        {data.tax_breakdown.length > 0 && (
          <div>
            <div className="text-overline uppercase tracking-wider text-text-muted mb-2">
              {t("property.taxBreakdown")}
            </div>
            <TaxBars breakdown={data.tax_breakdown} />
          </div>
        )}

        {/* Building facts — scannable grid, nulls omitted */}
        <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-3">
          <Fact label={t("property.class")} value={classLabel || null} />
          <Fact label={t("property.buildingSqft")} value={data.bldg_sqft ? data.bldg_sqft.toLocaleString() : null} />
          <Fact label={t("property.landSqft")} value={data.land_sqft ? data.land_sqft.toLocaleString() : null} />
          <Fact label={t("property.stories")} value={data.stories ? String(data.stories) : null} />
          <Fact label={t("property.units")} value={data.units ? String(data.units) : null} />
          <Fact label={t("property.rooms")} value={data.rooms ? String(data.rooms) : null} />
          <Fact label={t("property.bedrooms")} value={data.bedrooms ? String(data.bedrooms) : null} />
          <Fact label={t("property.baths")} value={baths} />
          <Fact label={t("property.buildingAge")} value={data.bldg_age != null ? `${data.bldg_age} ${t("property.yrs")}` : null} />
        </dl>

        {/* Full records (sales + assessment table) for the verifier persona */}
        {(data.sales_history.length > 0 || data.assessment_history.length > 0) && (
          <div>
            <button
              onClick={() => setShowRecords((s) => !s)}
              className="flex items-center gap-1.5 text-caption text-text-muted hover:text-text-secondary transition-colors"
            >
              <svg className={`w-3 h-3 transition-transform duration-150 ${showRecords ? "" : "-rotate-90"}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
              {t("property.fullRecords")}
            </button>
            {showRecords && (
              <div className="mt-3 grid sm:grid-cols-2 gap-4">
                {data.sales_history.length > 0 && (
                  <RecordTable
                    caption={t("property.salesHistory")}
                    headers={[t("property.date"), t("property.price"), t("property.deed")]}
                    rows={data.sales_history.map((s) => [
                      s.date ? formatDate(s.date) : "—",
                      fmtDollar(s.price),
                      s.deed_type ?? "—",
                    ])}
                  />
                )}
                {data.assessment_history.length > 0 && (
                  <RecordTable
                    caption={t("property.assessmentHistory")}
                    headers={[t("property.year"), t("property.land"), t("property.building"), t("property.total")]}
                    rows={data.assessment_history.map((a) => [
                      a.year != null ? String(a.year) : "—",
                      fmtDollar(a.land),
                      fmtDollar(a.building),
                      fmtDollar(a.total),
                    ])}
                  />
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

function RecordTable({ caption, headers, rows }: { caption: string; headers: string[]; rows: string[][] }) {
  return (
    <div>
      <div className="text-caption text-text-muted mb-1.5">{caption}</div>
      <table className="w-full text-caption">
        <thead>
          <tr className="text-text-muted border-b border-dark-border">
            {headers.map((h) => (
              <th key={h} className="text-left pb-1.5 pr-2 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-dark-border/50">
              {row.map((cell, j) => (
                <td key={j} className={`py-1.5 pr-2 text-text-primary ${j > 0 ? "tabular-nums" : ""}`}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
