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
