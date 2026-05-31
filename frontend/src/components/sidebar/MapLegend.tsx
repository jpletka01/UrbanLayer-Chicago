type FilterMode = "overview" | "crime" | "311" | "permits";

interface Props {
  activeLayers: Record<string, boolean>;
  filterMode: FilterMode;
}

export function MapLegend({ activeLayers, filterMode }: Props) {
  const activeKeys = Object.entries(activeLayers).filter(([, v]) => v).map(([k]) => k);
  if (activeKeys.length === 0) return null;

  if (filterMode === "crime") {
    return (
      <div className="absolute bottom-2 left-2 z-10 bg-dark-surface/90 backdrop-blur-sm
        border border-dark-border rounded-lg p-2 text-[10px] max-w-[180px]">
        <div className="text-text-secondary font-semibold mb-0.5">Crime Types</div>
        <div className="text-text-muted">{activeKeys.length} filter{activeKeys.length !== 1 ? "s" : ""} active</div>
      </div>
    );
  }

  if (filterMode === "311") {
    return (
      <div className="absolute bottom-2 left-2 z-10 bg-dark-surface/90 backdrop-blur-sm
        border border-dark-border rounded-lg p-2 text-[10px] max-w-[180px]">
        <div className="text-text-secondary font-semibold mb-0.5">311 Departments</div>
        <div className="text-text-muted">{activeKeys.length} filter{activeKeys.length !== 1 ? "s" : ""} active</div>
      </div>
    );
  }

  // Overview mode
  const showCrime = activeLayers.crimes;
  const show311 = activeLayers["requests-311"];
  const showPermits = activeLayers.permits;

  if (!showCrime && !show311 && !showPermits) return null;

  return (
    <div className="absolute bottom-2 left-2 z-10 bg-dark-surface/90 backdrop-blur-sm
      border border-dark-border rounded-lg p-2 text-[10px] max-w-[180px]">
      {showCrime && (
        <div className="mb-1">
          <span className="flex items-center gap-1 text-text-muted">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "rgb(226,75,74)" }} />
            Crime incidents
          </span>
        </div>
      )}
      {show311 && (
        <div className="mb-1">
          <span className="flex items-center gap-1 text-text-muted">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "rgb(0,188,212)" }} />
            311 requests
          </span>
        </div>
      )}
      {showPermits && (
        <div>
          <span className="flex items-center gap-1 text-text-muted">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "rgb(99,153,34)" }} />
            Building permits
          </span>
        </div>
      )}
    </div>
  );
}
