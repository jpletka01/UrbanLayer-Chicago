import { useMemo, useState } from "react";
import type { ContextObject, MapData, RetrievalPlan } from "../../lib/types";
import type { FilterMode } from "../../lib/mapColors";
import { zonePrefix, zoneColorCSS, ZONE_PREFIX_LABELS } from "../../lib/mapColors";
import { InfoTooltip } from "../InfoTooltip";
import { AnalyticsSection } from "./AnalyticsSection";
import { PropertyCard } from "./PropertyCard";
import { RegulatoryCard } from "./RegulatoryCard";
import { IncentivesCard } from "./IncentivesCard";
import { NeighborhoodCard } from "./NeighborhoodCard";
import { ViolationsCard } from "./ViolationsCard";
import { BusinessCard } from "./BusinessCard";

interface Props {
  plan: RetrievalPlan | null;
  context: ContextObject | null;
  loading: boolean;
  mapData?: MapData | null;
  filterMode?: FilterMode;
}

function Skeleton({ height = 24, className = "" }: { height?: number; className?: string }) {
  return (
    <div
      className={`animate-pulse bg-dark-elevated rounded ${className}`}
      style={{ height }}
    />
  );
}

const ZONE_CATEGORY_ORDER = [
  "RS", "RT", "RM", "B", "C", "M", "PD", "PMD",
  "D", "DC", "DX", "DR", "DS", "T", "P", "POS",
];

function ZoningCodesTable({ mapData }: { mapData: MapData }) {
  const [collapsed, setCollapsed] = useState(false);

  const zoneCodes = useMemo(() => {
    const features = (mapData.zoning as Record<string, unknown>)?.features as
      Array<{ properties?: Record<string, unknown> }> | undefined;
    if (!features?.length) return [];

    const codes = new Set<string>();
    for (const f of features) {
      const zc = f.properties?.ZONE_CLASS as string | undefined;
      if (zc) codes.add(zc);
    }

    return [...codes].sort((a, b) => {
      const pa = zonePrefix(a);
      const pb = zonePrefix(b);
      const ia = ZONE_CATEGORY_ORDER.indexOf(pa);
      const ib = ZONE_CATEGORY_ORDER.indexOf(pb);
      const oa = ia === -1 ? 999 : ia;
      const ob = ib === -1 ? 999 : ib;
      if (oa !== ob) return oa - ob;
      return a.localeCompare(b);
    });
  }, [mapData.zoning]);

  if (zoneCodes.length === 0) return null;

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
        Zoning Codes on Map
      </button>

      {!collapsed && (
        <div className="px-4 pb-3">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-text-muted border-b border-dark-border">
                <th className="text-left pr-2 pb-1.5 font-medium w-8"></th>
                <th className="text-left px-2 pb-1.5 font-medium">Code</th>
                <th className="text-left pl-2 pb-1.5 font-medium">Category</th>
              </tr>
            </thead>
            <tbody>
              {zoneCodes.map((code) => {
                const prefix = zonePrefix(code);
                const label = ZONE_PREFIX_LABELS[prefix] ?? "Other";
                return (
                  <tr key={code} className="border-t border-dark-border/50">
                    <td className="pr-2 py-1">
                      <span
                        className="w-3 h-3 rounded-sm inline-block border border-white/20"
                        style={{ backgroundColor: zoneColorCSS(code) }}
                      />
                    </td>
                    <td className="px-2 py-1 text-text-primary font-mono">
                      <InfoTooltip term={`zone:${prefix}`}>{code}</InfoTooltip>
                    </td>
                    <td className="pl-2 py-1 text-text-muted">{label}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function DataView({ context, loading, mapData, filterMode }: Props) {
  const hasMapData = mapData && (mapData.crimes.length > 0 || mapData.requests_311.length > 0 || mapData.building_permits.length > 0);
  const hasZoning = !!(mapData?.zoning && ((mapData.zoning as Record<string, unknown>).features as unknown[] | undefined)?.length);
  const hasDomainData = !!(context?.property || context?.regulatory || context?.incentives || context?.neighborhood
    || context?.violations || context?.crime_last_90d || context?.open_311_requests || context?.permits || context?.businesses);

  return (
    <div className="space-y-4">
      {context?.data_lag_note && (
        <div className="px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400/90 text-xs">
          {context.data_lag_note}
        </div>
      )}

      {hasZoning ? (
        <div className="px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400/90 text-xs leading-relaxed">
          <strong className="text-amber-400">Zoning data notice:</strong>{" "}
          This map is a good reference but may not reflect the most recent City Council votes.
          Check the{" "}
          <a
            href="https://gisapps.chicago.gov/ZoningMapWeb/?liab=1&config=zoning"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-amber-300 transition-colors"
          >
            official Chicago Zoning Map
          </a>{" "}
          for completely up-to-date data.
        </div>
      ) : null}

      {loading && !context && (
        <div className="space-y-3">
          <Skeleton height={100} />
          <Skeleton height={80} />
        </div>
      )}

      {context && !hasMapData && !hasZoning && !hasDomainData && !loading && (
        <p className="text-sm text-text-muted">No live datasets were queried for this answer.</p>
      )}

      {context?.property && <PropertyCard data={context.property} />}
      {context?.regulatory && <RegulatoryCard data={context.regulatory} />}
      {context?.incentives && <IncentivesCard data={context.incentives} />}
      {context?.neighborhood && <NeighborhoodCard data={context.neighborhood} />}
      {context?.violations && <ViolationsCard data={context.violations} />}

      {(hasMapData || context?.crime_last_90d || context?.open_311_requests || context?.permits) && (
        <AnalyticsSection mapData={mapData} filterMode={filterMode ?? "overview"} context={context} />
      )}

      {context?.businesses && <BusinessCard data={context.businesses} />}

      {hasZoning && <ZoningCodesTable mapData={mapData!} />}
    </div>
  );
}
