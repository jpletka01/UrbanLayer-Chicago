import { GeoJsonLayer, IconLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { PathStyleExtension } from "@deck.gl/extensions";
import { zoneColor, zoneLineColor, type MapTheme } from "../../lib/mapColors";
import {
  mapFeatureFillAlpha,
  mapFeatureHasDashedOutline,
  PARCEL_MAP_LAYER_OPACITY,
  type ParcelMapLayerState,
  type ParcelMapSource,
  type ParcelMapVariant,
} from "../../lib/parcelMap";
import {
  zoneLabelsVisible,
  type BoundaryMapModel,
  type ZoningLabelModelEntry,
  type ZoningMapModel,
} from "./parcelMapModel";

const DASH_EXTENSION = new PathStyleExtension({ dash: true });
const LOW_DASH: [number, number] = [4, 3];
const SOLID_DASH: [number, number] = [0, 0];
const ACCENT: [number, number, number, number] = [249, 164, 116, 255];
const LOW_CONFIDENCE_PIN_ICON = {
  id: "low-confidence-pin",
  url: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="#f9a474" fill-opacity=".5" stroke="#0a0a0a" stroke-width="3" stroke-dasharray="4 3"/></svg>',
  )}`,
  width: 24,
  height: 24,
  anchorX: 12,
  anchorY: 12,
};

export type ParcelMapLayerStates = Record<ParcelMapSource, ParcelMapLayerState>;

export const DEFAULT_PARCEL_MAP_LAYER_STATES: ParcelMapLayerStates = {
  zoning: "on",
  overlays: "on",
  tif: "on",
  ez: "on",
};

export function buildZoningDeckLayers({
  model,
  state,
  mapTheme,
  mapZoom,
  roadInsertionId,
}: {
  model: ZoningMapModel;
  state: ParcelMapLayerState;
  mapTheme: MapTheme;
  mapZoom: number;
  roadInsertionId: string | null;
}): unknown[] {
  if (state === "off" || model.visibleCount === 0) return [];
  const opacity = PARCEL_MAP_LAYER_OPACITY[state];
  const fillProps = {
    id: "zoning",
    data: model.featureCollection,
    beforeId: roadInsertionId ?? undefined,
    filled: true,
    stroked: false,
    opacity,
    getFillColor: (feature: GeoJSON.Feature) => {
      const color = zoneColor(String(feature.properties?.ZONE_CLASS ?? ""), mapTheme);
      return [
        color[0], color[1], color[2], mapFeatureFillAlpha(color[3], feature),
      ] as [number, number, number, number];
    },
    pickable: true,
  };
  const outlineProps = {
    id: "pm-zoning-outline",
    data: model.featureCollection,
    filled: false,
    stroked: true,
    opacity,
    getLineColor: (feature: GeoJSON.Feature) => zoneLineColor(
      String(feature.properties?.ZONE_CLASS ?? ""),
      mapTheme,
    ),
    getDashArray: (feature: GeoJSON.Feature) => (
      mapFeatureHasDashedOutline(feature) ? LOW_DASH : SOLID_DASH
    ),
    lineDashJustified: true,
    lineWidthMinPixels: 1.25,
    pickable: false,
    extensions: [DASH_EXTENSION],
  };
  const output: unknown[] = [new GeoJsonLayer(fillProps), new GeoJsonLayer(outlineProps)];
  if (zoneLabelsVisible(mapZoom)) {
    output.push(new TextLayer<ZoningLabelModelEntry>({
      id: "pm-zone-labels",
      data: model.labels,
      opacity,
      getPosition: (entry) => entry.position,
      getText: (entry) => entry.zoneClass,
      getSize: 12,
      sizeUnits: "pixels",
      getColor: mapTheme === "light" ? [20, 20, 20, 245] : [255, 255, 255, 245],
      outlineColor: mapTheme === "light" ? [255, 255, 255, 245] : [8, 8, 8, 245],
      outlineWidth: 0.18,
      fontFamily: "JetBrains Mono, monospace",
      fontSettings: { sdf: true, fontSize: 64, buffer: 8 },
      billboard: true,
      pickable: false,
    }));
  }
  return output;
}

export function buildBoundaryDeckLayers({
  model,
  states,
}: {
  model: BoundaryMapModel;
  states: ParcelMapLayerStates;
}): unknown[] {
  const output: unknown[] = [];
  for (const entry of model.entries) {
    const state = states[entry.source];
    if (state === "off") continue;
    const fill = entry.fillColor;
    const fillColor: [number, number, number, number] = [
      fill[0], fill[1], fill[2], mapFeatureFillAlpha(fill[3], entry.feature),
    ];
    const props = {
      id: entry.id,
      data: [entry.feature],
      opacity: PARCEL_MAP_LAYER_OPACITY[state],
      getFillColor: fillColor,
      getLineColor: entry.lineColor,
      getDashArray: entry.confidence === "low" ? LOW_DASH : SOLID_DASH,
      lineDashJustified: true,
      lineWidthMinPixels: 2,
      pickable: true,
      extensions: [DASH_EXTENSION],
    };
    output.push(new GeoJsonLayer(props));
  }
  return output;
}

export function buildSubjectParcelLayer({
  parcelGeometry,
  lat,
  lon,
  satellite,
  variant,
  confidence,
}: {
  parcelGeometry: GeoJSON.Geometry | null | undefined;
  lat: number;
  lon: number;
  satellite: boolean;
  variant: ParcelMapVariant;
  confidence: "authoritative" | "approximate" | null | undefined;
}): unknown {
  const low = confidence === "approximate";
  const fillAlpha = Math.round((satellite && variant === "place" ? 0 : 25) * (low ? 0.5 : 1));
  if (parcelGeometry) {
    const parcelFeature: GeoJSON.Feature = {
      type: "Feature",
      geometry: parcelGeometry,
      properties: {},
    };
    const fillColor: [number, number, number, number] = [249, 164, 116, fillAlpha];
    const props = {
      id: "pm-parcel",
      data: [parcelFeature],
      getFillColor: fillColor,
      getLineColor: ACCENT,
      getDashArray: low ? LOW_DASH : SOLID_DASH,
      lineDashJustified: true,
      lineWidthMinPixels: 2.5,
      pickable: false,
      extensions: [DASH_EXTENSION],
    };
    return new GeoJsonLayer(props);
  }

  if (low) {
    return new IconLayer({
      id: "pm-pin",
      data: [{ lat, lon }],
      getPosition: (): [number, number] => [lon, lat],
      getIcon: () => LOW_CONFIDENCE_PIN_ICON,
      getSize: 18,
      sizeUnits: "pixels",
      alphaCutoff: 0,
      pickable: false,
    });
  }

  const pinFill: [number, number, number, number] = [249, 164, 116, 255];
  const pinLine: [number, number, number, number] = [10, 10, 10, 255];
  const props = {
    id: "pm-pin",
    data: [{ lat, lon }],
    getPosition: (): [number, number] => [lon, lat],
    getRadius: 7,
    radiusUnits: "pixels" as const,
    getFillColor: pinFill,
    getLineColor: pinLine,
    getLineWidth: 2,
    lineWidthUnits: "pixels" as const,
    stroked: true,
    pickable: false,
  };
  return new ScatterplotLayer(props);
}

/** "This lot" in the new UI (decision Item 74): a black outline with a white edge (white with a dark edge on a
    dark street map), a faint fill, the same dashed treatment when the parcel's identity is approximate. Drawn as
    two layers, the wide edge under the outline. Today's Profile keeps buildSubjectParcelLayer (orange). */
export function buildSubjectParcelLayersNext({
  parcelGeometry,
  lat,
  lon,
  onDarkStreets,
  confidence,
}: {
  parcelGeometry: GeoJSON.Geometry | null | undefined;
  lat: number;
  lon: number;
  /** A dark street map flips the lot to white; satellite and light streets keep it black. */
  onDarkStreets: boolean;
  confidence: "authoritative" | "approximate" | null | undefined;
}): unknown[] {
  const low = confidence === "approximate";
  const ink: [number, number, number, number] = onDarkStreets ? [255, 255, 255, 255] : [28, 28, 28, 255];
  const edge: [number, number, number, number] = onDarkStreets ? [28, 28, 28, 230] : [255, 255, 255, 235];
  if (parcelGeometry) {
    const data = [{ type: "Feature", geometry: parcelGeometry, properties: {} } as GeoJSON.Feature];
    return [
      new GeoJsonLayer({
        id: "pm-parcel-edge", data, filled: false, getLineColor: edge, lineWidthMinPixels: 6, pickable: false,
      }),
      new GeoJsonLayer({
        id: "pm-parcel",
        data,
        getFillColor: [ink[0], ink[1], ink[2], low ? 10 : 20],
        getLineColor: ink,
        getDashArray: low ? LOW_DASH : SOLID_DASH,
        lineDashJustified: true,
        lineWidthMinPixels: 2.5,
        pickable: false,
        extensions: [DASH_EXTENSION],
      }),
    ];
  }
  return [
    new ScatterplotLayer({
      id: "pm-pin",
      data: [{ lat, lon }],
      getPosition: (): [number, number] => [lon, lat],
      getRadius: 7,
      radiusUnits: "pixels",
      getFillColor: low ? [ink[0], ink[1], ink[2], 128] : ink,
      getLineColor: edge,
      getLineWidth: 3,
      lineWidthUnits: "pixels",
      stroked: true,
      pickable: false,
    }),
  ];
}
