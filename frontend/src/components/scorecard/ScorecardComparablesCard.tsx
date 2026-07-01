// Page-scale Comparables card. Leads with the median, draws the sales as a price
// strip (dot plot on a price axis — single series, one hue, ring-marked dots per
// the dataviz method), and keeps the full table behind one disclosure. The subject's
// assessed value is deliberately NOT plotted: assessed ≠ market price, and putting
// them on one axis would misstate the comparison.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { ComparablesSummary } from "../../lib/types";
import { formatDate } from "../../lib/format";
import { Card } from "../ui/Card";

const ChartIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
  </svg>
);

function fmtFull(n: number | null | undefined): string {
  if (n == null) return "—";
  return `$${Math.round(n).toLocaleString()}`;
}
function fmtCompact(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n)}`;
}

/** Dot plot of sale prices on a price axis; median marked with a hairline. */
function PriceStrip({ data }: { data: ComparablesSummary }) {
  const { t } = useTranslation("data");
  const prices = data.sales.map((s) => s.sale_price).filter((p): p is number => p != null && p > 0);
  if (prices.length < 3) return null;
  const min = Math.min(...prices), max = Math.max(...prices);
  if (max === min) return null;
  const W = 560, H = 36, PX = 10;
  const x = (p: number) => PX + ((p - min) / (max - min)) * (W - 2 * PX);
  const median = data.median_sale_price;
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-9" aria-hidden>
        <line x1={PX} y1={H / 2} x2={W - PX} y2={H / 2} stroke="rgb(var(--border))" strokeWidth="1" />
        {median != null && (
          <line x1={x(median)} y1={4} x2={x(median)} y2={H - 4} stroke="rgb(var(--text-muted))" strokeWidth="1" strokeDasharray="3 3" />
        )}
        {prices.map((p, i) => (
          <circle key={i} cx={x(p)} cy={H / 2} r="5"
            fill="rgb(var(--accent))" stroke="rgb(var(--surface))" strokeWidth="2">
            <title>{fmtFull(p)}</title>
          </circle>
        ))}
      </svg>
      <div className="flex justify-between text-caption text-text-muted mt-0.5">
        <span>{fmtCompact(min)}</span>
        {median != null && <span className="text-text-secondary">{t("comparables.medianPrice")} {fmtCompact(median)}</span>}
        <span>{fmtCompact(max)}</span>
      </div>
    </div>
  );
}

export function ScorecardComparablesCard({ data }: { data: ComparablesSummary }) {
  const { t } = useTranslation("data");
  const [showSales, setShowSales] = useState(false);

  if (!data.sales || data.sales.length === 0) {
    return (
      <Card title={t("comparables.title")} icon={ChartIcon} divider>
        <p className="text-body text-text-muted">{t("comparables.noData")}</p>
      </Card>
    );
  }

  return (
    <Card
      title={t("comparables.title")}
      icon={ChartIcon}
      headerRight={<span className="text-caption text-text-muted">{t("comparables.radius")}</span>}
      divider
    >
      <div className="space-y-4">
        {data.median_sale_price != null && (
          <div>
            <div className="text-subtitle text-text-primary">{fmtFull(data.median_sale_price)}</div>
            <div className="text-caption text-text-muted mt-0.5">
              {t("comparables.medianPrice")} · {t("comparables.salesVolume")}: {data.sales_volume}
            </div>
          </div>
        )}

        <PriceStrip data={data} />

        <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
          {data.median_price_per_land_sqft != null && (
            <div>
              <dt className="text-caption text-text-muted">{t("comparables.priceLandSqft")}</dt>
              <dd className="text-body text-text-primary mt-0.5">${data.median_price_per_land_sqft.toFixed(0)}</dd>
            </div>
          )}
          {data.median_price_per_bldg_sqft != null && (
            <div>
              <dt className="text-caption text-text-muted">{t("comparables.priceBldgSqft")}</dt>
              <dd className="text-body text-text-primary mt-0.5">${data.median_price_per_bldg_sqft.toFixed(0)}</dd>
            </div>
          )}
        </dl>

        <div>
          <button
            onClick={() => setShowSales((s) => !s)}
            className="flex items-center gap-1.5 text-caption text-text-muted hover:text-text-secondary transition-colors"
          >
            <svg className={`w-3 h-3 transition-transform duration-150 ${showSales ? "" : "-rotate-90"}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
            {t("comparables.recentSales")} ({data.sales.length})
          </button>
          {showSales && (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-caption">
                <thead>
                  <tr className="text-text-muted border-b border-dark-border">
                    <th className="text-left pb-1.5 pr-2 font-medium">{t("comparables.date")}</th>
                    <th className="text-left pb-1.5 pr-2 font-medium">{t("comparables.price")}</th>
                    <th className="text-left pb-1.5 pr-2 font-medium">{t("comparables.class")}</th>
                    <th className="text-left pb-1.5 font-medium">{t("comparables.priceSqft")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.sales.map((sale, i) => (
                    <tr key={i} className="border-t border-dark-border/50">
                      <td className="py-1.5 pr-2 text-text-primary">{sale.sale_date ? formatDate(sale.sale_date) : "—"}</td>
                      <td className="py-1.5 pr-2 text-text-primary tabular-nums">{fmtFull(sale.sale_price)}</td>
                      <td className="py-1.5 pr-2 text-text-secondary">{sale.class_code ?? "—"}</td>
                      <td className="py-1.5 text-text-primary tabular-nums">
                        {sale.price_per_bldg_sqft != null ? `$${sale.price_per_bldg_sqft.toFixed(0)}` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
