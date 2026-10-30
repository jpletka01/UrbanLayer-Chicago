import { useTranslation } from "react-i18next";
import { zoneColorCSS } from "../../lib/mapColors";

type FilterMode = "overview" | "crime" | "311" | "permits";

interface Props {
  activeLayers: Record<string, boolean>;
  filterMode: FilterMode;
  showPoints: boolean;
  showZoning: boolean;
  hasZoning: boolean;
}

const ZONING_LEGEND_KEYS: { key: string; example: string }[] = [
  { key: "residential", example: "RS-3" },
  { key: "business", example: "B3-2" },
  { key: "commercial", example: "C2-2" },
  { key: "manufacturing", example: "M2-3" },
  { key: "plannedDev", example: "PD 799" },
  { key: "downtown", example: "DX-7" },
  { key: "transportation", example: "T" },
  { key: "parksOpenSpace", example: "POS-1" },
];

export function MapLegend({ activeLayers, filterMode, showPoints, showZoning, hasZoning }: Props) {
  const { t } = useTranslation("map");

  if (!showPoints && showZoning && hasZoning) {
    return (
      <div className="absolute bottom-2 left-2 z-10 bg-dark-surface/90 backdrop-blur-sm
        border border-dark-border rounded-lg p-2 text-micro max-w-[200px]">
        <div className="text-text-secondary font-semibold mb-1">{t("legend.zoningDistricts")}</div>
        <div className="space-y-0.5">
          {ZONING_LEGEND_KEYS.map(item => (
            <div key={item.key} className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-sm shrink-0 border border-dark-border-strong"
                style={{ backgroundColor: zoneColorCSS(item.example) }}
              />
              <span className="text-text-muted">{t(`legend.${item.key}`)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!showPoints) return null;

  const activeKeys = Object.entries(activeLayers).filter(([, v]) => v).map(([k]) => k);
  if (activeKeys.length === 0) return null;

  if (filterMode === "crime") {
    return (
      <div className="absolute bottom-2 left-2 z-10 bg-dark-surface/90 backdrop-blur-sm
        border border-dark-border rounded-lg p-2 text-micro max-w-[180px]">
        <div className="text-text-secondary font-semibold mb-0.5">{t("legend.crimeTypes")}</div>
        <div className="text-text-muted">{t("legend.filtersActive", { count: activeKeys.length })}</div>
      </div>
    );
  }

  if (filterMode === "311") {
    return (
      <div className="absolute bottom-2 left-2 z-10 bg-dark-surface/90 backdrop-blur-sm
        border border-dark-border rounded-lg p-2 text-micro max-w-[180px]">
        <div className="text-text-secondary font-semibold mb-0.5">{t("legend.311RequestTypes")}</div>
        <div className="text-text-muted">{t("legend.filtersActive", { count: activeKeys.length })}</div>
      </div>
    );
  }

  if (filterMode === "permits") {
    return (
      <div className="absolute bottom-2 left-2 z-10 bg-dark-surface/90 backdrop-blur-sm
        border border-dark-border rounded-lg p-2 text-micro max-w-[180px]">
        <div className="text-text-secondary font-semibold mb-0.5">{t("legend.permitTypes")}</div>
        <div className="text-text-muted">{t("legend.filtersActive", { count: activeKeys.length })}</div>
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
      border border-dark-border rounded-lg p-2 text-micro max-w-[180px]">
      {showCrime && (
        <div className="mb-1">
          <span className="flex items-center gap-1 text-text-muted">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "rgb(226,75,74)" }} />
            {t("legend.crimeIncidents")}
          </span>
        </div>
      )}
      {show311 && (
        <div className="mb-1">
          <span className="flex items-center gap-1 text-text-muted">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "rgb(0,188,212)" }} />
            {t("legend.311Requests")}
          </span>
        </div>
      )}
      {showPermits && (
        <div>
          <span className="flex items-center gap-1 text-text-muted">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "rgb(99,153,34)" }} />
            {t("legend.buildingPermits")}
          </span>
        </div>
      )}
    </div>
  );
}
