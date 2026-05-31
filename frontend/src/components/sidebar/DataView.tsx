import type { ContextObject, MapData, RetrievalPlan } from "../../lib/types";
import type { FilterMode } from "../../lib/mapColors";
import { AnalyticsSection } from "./AnalyticsSection";

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

export function DataView({ context, loading, mapData, filterMode }: Props) {
  const hasMapData = mapData && (mapData.crimes.length > 0 || mapData.requests_311.length > 0 || mapData.building_permits.length > 0);

  return (
    <div className="space-y-4">
      {context?.data_lag_note && (
        <div className="px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400/90 text-xs">
          {context.data_lag_note}
        </div>
      )}

      {loading && !context && (
        <div className="space-y-3">
          <Skeleton height={100} />
          <Skeleton height={80} />
        </div>
      )}

      {context && !hasMapData && !loading && (
        <p className="text-sm text-text-muted">No live datasets were queried for this answer.</p>
      )}

      {hasMapData && (
        <AnalyticsSection mapData={mapData!} filterMode={filterMode ?? "overview"} />
      )}
    </div>
  );
}
