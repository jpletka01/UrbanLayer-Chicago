import { useMemo, useState } from "react";
import type { MapData } from "../../lib/types";
import type { FilterMode } from "../../lib/mapColors";
import { deptColorCSS, normalizeDept, crimeColorCSS, srTypeMapColorCSS, permitColorCSS, normalizePermitType } from "../../lib/mapColors";
import { computeTrends, computePieSlices, getTrendMonthLabels } from "../../lib/analytics";
import { PieChart } from "./PieChart";
import { TrendTable } from "./TrendTable";

type ThreeOneOneGrouping = "sr_type" | "department";

interface Props {
  mapData: MapData;
  filterMode: FilterMode;
}

export function AnalyticsSection({ mapData, filterMode }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [threeOneOneGrouping, setThreeOneOneGrouping] = useState<ThreeOneOneGrouping>("sr_type");

  const crimeAnalytics = useMemo(() => {
    if (!mapData.crimes.length) return null;
    return {
      trends: computeTrends(mapData.crimes, c => c.date, c => c.primary_type, crimeColorCSS),
      pie: computePieSlices(mapData.crimes, c => c.primary_type, crimeColorCSS),
      monthLabels: getTrendMonthLabels(mapData.crimes, c => c.date),
    };
  }, [mapData.crimes]);

  const threeOneOneAnalytics = useMemo(() => {
    if (!mapData.requests_311.length) return null;
    const getCategory = threeOneOneGrouping === "sr_type"
      ? (r: (typeof mapData.requests_311)[0]) => r.sr_type
      : (r: (typeof mapData.requests_311)[0]) => normalizeDept(r.owner_department);
    const colorFn = threeOneOneGrouping === "sr_type" ? srTypeMapColorCSS : deptColorCSS;
    return {
      trends: computeTrends(mapData.requests_311, r => r.created_date, getCategory, colorFn),
      pie: computePieSlices(mapData.requests_311, getCategory, colorFn),
      monthLabels: getTrendMonthLabels(mapData.requests_311, r => r.created_date),
    };
  }, [mapData.requests_311, threeOneOneGrouping]);

  const permitAnalytics = useMemo(() => {
    if (!mapData.building_permits.length) return null;
    const getType = (p: (typeof mapData.building_permits)[0]) => normalizePermitType(p.permit_type);
    return {
      trends: computeTrends(mapData.building_permits, p => p.issue_date, getType, permitColorCSS),
      pie: computePieSlices(mapData.building_permits, getType, permitColorCSS),
      monthLabels: getTrendMonthLabels(mapData.building_permits, p => p.issue_date),
    };
  }, [mapData.building_permits]);

  const hasAnalytics = crimeAnalytics || threeOneOneAnalytics || permitAnalytics;
  if (!hasAnalytics) return null;

  const showCrime = (filterMode === "crime" || filterMode === "overview") && crimeAnalytics;
  const show311 = (filterMode === "311" || filterMode === "overview") && threeOneOneAnalytics;
  const showPermits = (filterMode === "permits" || filterMode === "overview") && permitAnalytics;

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
            <SourceAnalytics
              label="Crime"
              trends={crimeAnalytics.trends}
              pie={crimeAnalytics.pie}
              monthLabels={crimeAnalytics.monthLabels}
            />
          )}

          {show311 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-medium text-text-muted uppercase tracking-wider">311 Requests</span>
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
              </div>
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
            </div>
          )}

          {showPermits && (
            <SourceAnalytics
              label="Building Permits"
              trends={permitAnalytics.trends}
              pie={permitAnalytics.pie}
              monthLabels={permitAnalytics.monthLabels}
            />
          )}
        </div>
      )}
    </div>
  );
}

interface SourceAnalyticsProps {
  label: string;
  trends: ReturnType<typeof computeTrends>;
  pie: ReturnType<typeof computePieSlices>;
  monthLabels: ReturnType<typeof getTrendMonthLabels>;
}

function SourceAnalytics({ label, trends, pie, monthLabels }: SourceAnalyticsProps) {
  return (
    <div>
      <h4 className="text-[11px] font-medium text-text-muted uppercase tracking-wider mb-2">{label}</h4>
      <div className="space-y-3">
        {monthLabels && trends.length > 0 && (
          <TrendTable rows={trends} currentLabel={monthLabels.current} priorLabel={monthLabels.prior} />
        )}
        {pie.length > 0 && <PieChart slices={pie} />}
        {!monthLabels && pie.length > 0 && (
          <p className="text-[10px] text-text-muted">Not enough data for month-over-month trends.</p>
        )}
      </div>
    </div>
  );
}
