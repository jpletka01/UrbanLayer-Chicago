import { useMemo, useState } from "react";
import type { ContextObject, MapData } from "../../lib/types";
import type { FilterMode } from "../../lib/mapColors";
import { deptColorCSS, normalizeDept, CRIME_TYPE_COLORS } from "../../lib/mapColors";
import { computeTrends, computePieSlices, getTrendMonthLabels } from "../../lib/analytics";
import { PieChart } from "./PieChart";
import { TrendTable } from "./TrendTable";

const SR_TYPE_PALETTE = [
  "#26c6da", "#ff7043", "#42a5f5", "#ab47bc", "#66bb6a",
  "#ffa726", "#ef5350", "#8d6e63", "#78909c", "#ec407a",
];

function srTypeColor(type: string): string {
  let hash = 0;
  for (let i = 0; i < type.length; i++) hash = ((hash << 5) - hash + type.charCodeAt(i)) | 0;
  return SR_TYPE_PALETTE[Math.abs(hash) % SR_TYPE_PALETTE.length];
}

function permitTypeColor(type: string): string {
  const palette = ["#63992280", "#7cb342", "#558b2f", "#9ccc65", "#aed581"];
  let hash = 0;
  for (let i = 0; i < type.length; i++) hash = ((hash << 5) - hash + type.charCodeAt(i)) | 0;
  return palette[Math.abs(hash) % palette.length];
}

type ThreeOneOneGrouping = "sr_type" | "department";

interface Props {
  mapData: MapData;
  filterMode: FilterMode;
  context?: ContextObject | null;
}

export function AnalyticsSection({ mapData, filterMode, context }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [threeOneOneGrouping, setThreeOneOneGrouping] = useState<ThreeOneOneGrouping>("sr_type");

  const crimeAnalytics = useMemo(() => {
    if (!mapData.crimes.length) return null;
    const colorFn = (cat: string) => {
      const c = CRIME_TYPE_COLORS[cat];
      return c ? `rgb(${c[0]},${c[1]},${c[2]})` : "rgb(136,135,128)";
    };
    return {
      trends: computeTrends(mapData.crimes, c => c.date, c => c.primary_type, colorFn),
      pie: computePieSlices(mapData.crimes, c => c.primary_type, colorFn),
      monthLabels: getTrendMonthLabels(mapData.crimes, c => c.date),
    };
  }, [mapData.crimes]);

  const threeOneOneAnalytics = useMemo(() => {
    if (!mapData.requests_311.length) return null;
    const getCategory = threeOneOneGrouping === "sr_type"
      ? (r: (typeof mapData.requests_311)[0]) => r.sr_type
      : (r: (typeof mapData.requests_311)[0]) => normalizeDept(r.owner_department);
    const colorFn = threeOneOneGrouping === "sr_type" ? srTypeColor : deptColorCSS;
    return {
      trends: computeTrends(mapData.requests_311, r => r.created_date, getCategory, colorFn),
      pie: computePieSlices(mapData.requests_311, getCategory, colorFn),
      monthLabels: getTrendMonthLabels(mapData.requests_311, r => r.created_date),
    };
  }, [mapData.requests_311, threeOneOneGrouping]);

  const permitAnalytics = useMemo(() => {
    if (!mapData.building_permits.length) return null;
    return {
      trends: computeTrends(mapData.building_permits, p => p.issue_date, p => p.permit_type, permitTypeColor),
      pie: computePieSlices(mapData.building_permits, p => p.permit_type, permitTypeColor),
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
              totalOverride={context?.crime_last_90d?.total}
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
                  <PieChart slices={threeOneOneAnalytics.pie} totalOverride={context?.open_311_requests?.total} />
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
              totalOverride={context?.permits?.total}
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
  totalOverride?: number;
}

function SourceAnalytics({ label, trends, pie, monthLabels, totalOverride }: SourceAnalyticsProps) {
  return (
    <div>
      <h4 className="text-[11px] font-medium text-text-muted uppercase tracking-wider mb-2">{label}</h4>
      <div className="space-y-3">
        {monthLabels && trends.length > 0 && (
          <TrendTable rows={trends} currentLabel={monthLabels.current} priorLabel={monthLabels.prior} />
        )}
        {pie.length > 0 && <PieChart slices={pie} totalOverride={totalOverride} />}
        {!monthLabels && pie.length > 0 && (
          <p className="text-[10px] text-text-muted">Not enough data for month-over-month trends.</p>
        )}
      </div>
    </div>
  );
}
