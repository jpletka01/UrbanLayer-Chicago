// Map color ramp for redevelopment upside (PR6). CRITICAL: a null upside_score is its own
// distinct "no data" color — NOT the low end of the ramp. Pre-index, upside is null for
// ~everything, so without this the whole map would falsely read "low opportunity" where we
// simply don't know. The legend names the no-data swatch explicitly.

export type RGBA = [number, number, number, number];
export type DiscoveryColorMode = "upside" | "land_use";

export interface DiscoveryLegendDefinition {
  key: string;
  i18nKey: string;
  label: string;
  color: string;
  rgba: RGBA;
}

const NO_DATA: RGBA = [90, 88, 82, 150]; // muted gray, visibly different from the cool end
const HIGH: RGBA = [201, 100, 66, 230]; // accent — strongest opportunity
const MID: RGBA = [224, 154, 92, 215];
const LOW: RGBA = [96, 125, 139, 190]; // cool slate

/** upside_score (0–100) → fill color; null → the distinct no-data swatch. */
export function upsideColor(upside: number | null | undefined): RGBA {
  if (upside == null) return NO_DATA;
  if (upside >= 80) return HIGH;
  if (upside >= 50) return MID;
  return LOW;
}

function css([r, g, b]: RGBA): string {
  return `rgb(${r}, ${g}, ${b})`;
}

// Legend rows (top → bottom), including the no-data swatch. `i18nKey` is the
// `discovery.*`-relative key DiscoveryMap resolves at render; `label` is the English fallback.
export const UPSIDE_LEGEND: DiscoveryLegendDefinition[] = [
  { key: "upside:high", i18nKey: "legendUpsideHigh", label: "Upside 80+", color: css(HIGH), rgba: HIGH },
  { key: "upside:mid", i18nKey: "legendUpsideMid", label: "50–79", color: css(MID), rgba: MID },
  { key: "upside:low", i18nKey: "legendUpsideLow", label: "< 50", color: css(LOW), rgba: LOW },
  { key: "upside:no_data", i18nKey: "legendUpsideNoData", label: "No data", color: css(NO_DATA), rgba: NO_DATA },
];

export function upsideLegendKey(upside: number | null | undefined): string {
  if (upside == null) return "upside:no_data";
  if (upside >= 80) return "upside:high";
  if (upside >= 50) return "upside:mid";
  return "upside:low";
}

// --- Free-tier (view-only) map: color by land use, not the gated upside intelligence. ---
const LAND_USE_COLORS = {
  vacant: [120, 144, 156, 190],
  residential: [79, 195, 247, 200],
  multi_family: [126, 87, 194, 205],
  commercial: [255, 213, 79, 205],
  industrial: [239, 83, 80, 205],
  mixed_use: [38, 198, 218, 205],
  institutional: [102, 187, 106, 200],
  exempt: [120, 120, 120, 170],
} satisfies Record<string, RGBA>;

export type RenderableLandUse = keyof typeof LAND_USE_COLORS;
export const RENDERABLE_LAND_USES = Object.keys(LAND_USE_COLORS) as RenderableLandUse[];

export function landUseColor(landUse: string | null | undefined): RGBA {
  if (landUse == null || !(landUse in LAND_USE_COLORS)) return NO_DATA;
  return LAND_USE_COLORS[landUse as RenderableLandUse];
}

export function landUseLegendKey(landUse: string | null | undefined): string {
  return landUse != null && landUse in LAND_USE_COLORS
    ? `land_use:${landUse}`
    : "land_use:no_data";
}

export const LAND_USE_LEGEND: DiscoveryLegendDefinition[] = [
  { key: "land_use:vacant", i18nKey: "enum.land_use.vacant", label: "Vacant", color: css(LAND_USE_COLORS.vacant), rgba: LAND_USE_COLORS.vacant },
  { key: "land_use:residential", i18nKey: "enum.land_use.residential", label: "Residential", color: css(LAND_USE_COLORS.residential), rgba: LAND_USE_COLORS.residential },
  { key: "land_use:multi_family", i18nKey: "enum.land_use.multi_family", label: "Multifamily", color: css(LAND_USE_COLORS.multi_family), rgba: LAND_USE_COLORS.multi_family },
  { key: "land_use:commercial", i18nKey: "enum.land_use.commercial", label: "Commercial", color: css(LAND_USE_COLORS.commercial), rgba: LAND_USE_COLORS.commercial },
  { key: "land_use:industrial", i18nKey: "enum.land_use.industrial", label: "Industrial", color: css(LAND_USE_COLORS.industrial), rgba: LAND_USE_COLORS.industrial },
  { key: "land_use:mixed_use", i18nKey: "enum.land_use.mixed_use", label: "Mixed-use", color: css(LAND_USE_COLORS.mixed_use), rgba: LAND_USE_COLORS.mixed_use },
  { key: "land_use:institutional", i18nKey: "enum.land_use.institutional", label: "Institutional", color: css(LAND_USE_COLORS.institutional), rgba: LAND_USE_COLORS.institutional },
  { key: "land_use:exempt", i18nKey: "enum.land_use.exempt", label: "Tax-exempt", color: css(LAND_USE_COLORS.exempt), rgba: LAND_USE_COLORS.exempt },
  { key: "land_use:no_data", i18nKey: "legendLandUseNoData", label: "No data", color: css(NO_DATA), rgba: NO_DATA },
];

export function legendFor(mode: DiscoveryColorMode): DiscoveryLegendDefinition[] {
  return mode === "upside" ? UPSIDE_LEGEND : LAND_USE_LEGEND;
}
