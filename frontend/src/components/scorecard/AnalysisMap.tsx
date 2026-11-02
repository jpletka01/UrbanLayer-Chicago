// AnalysisMap — the Build section's ONE map (redesign step 5, decision Item 55). It replaces the zoning,
// boundaries and capacity maps that each took half the section: one map slot with a layer switch,
// Zoning · Overlays & incentives · Built vs allowed. Each layer keeps its own render adapter
// (`parcelMapModel` / `capacityMapModel`) and its own collapsed key; only the chosen one mounts, so the
// section holds one GL context instead of three. A layer with nothing to draw is not offered.
import { useState, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { ParcelMap, type ParcelMapLayers } from "./ParcelMap";
import { availableLayers, type AnalysisLayer } from "./analysisLayers";
import { CapacityMap } from "./CapacityMap";

interface AnalysisMapProps {
  lat: number;
  lon: number;
  pin?: string | null;
  parcelGeometry?: GeoJSON.Geometry | null;
  /** Stable Property Profile identity (the page also keys this component by it, so a new parcel starts on Zoning). */
  profileKey?: string | null;
  parcelConfidence?: "authoritative" | "approximate" | null;
  /** `/api/parcel-map` layers; null while loading (Zoning and Overlays wait for them). */
  layers: ParcelMapLayers | null;
  /** The parcel's own district, listed first in the zoning key. */
  subjectKey?: string | null;
  className?: string;
}

export function AnalysisMap({ lat, lon, pin, parcelGeometry, profileKey, parcelConfidence, layers, subjectKey, className }: AnalysisMapProps) {
  const { t } = useTranslation("pages");
  const offered = availableLayers(layers);
  const [chosen, setChosen] = useState<AnalysisLayer>("zoning");
  // Until the parcel-map layers arrive, hold the Zoning slot rather than jumping to Built vs allowed.
  const layer: AnalysisLayer = offered.includes(chosen) ? chosen : layers ? offered[0] : chosen;

  const common = { lat, lon, parcelGeometry, profileKey, parcelConfidence, layers };
  // A radio group: one tab stop, arrow keys move the choice (and the focus) along the switch.
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = offered[(offered.indexOf(layer) + step + offered.length) % offered.length];
    setChosen(next);
    (e.currentTarget.querySelector(`[data-layer="${next}"]`) as HTMLButtonElement | null)?.focus();
  };
  return (
    <section className={`flex min-w-0 flex-col gap-3 ${className ?? ""}`} data-testid="analysis-map">
      <div
        role="radiogroup"
        aria-label={t("scorecard.analysisMap.switchLabel")}
        onKeyDown={onKeyDown}
        className="inline-flex max-w-full self-start overflow-x-auto rounded-lg border border-dark-border bg-dark-elevated/40 p-0.5"
      >
        {offered.map((id) => (
          <button
            key={id}
            type="button"
            role="radio"
            aria-checked={layer === id}
            tabIndex={layer === id ? 0 : -1}
            data-layer={id}
            onClick={() => setChosen(id)}
            data-testid={`analysis-layer-${id}`}
            className={`touch-target whitespace-nowrap rounded-md px-3 py-1.5 text-caption transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
              layer === id ? "bg-dark-surface text-text-primary shadow-sm" : "text-text-secondary hover:text-link"
            }`}
          >
            {t(`scorecard.analysisMap.layer.${id}`)}
          </button>
        ))}
      </div>
      {layer === "capacity" ? (
        <CapacityMap key={`capacity:${profileKey ?? `${lat}:${lon}`}`} pin={pin ?? null} lat={lat} lon={lon} profileKey={profileKey} />
      ) : !layers ? (
        <div className="h-[22rem] lg:h-[26rem] rounded-lg border border-dark-border bg-dark-elevated/40" aria-hidden />
      ) : (
        <ParcelMap
          {...common}
          key={layer}
          variant={layer === "zoning" ? "zoning" : "boundaries"}
          lazy
          subjectKey={layer === "zoning" ? subjectKey ?? null : null}
          className="h-[22rem] lg:h-[26rem]"
        />
      )}
    </section>
  );
}
