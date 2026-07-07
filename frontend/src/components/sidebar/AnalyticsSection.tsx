import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { MapData, ContextObject } from "../../lib/types";
import type { FilterMode } from "../../lib/mapColors";
import { deptColorCSS, normalizeDept, crimeColorCSS, srTypeMapColorCSS, permitColorCSS, normalizePermitType } from "../../lib/mapColors";
import { computeTrends, computePieSlices, getTrendMonthLabels } from "../../lib/analytics";
import { PieChart } from "./PieChart";
import { TrendTable } from "./TrendTable";
import { exportCSV, buildFilenameSlug } from "../../lib/csvExport";

type ThreeOneOneGrouping = "sr_type" | "department";

interface Props {
  mapData?: MapData | null;
  filterMode: FilterMode;
  context?: ContextObject | null;
}

function fmtNum(n: number): string {
  return n.toLocaleString();
}

function fmtDollar(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString()}`;
}

function StatPill({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <span className="inline-flex items-center gap-1 bg-dark-elevated/60 rounded-md px-2 py-0.5">
      <span className="text-micro text-text-muted">{label}</span>
      <span className={`text-micro font-mono font-medium ${color ?? "text-text-primary"}`}>{value}</span>
    </span>
  );
}

export function AnalyticsSection({ mapData, filterMode, context }: Props) {
  const { t } = useTranslation("data");
  const [collapsed, setCollapsed] = useState(false);
  const [threeOneOneGrouping, setThreeOneOneGrouping] = useState<ThreeOneOneGrouping>("sr_type");

  const crimeSummary = context?.crime_last_90d ?? null;
  const threeOneOneSummary = context?.open_311_requests ?? null;
  const permitSummary = context?.permits ?? null;

  const crimeAnalytics = useMemo(() => {
    if (!mapData?.crimes?.length) return null;
    const capped = !!mapData.capped?.crimes;
    return {
      trends: computeTrends(mapData.crimes, c => c.date, c => c.primary_type, crimeColorCSS, capped),
      pie: computePieSlices(mapData.crimes, c => c.primary_type, crimeColorCSS),
      monthLabels: getTrendMonthLabels(mapData.crimes, c => c.date, capped),
    };
  }, [mapData?.crimes, mapData?.capped?.crimes]);

  const threeOneOneAnalytics = useMemo(() => {
    if (!mapData?.requests_311?.length) return null;
    const getCategory = threeOneOneGrouping === "sr_type"
      ? (r: (typeof mapData.requests_311)[0]) => r.sr_type
      : (r: (typeof mapData.requests_311)[0]) => normalizeDept(r.owner_department);
    const colorFn = threeOneOneGrouping === "sr_type" ? srTypeMapColorCSS : deptColorCSS;
    const capped = !!mapData.capped?.requests_311;
    return {
      trends: computeTrends(mapData.requests_311, r => r.created_date, getCategory, colorFn, capped),
      pie: computePieSlices(mapData.requests_311, getCategory, colorFn),
      monthLabels: getTrendMonthLabels(mapData.requests_311, r => r.created_date, capped),
    };
  }, [mapData?.requests_311, threeOneOneGrouping, mapData?.capped?.requests_311]);

  const permitAnalytics = useMemo(() => {
    if (!mapData?.building_permits?.length) return null;
    const getType = (p: (typeof mapData.building_permits)[0]) => normalizePermitType(p.permit_type);
    const capped = !!mapData.capped?.building_permits;
    return {
      trends: computeTrends(mapData.building_permits, p => p.issue_date, getType, permitColorCSS, capped),
      pie: computePieSlices(mapData.building_permits, getType, permitColorCSS),
      monthLabels: getTrendMonthLabels(mapData.building_permits, p => p.issue_date, capped),
    };
  }, [mapData?.building_permits, mapData?.capped?.building_permits]);

  const hasAnalytics = crimeAnalytics || threeOneOneAnalytics || permitAnalytics
    || crimeSummary || threeOneOneSummary || permitSummary;
  if (!hasAnalytics) return null;

  const showCrime = (filterMode === "crime" || filterMode === "overview") && (crimeAnalytics || crimeSummary);
  const show311 = (filterMode === "311" || filterMode === "overview") && (threeOneOneAnalytics || threeOneOneSummary);
  const showPermits = (filterMode === "permits" || filterMode === "overview") && (permitAnalytics || permitSummary);

  return (
    <div className="rounded-xl bg-dark-surface border border-dark-border overflow-hidden">
      <button
        onClick={() => setCollapsed(c => !c)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-xs font-medium text-text-muted
                   uppercase tracking-wider hover:text-text-secondary transition-colors"
      >
        <svg
          className={`w-3 h-3 transition-transform duration-200 ${collapsed ? "-rotate-90" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
        {t("analytics.title")}
      </button>

      {!collapsed && (
        <div className="px-4 pb-4 space-y-5">
          {showCrime && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-micro font-medium text-text-muted uppercase tracking-wider">{t("analytics.crime")}</h4>
                {mapData?.crimes && mapData.crimes.length > 0 && (
                  <button
                    onClick={() => {
                      const slug = buildFilenameSlug(context?.community_area_name || "chicago");
                      const date = new Date().toISOString().slice(0, 10);
                      exportCSV(mapData!.crimes, `${slug}_crimes_${date}.csv`, [
                        { key: "latitude", header: "Latitude" },
                        { key: "longitude", header: "Longitude" },
                        { key: "primary_type", header: "Type" },
                        { key: "description", header: "Description" },
                        { key: "date", header: "Date" },
                        { key: "arrest", header: "Arrest" },
                      ]);
                    }}
                    className="text-micro text-accent hover:text-accent-hover transition-colors"
                  >
                    {t("analytics.exportCsv")}
                  </button>
                )}
              </div>
              {crimeSummary && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  <StatPill label={t("analytics.totalStat")} value={fmtNum(crimeSummary.total)} />
                  <StatPill label={t("analytics.arrestRate")} value={`${(crimeSummary.arrest_rate * 100).toFixed(1)}%`} />
                </div>
              )}
              {crimeAnalytics && (
                <div className="space-y-3">
                  {crimeAnalytics.monthLabels && crimeAnalytics.trends.length > 0 && (
                    <TrendTable rows={crimeAnalytics.trends} currentLabel={crimeAnalytics.monthLabels.current} priorLabel={crimeAnalytics.monthLabels.prior} />
                  )}
                  {crimeAnalytics.pie.length > 0 && <PieChart slices={crimeAnalytics.pie} />}
                  {!crimeAnalytics.monthLabels && crimeAnalytics.pie.length > 0 && (
                    <p className="text-micro text-text-muted">{t("analytics.notEnoughData")}</p>
                  )}
                </div>
              )}
              {crimeSummary?.capped && (
                <p className="text-micro text-text-muted italic mt-1">{t("analytics.cappedCrime")}</p>
              )}
            </div>
          )}

          {show311 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-micro font-medium text-text-muted uppercase tracking-wider">{t("analytics.311Requests")}</span>
                <span className="flex items-center gap-2">
                  {mapData?.requests_311 && mapData.requests_311.length > 0 && (
                    <button
                      onClick={() => {
                        const slug = buildFilenameSlug(context?.community_area_name || "chicago");
                        const date = new Date().toISOString().slice(0, 10);
                        exportCSV(mapData!.requests_311, `${slug}_311_requests_${date}.csv`, [
                          { key: "latitude", header: "Latitude" },
                          { key: "longitude", header: "Longitude" },
                          { key: "sr_type", header: "Type" },
                          { key: "status", header: "Status" },
                          { key: "created_date", header: "Date" },
                          { key: "owner_department", header: "Department" },
                        ]);
                      }}
                      className="text-micro text-accent hover:text-accent-hover transition-colors"
                    >
                      {t("analytics.exportCsv")}
                    </button>
                  )}
                {threeOneOneAnalytics && (
                  <div className="flex bg-dark-bg/60 rounded-md overflow-hidden border border-dark-border">
                    <button
                      onClick={() => setThreeOneOneGrouping("sr_type")}
                      className={`px-2 py-0.5 text-micro font-medium transition-colors ${
                        threeOneOneGrouping === "sr_type"
                          ? "bg-dark-elevated text-text-primary"
                          : "text-text-muted hover:text-text-secondary"
                      }`}
                    >
                      {t("analytics.type")}
                    </button>
                    <button
                      onClick={() => setThreeOneOneGrouping("department")}
                      className={`px-2 py-0.5 text-micro font-medium border-l border-dark-border transition-colors ${
                        threeOneOneGrouping === "department"
                          ? "bg-dark-elevated text-text-primary"
                          : "text-text-muted hover:text-text-secondary"
                      }`}
                    >
                      {t("analytics.dept")}
                    </button>
                  </div>
                )}
                </span>
              </div>
              {threeOneOneSummary && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  <StatPill label={t("analytics.openStat")} value={fmtNum(threeOneOneSummary.total)} />
                  {threeOneOneSummary.oldest_open_days != null && (
                    <StatPill
                      label={t("analytics.oldest")}
                      value={threeOneOneSummary.oldest_open_days >= 365
                        ? `${(threeOneOneSummary.oldest_open_days / 365).toFixed(1)}yr`
                        : `${threeOneOneSummary.oldest_open_days}d`}
                    />
                  )}
                </div>
              )}
              {threeOneOneAnalytics && (
                <div className="space-y-3">
                  {threeOneOneAnalytics.monthLabels && threeOneOneAnalytics.trends.length > 0 && (
                    <TrendTable
                      rows={threeOneOneAnalytics.trends}
                      currentLabel={threeOneOneAnalytics.monthLabels.current}
                      priorLabel={threeOneOneAnalytics.monthLabels.prior}
                    />
                  )}
                  {threeOneOneAnalytics.pie.length > 0 && (
                    <PieChart slices={threeOneOneAnalytics.pie} />
                  )}
                  {!threeOneOneAnalytics.monthLabels && threeOneOneAnalytics.pie.length > 0 && (
                    <p className="text-micro text-text-muted">{t("analytics.notEnoughData")}</p>
                  )}
                </div>
              )}
              {threeOneOneSummary?.capped && (
                <p className="text-micro text-text-muted italic mt-1">{t("analytics.capped311")}</p>
              )}
            </div>
          )}

          {showPermits && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-micro font-medium text-text-muted uppercase tracking-wider">{t("analytics.buildingPermits")}</h4>
                {mapData?.building_permits && mapData.building_permits.length > 0 && (
                  <button
                    onClick={() => {
                      const slug = buildFilenameSlug(context?.community_area_name || "chicago");
                      const date = new Date().toISOString().slice(0, 10);
                      exportCSV(mapData!.building_permits, `${slug}_permits_${date}.csv`, [
                        { key: "latitude", header: "Latitude" },
                        { key: "longitude", header: "Longitude" },
                        { key: "permit_type", header: "Type" },
                        { key: "work_description", header: "Description" },
                        { key: "estimated_cost", header: "Estimated Cost" },
                        { key: "issue_date", header: "Date" },
                      ]);
                    }}
                    className="text-micro text-accent hover:text-accent-hover transition-colors"
                  >
                    {t("analytics.exportCsv")}
                  </button>
                )}
              </div>
              {permitSummary && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  <StatPill label={t("analytics.totalStat")} value={fmtNum(permitSummary.total)} />
                  {permitSummary.total_estimated_cost > 0 && (
                    <StatPill label={t("analytics.estCost")} value={fmtDollar(permitSummary.total_estimated_cost)} />
                  )}
                </div>
              )}
              {permitAnalytics && (
                <div className="space-y-3">
                  {permitAnalytics.monthLabels && permitAnalytics.trends.length > 0 && (
                    <TrendTable rows={permitAnalytics.trends} currentLabel={permitAnalytics.monthLabels.current} priorLabel={permitAnalytics.monthLabels.prior} />
                  )}
                  {permitAnalytics.pie.length > 0 && <PieChart slices={permitAnalytics.pie} />}
                  {!permitAnalytics.monthLabels && permitAnalytics.pie.length > 0 && (
                    <p className="text-micro text-text-muted">{t("analytics.notEnoughData")}</p>
                  )}
                </div>
              )}
              {permitSummary?.capped && (
                <p className="text-micro text-text-muted italic mt-1">{t("analytics.cappedPermits")}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

