import type { SourceTag } from "./types";

export const CRIME_TYPE_COLORS: Record<string, [number, number, number, number]> = {
  // Violent — hot reds
  HOMICIDE: [183, 28, 28, 210],
  "CRIM SEXUAL ASSAULT": [198, 40, 40, 200],
  KIDNAPPING: [211, 47, 47, 190],
  ASSAULT: [229, 57, 53, 180],
  BATTERY: [239, 83, 80, 180],
  ROBBERY: [220, 50, 50, 200],
  "HUMAN TRAFFICKING": [191, 27, 44, 200],
  "OFFENSE INVOLVING CHILDREN": [213, 0, 0, 190],
  "SEX OFFENSE": [194, 24, 91, 180],

  // Aggressive / weapons — deep oranges
  ARSON: [255, 87, 34, 190],
  "WEAPONS VIOLATION": [191, 54, 12, 180],
  INTIMIDATION: [244, 81, 30, 180],
  STALKING: [230, 74, 25, 170],

  // Property — ambers, warm oranges
  THEFT: [239, 159, 39, 180],
  BURGLARY: [255, 112, 67, 180],
  "MOTOR VEHICLE THEFT": [171, 71, 188, 180],
  "CRIMINAL DAMAGE": [255, 167, 38, 160],
  "CRIMINAL TRESPASS": [255, 183, 77, 170],

  // Drug / vice — purples
  NARCOTICS: [127, 119, 221, 180],
  PROSTITUTION: [186, 104, 200, 160],
  "OTHER NARCOTIC VIOLATION": [149, 117, 205, 170],

  // Non-violent / white-collar — cool blues, teals
  "DECEPTIVE PRACTICE": [66, 165, 245, 170],
  "PUBLIC PEACE VIOLATION": [77, 182, 172, 160],
  "INTERFERENCE WITH PUBLIC OFFICER": [100, 181, 246, 160],
  "LIQUOR LAW VIOLATION": [120, 144, 156, 160],
  GAMBLING: [149, 165, 166, 160],
  "CONCEALED CARRY LICENSE VIOLATION": [141, 182, 205, 160],
  "NON-CRIMINAL": [176, 190, 197, 150],
  OBSCENITY: [158, 158, 158, 150],

  // Catch-all
  "OTHER OFFENSE": [158, 158, 158, 160],
};

const CRIME_FALLBACK: [number, number, number, number] = [158, 158, 158, 160];

const EXTRA_PALETTE: [number, number, number, number][] = [
  [102, 187, 106, 180],
  [0, 150, 136, 180],
  [236, 64, 122, 180],
  [255, 202, 40, 180],
  [141, 110, 99, 180],
  [120, 144, 156, 180],
  [38, 198, 218, 180],
  [255, 138, 101, 180],
];

function hashToColor(s: string): [number, number, number, number] {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  return EXTRA_PALETTE[Math.abs(h) % EXTRA_PALETTE.length];
}

export function crimeColor(type: string): [number, number, number, number] {
  return CRIME_TYPE_COLORS[type] ?? CRIME_FALLBACK;
}

export const DEPT_COLORS: Record<string, [number, number, number, number]> = {
  "Streets & Sanitation": [0, 188, 212, 180],
  Buildings: [255, 112, 67, 180],
  CDOT: [66, 165, 245, 180],
};

export function deptColor(dept: string): [number, number, number, number] {
  if (dept?.includes("Streets") || dept?.includes("Sanitation")) return DEPT_COLORS["Streets & Sanitation"];
  if (dept?.includes("Buildings") || dept?.includes("BLDG")) return DEPT_COLORS.Buildings;
  if (dept?.includes("CDOT") || dept?.includes("Transportation")) return DEPT_COLORS.CDOT;
  return [158, 158, 158, 140];
}

export function normalizeDept(dept: string): string {
  if (dept?.includes("Streets") || dept?.includes("Sanitation")) return "Streets & Sanitation";
  if (dept?.includes("Buildings") || dept?.includes("BLDG")) return "Buildings";
  if (dept?.includes("CDOT") || dept?.includes("Transportation")) return "CDOT";
  return dept || "Other";
}

export const PERMIT_COLOR: [number, number, number, number] = [99, 153, 34, 180];

