import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { ComparablesSummary } from "../../lib/types";
import { formatDate } from "../../lib/format";
import { CollapsibleCard } from "./CollapsibleCard";
import { ReportTeaser } from "./ReportTeaser";

const ChartIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
  </svg>
);

function fmtDollar(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString()}`;
}

function fmtDollarFull(n: number | null | undefined): string {
  if (n == null) return "—";
  return `$${n.toLocaleString()}`;
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
      <div className="text-[10px] text-text-muted mt-0.5">{label}</div>
    </div>
  );
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

export function ComparablesCard({ data }: { data: ComparablesSummary }) {
  const { t } = useTranslation("data");
  const [showSales, setShowSales] = useState(false);

  if (!data.sales || data.sales.length === 0) {
    return (
      <CollapsibleCard title={t("comparables.title")} icon={ChartIcon}>
        <p className="text-[11px] text-text-muted">{t("comparables.noData")}</p>
      </CollapsibleCard>
    );
  }

  const rangeStr = data.price_range_min != null && data.price_range_max != null
    ? `${fmtDollar(data.price_range_min)} — ${fmtDollar(data.price_range_max)}`
    : null;

  return (
    <CollapsibleCard title={t("comparables.title")} icon={ChartIcon}>
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-2 py-1">
          <StatBox label={t("comparables.medianPrice")} value={data.median_sale_price != null ? fmtDollar(data.median_sale_price) : null}
            naLabel={t("na.value")} naTitle={t("na.title")} />
          <StatBox label={t("comparables.priceLandSqft")} value={data.median_price_per_land_sqft != null ? `$${data.median_price_per_land_sqft.toFixed(0)}` : null}
            naLabel={t("na.value")} naTitle={t("na.title")} />
          <StatBox label={t("comparables.salesVolume")} value={String(data.sales_volume)} />
        </div>

        <div className="space-y-1">
          <KV label={t("comparables.priceRange")} value={rangeStr} />
          <KV label={t("comparables.priceBldgSqft")} value={data.median_price_per_bldg_sqft != null ? `$${data.median_price_per_bldg_sqft.toFixed(0)}` : null} />
        </div>

        <p className="text-[10px] text-text-muted">{t("comparables.radius")}</p>

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
            {t("comparables.recentSales")} ({data.sales.length})
          </button>
          {showSales && (
            <div className="mt-1.5 overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-text-muted border-b border-dark-border">
                    <th className="text-left pb-1.5 pr-2 font-medium">{t("comparables.date")}</th>
                    <th className="text-left pb-1.5 pr-2 font-medium">{t("comparables.price")}</th>
                    <th className="text-left pb-1.5 pr-2 font-medium">{t("comparables.distance")}</th>
                    <th className="text-left pb-1.5 font-medium">{t("comparables.priceSqft")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.sales.map((sale, i) => (
                    <tr key={i} className="border-t border-dark-border/50">
                      <td className="py-1 pr-2 text-text-primary">
                        {sale.sale_date ? formatDate(sale.sale_date) : "—"}
                      </td>
                      <td className="py-1 pr-2 font-mono text-text-primary">
                        {fmtDollarFull(sale.sale_price)}
                      </td>
                      <td className="py-1 pr-2 font-mono text-text-primary">
                        {sale.distance_mi != null ? `${sale.distance_mi.toFixed(2)} mi` : "—"}
                      </td>
                      <td className="py-1 font-mono text-text-primary">
                        {sale.price_per_bldg_sqft != null ? `$${sale.price_per_bldg_sqft.toFixed(0)}` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <ReportTeaser text={t("comparables.reportTeaser")} />
      </div>
    </CollapsibleCard>
  );
}
