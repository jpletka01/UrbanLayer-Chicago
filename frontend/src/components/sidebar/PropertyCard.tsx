import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { PropertySummary } from "../../lib/types";
import { formatDate } from "../../lib/format";
import { CollapsibleCard } from "./CollapsibleCard";
import { ReportTeaser } from "./ReportTeaser";

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
      <span className="text-text-muted text-micro shrink-0">{label}</span>
      <span className="text-text-primary text-micro font-mono text-right">{value}</span>
    </div>
  );
}

function MiniTable({ headers, rows }: { headers: string[]; rows: (string | null)[][] }) {
  return (
    <table className="w-full text-micro">
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

function StatBox({ label, value, naLabel, naTitle }: {
  label: string; value: string | null; naLabel?: string; naTitle?: string;
}) {
  const na = value == null;
  return (
    <div className="text-center">
      <div
        className={`text-sm font-semibold ${na ? "text-text-muted cursor-help" : "text-text-primary"}`}
        title={na ? naTitle : undefined}
      >
        {na ? (naLabel ?? "n/a") : value}
      </div>
      <div className="text-micro text-text-muted mt-0.5">{label}</div>
    </div>
  );
}

export function PropertyCard({ data, scorecardHref }: { data: PropertySummary; scorecardHref?: string | null }) {
  const { t } = useTranslation("data");
  const [showAssessments, setShowAssessments] = useState(false);
  const [showTax, setShowTax] = useState(false);
  const [showSales, setShowSales] = useState(false);

  const baths = [
    data.full_baths ? `${data.full_baths}F` : null,
    data.half_baths ? `${data.half_baths}H` : null,
  ].filter(Boolean).join(" / ") || null;

  const classLabel = [data.bldg_class, data.bldg_class_description].filter(Boolean).join(" — ");

  const assessed = data.total_assessed_value;
  const tax = data.estimated_annual_tax;
  const effectiveRate = assessed && assessed > 0 && tax && tax > 0
    ? `${((tax / (assessed / 0.10)) * 100).toFixed(2)}%`
    : null;

  const hasFinancials = assessed != null || tax != null;

  return (
    <CollapsibleCard title={t("property.title")} icon={BuildingIcon}>
      <div className="space-y-3">
        {hasFinancials && (
          <div className="grid grid-cols-3 gap-2 py-1">
            <StatBox label={t("property.assessedValue")} value={assessed != null ? fmtDollar(assessed) : null}
              naLabel={t("na.value")} naTitle={t("na.title")} />
            <StatBox label={t("property.annualTax")} value={tax != null ? fmtDollar(tax) : null}
              naLabel={t("na.value")} naTitle={t("na.title")} />
            <StatBox label={t("property.effectiveRate")} value={effectiveRate}
              naLabel={t("na.value")} naTitle={t("na.title")} />
          </div>
        )}

        <div className="space-y-1">
          <KV label={t("property.address")} value={data.address} />
          <KV label={t("property.pin")} value={data.pin14} />
          {classLabel && <KV label={t("property.class")} value={classLabel} />}
          {/* zeroes in the assessor characteristics feed are placeholders, not measurements — hide them */}
          <KV label={t("property.buildingSqft")} value={data.bldg_sqft ? fmt(data.bldg_sqft) : null} />
          <KV label={t("property.landSqft")} value={data.land_sqft ? fmt(data.land_sqft) : null} />
          <KV label={t("property.stories")} value={data.stories ? String(data.stories) : null} />
          <KV label={t("property.units")} value={data.units ? String(data.units) : null} />
          <KV label={t("property.rooms")} value={data.rooms ? String(data.rooms) : null} />
          <KV label={t("property.bedrooms")} value={data.bedrooms ? String(data.bedrooms) : null} />
          <KV label={t("property.baths")} value={baths} />
          <KV label={t("property.buildingAge")} value={data.bldg_age != null ? `${data.bldg_age} ${t("property.yrs")}` : null} />
        </div>

        {data.assessment_history.length > 0 && (
          <div>
            <button
              onClick={() => setShowAssessments(a => !a)}
              className="flex items-center gap-1.5 text-micro text-text-muted hover:text-text-secondary transition-colors"
            >
              <svg
                className={`w-2.5 h-2.5 transition-transform duration-150 ${showAssessments ? "" : "-rotate-90"}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
              {t("property.assessmentHistory")} ({t("property.yrsCount", { count: data.assessment_history.length })})
            </button>
            {showAssessments && (
              <div className="mt-1.5">
                <MiniTable
                  headers={[t("property.year"), t("property.land"), t("property.building"), t("property.total")]}
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

        {data.sales_history.length > 0 && (
          <div>
            <button
              onClick={() => setShowSales(s => !s)}
              className="flex items-center gap-1.5 text-micro text-text-muted hover:text-text-secondary transition-colors"
            >
              <svg
                className={`w-2.5 h-2.5 transition-transform duration-150 ${showSales ? "" : "-rotate-90"}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
              {t("property.salesHistory")} ({data.sales_history.length})
            </button>
            {showSales && (
              <div className="mt-1.5">
                <MiniTable
                  headers={[t("property.date"), t("property.price"), t("property.deed")]}
                  rows={data.sales_history.map(s => [
                    s.date ? formatDate(s.date) : null,
                    fmtDollar(s.price),
                    s.deed_type,
                  ])}
                />
              </div>
            )}
          </div>
        )}

        {data.estimated_annual_tax != null && (
          <div>
            <div className="flex items-center justify-between text-micro">
              <span className="text-text-muted">{t("property.estAnnualTax")}</span>
              <span className="font-medium text-text-primary">{fmtDollar(data.estimated_annual_tax)}</span>
            </div>
            {data.tax_breakdown.length > 0 && (
              <>
                <button
                  onClick={() => setShowTax(tx => !tx)}
                  className="flex items-center gap-1.5 text-micro text-text-muted hover:text-text-secondary transition-colors mt-1"
                >
                  <svg
                    className={`w-2.5 h-2.5 transition-transform duration-150 ${showTax ? "" : "-rotate-90"}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                  {t("property.taxBreakdown")} ({t("property.agencies", { count: data.tax_breakdown.length })})
                </button>
                {showTax && (
                  <div className="mt-1.5">
                    <MiniTable
                      headers={[t("property.agency"), t("property.rate"), t("property.amount")]}
                      rows={data.tax_breakdown.map(tb => [
                        tb.agency,
                        `${tb.rate.toFixed(3)}%`,
                        fmtDollar(tb.amount),
                      ])}
                    />
                  </div>
                )}
              </>
            )}
          </div>
        )}
        <ReportTeaser text={t("property.reportTeaser")} href={scorecardHref} />
      </div>
    </CollapsibleCard>
  );
}
