import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { MapData } from "../../lib/types";
import type { LandingSource } from "./DataSourceTabs";
import { computePieSlices, computeTrends, getTrendMonthLabels } from "../../lib/analytics";
import { crimeColorCSS, srTypeMapColorCSS, permitColorCSS } from "../../lib/mapColors";
import { PieChart } from "../sidebar/PieChart";
import { TrendTable } from "../sidebar/TrendTable";
import { CountUp } from "../CountUp";

interface Props {
  mapData: MapData;
  source: LandingSource;
}

const commaFmt = (n: number) => n.toLocaleString("en-US");

export function LandingAnalytics({ mapData, source }: Props) {
  const { t } = useTranslation("landing");
  const showCrime = source === "all" || source === "crime";
  const show311 = source === "all" || source === "311";
  const showPermits = source === "all" || source === "permits";

  const crimeSlices = useMemo(
    () => showCrime ? computePieSlices(mapData.crimes, (r) => r.primary_type, crimeColorCSS) : [],
    [mapData.crimes, showCrime],
  );
  const crimeTrends = useMemo(
    () => showCrime ? computeTrends(mapData.crimes, (r) => r.date, (r) => r.primary_type, crimeColorCSS) : [],
    [mapData.crimes, showCrime],
  );
  const crimeLabels = useMemo(
    () => showCrime ? getTrendMonthLabels(mapData.crimes, (r) => r.date) : null,
    [mapData.crimes, showCrime],
  );

  const srSlices = useMemo(
    () => show311 ? computePieSlices(mapData.requests_311, (r) => r.sr_type, srTypeMapColorCSS) : [],
    [mapData.requests_311, show311],
  );

  const permitSlices = useMemo(
    () => showPermits ? computePieSlices(mapData.building_permits, (r) => r.permit_type, permitColorCSS) : [],
    [mapData.building_permits, showPermits],
  );

  const totalCrimes = mapData.crimes.length;
  const total311 = mapData.requests_311.length;
  const totalPermits = mapData.building_permits.length;
  const arrestRate = totalCrimes > 0
    ? mapData.crimes.filter((c) => c.arrest === true || c.arrest === "true").length / totalCrimes
    : 0;

  // Decide which dataset to feature in pie + trend
  const activePie = showCrime && crimeSlices.length > 0
    ? crimeSlices
    : show311 && srSlices.length > 0
      ? srSlices
      : permitSlices;

  const activeBreakdownKey = showCrime && crimeSlices.length > 0
    ? "crimeBreakdown"
    : show311 && srSlices.length > 0
      ? "311Breakdown"
      : "permitsBreakdown";

  return (
    <div className="space-y-6">
      {/* Stat badges */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {showCrime && totalCrimes > 0 && (
          <StatBadge label={t("explorer.crimes")} value={totalCrimes} color="text-red-400" />
        )}
        {showCrime && totalCrimes > 0 && (
          <StatBadge label={t("explorer.arrestRate")} value={Math.round(arrestRate * 100)} suffix="%" color="text-amber-400" />
        )}
        {show311 && total311 > 0 && (
          <StatBadge label={t("explorer.311requests")} value={total311} color="text-teal-400" />
        )}
        {showPermits && totalPermits > 0 && (
          <StatBadge label={t("explorer.permits")} value={totalPermits} color="text-green-400" />
        )}
      </div>

      {/* Pie chart + Trend table side by side */}
      {activePie.length > 0 && (
        <div className="space-y-4">
          <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider">
            {t(`explorer.${activeBreakdownKey}`)}
          </h4>
          <div className="flex flex-col md:flex-row gap-6 items-start">
            <div className="flex-shrink-0">
              <PieChart slices={activePie} size={180} />
            </div>
            {crimeTrends.length > 0 && crimeLabels && showCrime && (
              <div className="flex-1 min-w-0">
                <TrendTable rows={crimeTrends.slice(0, 8)} currentLabel={crimeLabels.current} priorLabel={crimeLabels.prior} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function StatBadge({ label, value, suffix, color }: { label: string; value: number; suffix?: string; color: string }) {
  return (
    <div className="bg-dark-elevated border border-dark-border rounded-lg p-4 text-center">
      <div className={`text-2xl font-semibold ${color}`}>
        <CountUp to={value} format={suffix ? undefined : commaFmt} duration={1} />
        {suffix}
      </div>
      <div className="text-xs text-text-muted mt-1 uppercase tracking-wider">{label}</div>
    </div>
  );
}
