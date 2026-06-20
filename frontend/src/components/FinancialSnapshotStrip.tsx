import { useTranslation } from "react-i18next";
import type { PropertySummary, ComparablesSummary, IncentivesSummary } from "../lib/types";

function fmtDollar(n: number | null | undefined): string {
  if (n == null) return "";
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString()}`;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center min-w-[80px]">
      <div className="text-sm font-semibold text-text-primary font-mono">{value}</div>
      <div className="text-micro text-text-muted uppercase tracking-wider mt-0.5">{label}</div>
    </div>
  );
}

interface Props {
  property?: PropertySummary | null;
  comparables?: ComparablesSummary | null;
  incentives?: IncentivesSummary | null;
}

export function FinancialSnapshotStrip({ property, comparables, incentives }: Props) {
  const { t } = useTranslation("data");

  const metrics: { label: string; value: string }[] = [];

  if (property?.total_assessed_value != null) {
    metrics.push({ label: t("financialSnapshot.assessedValue"), value: fmtDollar(property.total_assessed_value) });
  }
  if (property?.estimated_annual_tax != null) {
    metrics.push({ label: t("financialSnapshot.annualTax"), value: fmtDollar(property.estimated_annual_tax) });
  }
  if (comparables?.median_sale_price != null) {
    metrics.push({ label: t("financialSnapshot.medianCompSale"), value: fmtDollar(comparables.median_sale_price) });
  }
  if (incentives?.in_tif_district && incentives.tif_fund_balance != null) {
    metrics.push({ label: t("financialSnapshot.tifFundBalance"), value: fmtDollar(incentives.tif_fund_balance) });
  }

  const zoneCount = [incentives?.in_tif_district, incentives?.in_opportunity_zone, incentives?.in_enterprise_zone, incentives?.in_qct, incentives?.in_nmtc].filter(Boolean).length;
  if (zoneCount > 0) {
    metrics.push({ label: t("financialSnapshot.activeIncentives"), value: t("financialSnapshot.zonesCount", { count: zoneCount }) });
  }

  if (metrics.length < 2) return null;

  return (
    <div className="rounded-xl bg-dark-surface/60 border border-dark-border px-4 py-3 mb-6">
      <div className="flex flex-wrap gap-x-6 gap-y-2 justify-around">
        {metrics.map((m) => (
          <Metric key={m.label} label={m.label} value={m.value} />
        ))}
      </div>
    </div>
  );
}
