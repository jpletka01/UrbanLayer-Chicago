// Map color ramp for redevelopment upside (PR6). CRITICAL: a null upside_score is its own
// distinct "no data" color — NOT the low end of the ramp. Pre-index, upside is null for
// ~everything, so without this the whole map would falsely read "low opportunity" where we
// simply don't know. The legend names the no-data swatch explicitly.

export type RGBA = [number, number, number, number];

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

// Legend rows (top → bottom), including the no-data swatch.
export const UPSIDE_LEGEND: { label: string; color: string }[] = [
  { label: "Upside 80+", color: css(HIGH) },
  { label: "50–79", color: css(MID) },
  { label: "< 50", color: css(LOW) },
  { label: "No data", color: css(NO_DATA) },
];

// --- Free-tier (view-only) map: color by land use, not the gated upside intelligence. ---
const LAND_USE_COLORS: Record<string, RGBA> = {
  vacant: [120, 144, 156, 190],
  residential: [79, 195, 247, 200],
  multi_family: [126, 87, 194, 205],
  commercial: [255, 213, 79, 205],
  industrial: [239, 83, 80, 205],
  mixed_use: [38, 198, 218, 205],
  institutional: [102, 187, 106, 200],
  exempt: [120, 120, 120, 170],
};

export function landUseColor(landUse: string | null | undefined): RGBA {
  return (landUse && LAND_USE_COLORS[landUse]) || NO_DATA;
}

export const LAND_USE_LEGEND: { label: string; color: string }[] = [
  { label: "Residential", color: css(LAND_USE_COLORS.residential) },
  { label: "Multifamily", color: css(LAND_USE_COLORS.multi_family) },
  { label: "Commercial", color: css(LAND_USE_COLORS.commercial) },
  { label: "Industrial", color: css(LAND_USE_COLORS.industrial) },
  { label: "Vacant", color: css(LAND_USE_COLORS.vacant) },
];
