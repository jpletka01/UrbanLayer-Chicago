import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ContextObject, MapData } from "../../lib/types";
import type { FilterMode } from "../../lib/mapColors";
import { zonePrefix, zoneColorCSS, zonePrefixLabel } from "../../lib/mapColors";
import { InfoTooltip } from "../InfoTooltip";
import { AnalyticsSection } from "./AnalyticsSection";
import { ScorecardBridgeCard, buildScorecardHref } from "./ScorecardBridgeCard";
import { PropertyCard } from "./PropertyCard";
import { RegulatoryCard } from "./RegulatoryCard";
import { IncentivesCard } from "./IncentivesCard";
import { NeighborhoodCard } from "./NeighborhoodCard";
import { ViolationsCard } from "./ViolationsCard";
import { BusinessCard } from "./BusinessCard";
import { VacantBuildingsCard } from "./VacantBuildingsCard";
import { FoodInspectionCard } from "./FoodInspectionCard";

interface Props {
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
  const { t } = useTranslation("map");
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
        {t("states.zoningCodesOnMap")}
      </button>

      {!collapsed && (
        <div className="px-4 pb-3">
          <table className="w-full text-micro">
            <thead>
              <tr className="text-text-muted border-b border-dark-border">
                <th className="text-left pr-2 pb-1.5 font-medium w-8"></th>
                <th className="text-left px-2 pb-1.5 font-medium">{t("states.code")}</th>
                <th className="text-left pl-2 pb-1.5 font-medium">{t("states.category")}</th>
              </tr>
            </thead>
            <tbody>
              {zoneCodes.map((code) => {
                const prefix = zonePrefix(code);
                const label = zonePrefixLabel(prefix) || t("filters.other");
                return (
                  <tr key={code} className="border-t border-dark-border/50">
                    <td className="pr-2 py-1">
                      <span
                        className="w-3 h-3 rounded-sm inline-block border border-dark-border-strong"
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
  const { t } = useTranslation("map");
  const { t: td } = useTranslation("data");
  const hasMapData = mapData && (mapData.crimes.length > 0 || mapData.requests_311.length > 0 || mapData.building_permits.length > 0);
  const hasZoning = !!(mapData?.zoning && ((mapData.zoning as Record<string, unknown>).features as unknown[] | undefined)?.length);
  const hasDomainData = !!(context?.property || context?.regulatory || context?.incentives || context?.neighborhood
    || context?.violations || context?.crime_last_90d || context?.open_311_requests || context?.permits || context?.businesses);
  const parcelPin = context?.property?.pin14 ?? null;
  const parcelAddress = context?.resolved_address ?? context?.property?.address ?? null;
  const scorecardHref = buildScorecardHref(parcelPin, parcelAddress);

  return (
    <div className="space-y-4">
      {(parcelPin || parcelAddress) && (
        <ScorecardBridgeCard pin={parcelPin} address={parcelAddress} />
      )}

      {context?.data_lag_note && (
        <div className="px-3 py-2 rounded-lg bg-state-warning/10 border border-state-warning/20 text-state-warning/90 text-xs">
          {context.data_lag_days && context.data_lag_cutoff
            ? td("crimeDataLag", { days: context.data_lag_days, cutoff: context.data_lag_cutoff })
            : context.data_lag_note}
        </div>
      )}

      {hasZoning ? (
        <div className="px-3 py-2 rounded-lg bg-state-warning/10 border border-state-warning/20 text-state-warning/90 text-xs leading-relaxed">
          <strong className="text-state-warning">{t("states.zoningNotice")}</strong>{" "}
          {t("states.zoningNoticeText")}{" "}
          <a
            href="https://gisapps.chicago.gov/ZoningMapWeb/?liab=1&config=zoning"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-state-warning transition-colors"
          >
            {t("states.zoningNoticeLink")}
          </a>{" "}
          {t("states.zoningNoticeAfter")}
        </div>
      ) : null}

      {loading && !context && (
        <div className="space-y-3">
          <Skeleton height={100} />
          <Skeleton height={80} />
        </div>
      )}

      {context && !hasMapData && !hasZoning && !hasDomainData && !loading && (
        <p className="text-sm text-text-muted">{t("states.noDatasets")}</p>
      )}

      {context?.property && <PropertyCard data={context.property} scorecardHref={scorecardHref} />}
      {context?.regulatory && <RegulatoryCard data={context.regulatory} />}
      {context?.incentives && <IncentivesCard data={context.incentives} scorecardHref={scorecardHref} />}
      {context?.neighborhood && <NeighborhoodCard data={context.neighborhood} />}
      {context?.violations && <ViolationsCard data={context.violations} />}

      {(hasMapData || context?.crime_last_90d || context?.open_311_requests || context?.permits) && (
        <AnalyticsSection mapData={mapData} filterMode={filterMode ?? "overview"} context={context} />
      )}

      {context?.businesses && <BusinessCard data={context.businesses} />}
      {context?.vacant_buildings && <VacantBuildingsCard data={context.vacant_buildings} />}
      {context?.food_inspections && <FoodInspectionCard data={context.food_inspections} />}

      {hasZoning && <ZoningCodesTable mapData={mapData!} />}
    </div>
  );
}
