import { useMemo, useState } from "react";
import type { MapData, ContextObject } from "../../lib/types";
import type { FilterMode } from "../../lib/mapColors";
import { deptColorCSS, normalizeDept, crimeColorCSS, srTypeMapColorCSS, permitColorCSS, normalizePermitType } from "../../lib/mapColors";
import { computeTrends, computePieSlices, getTrendMonthLabels } from "../../lib/analytics";
import { PieChart } from "./PieChart";
import { TrendTable } from "./TrendTable";

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
      <span className="text-[10px] text-text-muted">{label}</span>
      <span className={`text-[11px] font-mono font-medium ${color ?? "text-text-primary"}`}>{value}</span>
    </span>
  );
}

export function AnalyticsSection({ mapData, filterMode, context }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [threeOneOneGrouping, setThreeOneOneGrouping] = useState<ThreeOneOneGrouping>("sr_type");

  const crimeSummary = context?.crime_last_90d ?? null;
  const threeOneOneSummary = context?.open_311_requests ?? null;
  const permitSummary = context?.permits ?? null;

  const crimeAnalytics = useMemo(() => {
    if (!mapData?.crimes?.length) return null;
    return {
      trends: computeTrends(mapData.crimes, c => c.date, c => c.primary_type, crimeColorCSS),
      pie: computePieSlices(mapData.crimes, c => c.primary_type, crimeColorCSS),
      monthLabels: getTrendMonthLabels(mapData.crimes, c => c.date),
    };
  }, [mapData?.crimes]);

  const threeOneOneAnalytics = useMemo(() => {
    if (!mapData?.requests_311?.length) return null;
    const getCategory = threeOneOneGrouping === "sr_type"
      ? (r: (typeof mapData.requests_311)[0]) => r.sr_type
      : (r: (typeof mapData.requests_311)[0]) => normalizeDept(r.owner_department);
    const colorFn = threeOneOneGrouping === "sr_type" ? srTypeMapColorCSS : deptColorCSS;
    return {
      trends: computeTrends(mapData.requests_311, r => r.created_date, getCategory, colorFn),
      pie: computePieSlices(mapData.requests_311, getCategory, colorFn),
      monthLabels: getTrendMonthLabels(mapData.requests_311, r => r.created_date),
    };
  }, [mapData?.requests_311, threeOneOneGrouping]);

  const permitAnalytics = useMemo(() => {
    if (!mapData?.building_permits?.length) return null;
    const getType = (p: (typeof mapData.building_permits)[0]) => normalizePermitType(p.permit_type);
    return {
      trends: computeTrends(mapData.building_permits, p => p.issue_date, getType, permitColorCSS),
      pie: computePieSlices(mapData.building_permits, getType, permitColorCSS),
      monthLabels: getTrendMonthLabels(mapData.building_permits, p => p.issue_date),
    };
  }, [mapData?.building_permits]);

  const hasAnalytics = crimeAnalytics || threeOneOneAnalytics || permitAnalytics
    || crimeSummary || threeOneOneSummary || permitSummary;
  if (!hasAnalytics) return null;

  const showCrime = (filterMode === "crime" || filterMode === "overview") && (crimeAnalytics || crimeSummary);
  const show311 = (filterMode === "311" || filterMode === "overview") && (threeOneOneAnalytics || threeOneOneSummary);
  const showPermits = (filterMode === "permits" || filterMode === "overview") && (permitAnalytics || permitSummary);

  return (
    <div className="rounded-xl bg-dark-surface/80 backdrop-blur-sm border border-dark-border overflow-hidden">
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
        Analytics
      </button>

      {!collapsed && (
        <div className="px-4 pb-4 space-y-5">
          {showCrime && (
            <div>
              <h4 className="text-[11px] font-medium text-text-muted uppercase tracking-wider mb-2">Crime</h4>
              {crimeSummary && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  <StatPill label="Total" value={fmtNum(crimeSummary.total)} />
                  <StatPill label="Arrest Rate" value={`${(crimeSummary.arrest_rate * 100).toFixed(1)}%`} />
                </div>
              )}
              {crimeAnalytics && (
                <div className="space-y-3">
                  {crimeAnalytics.monthLabels && crimeAnalytics.trends.length > 0 && (
                    <TrendTable rows={crimeAnalytics.trends} currentLabel={crimeAnalytics.monthLabels.current} priorLabel={crimeAnalytics.monthLabels.prior} />
                  )}
                  {crimeAnalytics.pie.length > 0 && <PieChart slices={crimeAnalytics.pie} />}
                  {!crimeAnalytics.monthLabels && crimeAnalytics.pie.length > 0 && (
                    <p className="text-[10px] text-text-muted">Not enough data for month-over-month trends.</p>
                  )}
                </div>
              )}
              {crimeSummary?.capped && (
                <p className="text-[10px] text-text-muted italic mt-1">Data capped — more incidents may exist.</p>
              )}
            </div>
          )}

          {show311 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-medium text-text-muted uppercase tracking-wider">311 Requests</span>
                {threeOneOneAnalytics && (
                  <div className="flex bg-dark-bg/60 rounded-md overflow-hidden border border-dark-border">
                    <button
                      onClick={() => setThreeOneOneGrouping("sr_type")}
                      className={`px-2 py-0.5 text-[10px] font-medium transition-colors ${
                        threeOneOneGrouping === "sr_type"
                          ? "bg-dark-elevated text-text-primary"
                          : "text-text-muted hover:text-text-secondary"
                      }`}
                    >
                      Type
                    </button>
                    <button
                      onClick={() => setThreeOneOneGrouping("department")}
                      className={`px-2 py-0.5 text-[10px] font-medium border-l border-dark-border transition-colors ${
                        threeOneOneGrouping === "department"
                          ? "bg-dark-elevated text-text-primary"
                          : "text-text-muted hover:text-text-secondary"
                      }`}
                    >
                      Dept
                    </button>
                  </div>
                )}
              </div>
              {threeOneOneSummary && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  <StatPill label="Open" value={fmtNum(threeOneOneSummary.total)} />
                  {threeOneOneSummary.oldest_open_days != null && (
                    <StatPill
                      label="Oldest"
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
                    <p className="text-[10px] text-text-muted">Not enough data for month-over-month trends.</p>
                  )}
                </div>
              )}
              {threeOneOneSummary?.capped && (
                <p className="text-[10px] text-text-muted italic mt-1">Data capped — more requests may exist.</p>
              )}
            </div>
          )}

          {showPermits && (
            <div>
              <h4 className="text-[11px] font-medium text-text-muted uppercase tracking-wider mb-2">Building Permits</h4>
              {permitSummary && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  <StatPill label="Total" value={fmtNum(permitSummary.total)} />
                  {permitSummary.total_estimated_cost > 0 && (
                    <StatPill label="Est. Cost" value={fmtDollar(permitSummary.total_estimated_cost)} />
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
                    <p className="text-[10px] text-text-muted">Not enough data for month-over-month trends.</p>
                  )}
                </div>
              )}
              {permitSummary?.capped && (
                <p className="text-[10px] text-text-muted italic mt-1">Data capped — more permits may exist.</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