export const PERMIT_TYPE_COLORS: Record<string, [number, number, number, number]> = {
  "EXPRESS PERMIT": [0, 188, 212, 180],
  "RENOVATION/ALTERATION": [255, 152, 0, 180],
  "SIGNS": [156, 39, 176, 180],
  "NEW CONSTRUCTION": [76, 175, 80, 180],
  "WRECKING/DEMOLITION": [244, 67, 54, 180],
  "ELEVATOR EQUIPMENT": [255, 193, 7, 180],
};

export const PERMIT_TYPE_ORDER = [
  "EXPRESS PERMIT", "RENOVATION/ALTERATION", "SIGNS",
  "NEW CONSTRUCTION", "WRECKING/DEMOLITION", "ELEVATOR EQUIPMENT",
];

export function normalizePermitType(raw: string): string {
  const upper = (raw || "").toUpperCase();
  if (upper.includes("EXPRESS")) return "EXPRESS PERMIT";
  if (upper.includes("RENOVATION") || upper.includes("ALTERATION")) return "RENOVATION/ALTERATION";
  if (upper.includes("SIGN")) return "SIGNS";
  if (upper.includes("NEW CONSTRUCTION")) return "NEW CONSTRUCTION";
  if (upper.includes("WRECK") || upper.includes("DEMOLITION")) return "WRECKING/DEMOLITION";
  if (upper.includes("ELEVATOR")) return "ELEVATOR EQUIPMENT";
  return upper.replace(/^PERMIT\s*[-–—]\s*/i, "").trim() || "OTHER";
}

export function permitColor(type: string): [number, number, number, number] {
  return PERMIT_TYPE_COLORS[normalizePermitType(type)] ?? hashToColor(type);
}

const SR_TYPE_PALETTE: [number, number, number, number][] = [
  [0, 188, 212, 180],
  [255, 112, 67, 180],
  [66, 165, 245, 180],
  [171, 71, 188, 180],
  [102, 187, 106, 180],
  [255, 167, 38, 180],
  [239, 83, 80, 180],
  [141, 110, 99, 180],
  [255, 202, 40, 180],
  [236, 64, 122, 180],
  [0, 150, 136, 180],
  [120, 144, 156, 180],
];

function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export function srTypeMapColor(type: string): [number, number, number, number] {
  return SR_TYPE_PALETTE[hashStr(type) % SR_TYPE_PALETTE.length];
}

export function srTypeMapColorCSS(type: string): string {
  const c = srTypeMapColor(type);
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export type FilterMode = "overview" | "crime" | "311" | "permits";

export function deriveFilterMode(sources: SourceTag[]): FilterMode {
  const mapped = sources.filter(s => s === "crime_api" || s === "311_api" || s === "permits_api");
  if (mapped.length === 1) {
    if (mapped[0] === "crime_api") return "crime";
    if (mapped[0] === "311_api") return "311";
    if (mapped[0] === "permits_api") return "permits";
  }
  return "overview";
}

export const CRIME_TYPE_ORDER = [
  "THEFT", "BATTERY", "CRIMINAL DAMAGE", "ASSAULT", "DECEPTIVE PRACTICE",
  "OTHER OFFENSE", "NARCOTICS", "BURGLARY", "MOTOR VEHICLE THEFT", "ROBBERY",
  "WEAPONS VIOLATION", "CRIMINAL TRESPASS", "OFFENSE INVOLVING CHILDREN",
  "PUBLIC PEACE VIOLATION", "SEX OFFENSE", "CRIM SEXUAL ASSAULT",
  "STALKING", "HOMICIDE", "ARSON", "KIDNAPPING", "INTIMIDATION",
  "PROSTITUTION", "INTERFERENCE WITH PUBLIC OFFICER", "LIQUOR LAW VIOLATION",
  "GAMBLING", "CONCEALED CARRY LICENSE VIOLATION", "HUMAN TRAFFICKING",
];

export function crimeColorCSS(type: string): string {
  const c = CRIME_TYPE_COLORS[type] ?? CRIME_FALLBACK;
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function deptColorCSS(dept: string): string {
  const normalized = normalizeDept(dept);
  const c = DEPT_COLORS[normalized];
  if (!c) return "rgb(158,158,158)";
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function permitColorCSS(type?: string): string {
  if (type) {
    const c = PERMIT_TYPE_COLORS[normalizePermitType(type)] ?? hashToColor(type);
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }
  return `rgb(${PERMIT_COLOR[0]},${PERMIT_COLOR[1]},${PERMIT_COLOR[2]})`;
}

export function isArrested(arrest: boolean | string): boolean {
  return arrest === true || arrest === "true";
}
