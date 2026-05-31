import type { SourceTag } from "./types";

export const CRIME_TYPE_COLORS: Record<string, [number, number, number, number]> = {
  // Violent — hot reds
  HOMICIDE: [183, 28, 28, 210],
  "CRIMINAL SEXUAL ASSAULT": [198, 40, 40, 200],
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
  "NON-CRIMINAL (SUBJECT SPECIFIED)": [176, 190, 197, 150],
  OBSCENITY: [158, 158, 158, 150],
  "PUBLIC INDECENCY": [194, 143, 158, 160],

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
  "Buildings": [255, 112, 67, 180],
  "CDOT": [66, 165, 245, 180],
  "Water Management": [33, 150, 243, 180],
  "Aviation": [171, 71, 188, 180],
  "Animal Care": [102, 187, 106, 180],
  "311 City Services": [255, 167, 38, 180],
  "Finance": [255, 202, 40, 180],
  "BACP": [236, 64, 122, 180],
  "Health": [239, 83, 80, 180],
  "Fire": [244, 67, 54, 180],
  "Housing": [141, 110, 99, 180],
  "City Clerk": [120, 144, 156, 180],
  "Outside Agencies": [158, 158, 158, 160],
};

export const DEPT_ORDER = [
  "Streets & Sanitation", "CDOT", "Buildings", "Water Management",
  "Aviation", "Animal Care", "311 City Services", "Finance",
  "BACP", "Health", "Fire", "Housing", "City Clerk", "Outside Agencies",
];

export function deptColor(dept: string): [number, number, number, number] {
  return DEPT_COLORS[normalizeDept(dept)] ?? [158, 158, 158, 140];
}

export function normalizeDept(dept: string): string {
  if (!dept) return "Other";
  if (dept.includes("Streets") || dept.includes("Sanitation")) return "Streets & Sanitation";
  if (dept.includes("DOB") || dept === "Buildings" || dept.includes("BLDG")) return "Buildings";
  if (dept.includes("CDOT") || dept.includes("Transportation")) return "CDOT";
  if (dept.includes("Water")) return "Water Management";
  if (dept.includes("Aviation")) return "Aviation";
  if (dept.includes("Animal")) return "Animal Care";
  if (dept.includes("311")) return "311 City Services";
  if (dept.includes("Finance")) return "Finance";
  if (dept.includes("BACP") || dept.includes("Business Affairs") || dept.includes("Consumer")) return "BACP";
  if (dept.includes("Health")) return "Health";
  if (dept.includes("Fire")) return "Fire";
  if (dept.includes("Housing")) return "Housing";
  if (dept.includes("Clerk")) return "City Clerk";
  if (dept.includes("Outside")) return "Outside Agencies";
  return dept;
}

export const PERMIT_COLOR: [number, number, number, number] = [99, 153, 34, 180];

export const PERMIT_TYPE_COLORS: Record<string, [number, number, number, number]> = {
  "EXPRESS PERMIT": [0, 188, 212, 180],
  "RENOVATION/ALTERATION": [255, 152, 0, 180],
  "SIGNS": [156, 39, 176, 180],
  "NEW CONSTRUCTION": [76, 175, 80, 180],
  "ELEVATOR EQUIPMENT": [255, 193, 7, 180],
  "WRECKING/DEMOLITION": [244, 67, 54, 180],
  "REINSTATE REVOKED PMT": [141, 110, 99, 180],
  "EASY PERMIT PROCESS": [120, 144, 156, 180],
};

export const PERMIT_TYPE_ORDER = [
  "EXPRESS PERMIT", "RENOVATION/ALTERATION", "SIGNS",
  "NEW CONSTRUCTION", "ELEVATOR EQUIPMENT", "WRECKING/DEMOLITION",
  "REINSTATE REVOKED PMT", "EASY PERMIT PROCESS",
];

export function normalizePermitType(raw: string): string {
  const upper = (raw || "").toUpperCase();
  if (upper.includes("EXPRESS")) return "EXPRESS PERMIT";
  if (upper.includes("RENOVATION") || upper.includes("ALTERATION")) return "RENOVATION/ALTERATION";
  if (upper.includes("SIGN")) return "SIGNS";
  if (upper.includes("NEW CONSTRUCTION")) return "NEW CONSTRUCTION";
  if (upper.includes("WRECK") || upper.includes("DEMOLITION")) return "WRECKING/DEMOLITION";
  if (upper.includes("ELEVATOR")) return "ELEVATOR EQUIPMENT";
  if (upper.includes("REINSTATE")) return "REINSTATE REVOKED PMT";
  if (upper.includes("EASY PERMIT")) return "EASY PERMIT PROCESS";
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
  "THEFT", "BATTERY", "CRIMINAL DAMAGE", "ASSAULT", "MOTOR VEHICLE THEFT",
  "OTHER OFFENSE", "DECEPTIVE PRACTICE", "NARCOTICS", "BURGLARY", "ROBBERY",
  "WEAPONS VIOLATION", "CRIMINAL TRESPASS", "CRIMINAL SEXUAL ASSAULT",
  "OFFENSE INVOLVING CHILDREN", "SEX OFFENSE", "PUBLIC PEACE VIOLATION",
  "INTERFERENCE WITH PUBLIC OFFICER", "STALKING", "HOMICIDE", "ARSON",
  "CONCEALED CARRY LICENSE VIOLATION", "LIQUOR LAW VIOLATION", "INTIMIDATION",
  "PROSTITUTION", "KIDNAPPING", "OBSCENITY", "PUBLIC INDECENCY",
  "HUMAN TRAFFICKING", "GAMBLING", "OTHER NARCOTIC VIOLATION", "NON-CRIMINAL",
];

export function crimeColorCSS(type: string): string {
  const c = CRIME_TYPE_COLORS[type] ?? CRIME_FALLBACK;
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function deptColorCSS(dept: string): string {
  const c = deptColor(dept);
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

// --- Zoning colors (Chicago standard scheme) ---

const ZONE_PREFIX_COLORS: Record<string, [number, number, number]> = {
  RS: [255, 235, 59],     // Yellow — single-family residential
  RT: [255, 224, 130],    // Light yellow — two-flat residential
  RM: [255, 213, 79],     // Gold — multi-unit residential
  B:  [66, 133, 244],     // Blue — business
  C:  [156, 39, 176],     // Purple — commercial
  M:  [233, 30, 99],      // Magenta/pink — manufacturing
  PD: [158, 158, 158],    // Gray — planned development
  PMD:[176, 176, 176],    // Light gray — planned manufacturing
  D:  [0, 150, 136],      // Teal — downtown core
  DC: [0, 150, 136],      // Teal — downtown core
  DX: [38, 166, 154],     // Light teal — downtown mixed-use
  DR: [77, 182, 172],     // Aqua — downtown residential
  DS: [0, 137, 123],      // Dark teal — downtown service
  T:  [141, 110, 99],     // Brown — transportation
  P:  [76, 175, 80],      // Green — parks
  POS:[102, 187, 106],    // Light green — open space
};

const ZONE_FALLBACK: [number, number, number] = [120, 120, 120];

export function zonePrefix(zoneClass: string): string {
  const s = (zoneClass || "").trim().toUpperCase();
  // "PD 799" → "PD", "PMD 3" → "PMD", "RS-3" → "RS", "B3-2" → "B", "DX-7" → "DX"
  const m = s.match(/^([A-Z]+)/);
  return m ? m[1] : "";
}

export const ZONE_PREFIX_LABELS: Record<string, string> = {
  RS: "Residential Single-Unit",
  RT: "Residential Two-Flat",
  RM: "Residential Multi-Unit",
  B: "Business",
  C: "Commercial",
  M: "Manufacturing",
  PD: "Planned Development",
  PMD: "Planned Manufacturing",
  D: "Downtown Core",
  DC: "Downtown Core",
  DX: "Downtown Mixed-Use",
  DR: "Downtown Residential",
  DS: "Downtown Service",
  T: "Transportation",
  P: "Parks",
  POS: "Public Open Space",
};

export const ZONE_INFO: Record<string, { label: string; description: string; examples: string[] }> = {
  RS: { label: "Residential Single-Unit", description: "Detached single-family homes on individual lots", examples: ["Single-family house", "Home office", "Accessory garage"] },
  RT: { label: "Residential Two-Flat", description: "Two-unit residential buildings and townhouses", examples: ["Two-flat building", "Townhouse", "Coach house"] },
  RM: { label: "Residential Multi-Unit", description: "Apartment buildings and multi-unit residential", examples: ["Apartment building", "Condo building", "Senior housing"] },
  B: { label: "Business", description: "Neighborhood retail, offices, and mixed-use", examples: ["Retail store", "Restaurant", "Office space"] },
  C: { label: "Commercial", description: "Larger commercial and auto-oriented uses", examples: ["Auto repair shop", "Shopping center", "Gas station"] },
  M: { label: "Manufacturing", description: "Industrial and manufacturing uses", examples: ["Warehouse", "Factory", "Distribution center"] },
  PD: { label: "Planned Development", description: "Custom site-specific development with negotiated terms", examples: ["Mixed-use complex", "Large residential development"] },
  PMD: { label: "Planned Manufacturing", description: "Protected industrial corridors", examples: ["Industrial campus", "Manufacturing facility"] },
  D: { label: "Downtown Core", description: "High-density downtown offices and retail", examples: ["Office tower", "Department store", "Hotel"] },
  DC: { label: "Downtown Core", description: "High-density downtown offices and retail", examples: ["Office tower", "Department store", "Hotel"] },
  DX: { label: "Downtown Mixed-Use", description: "Mixed residential, office, and retail in the Loop", examples: ["Mixed-use tower", "Residential high-rise"] },
  DR: { label: "Downtown Residential", description: "Residential towers in downtown Chicago", examples: ["Condo tower", "Apartment high-rise"] },
  DS: { label: "Downtown Service", description: "Service and support uses in downtown", examples: ["Parking structure", "Utility facility"] },
  T: { label: "Transportation", description: "Transit-related corridors and facilities", examples: ["Transit station", "Rail corridor"] },
  P: { label: "Parks & Open Space", description: "Public parks, recreation areas, and open space", examples: ["Public park", "Playground", "Nature preserve"] },
  POS: { label: "Parks & Open Space", description: "Public parks, recreation areas, and open space", examples: ["Public park", "Playground", "Nature preserve"] },
};

export function zoneColor(zoneClass: string): [number, number, number, number] {
  const rgb = ZONE_PREFIX_COLORS[zonePrefix(zoneClass)] ?? ZONE_FALLBACK;
  return [rgb[0], rgb[1], rgb[2], 80];
}

export function zoneLineColor(zoneClass: string): [number, number, number, number] {
  const rgb = ZONE_PREFIX_COLORS[zonePrefix(zoneClass)] ?? ZONE_FALLBACK;
  return [rgb[0], rgb[1], rgb[2], 180];
}

export function zoneColorCSS(zoneClass: string): string {
  const rgb = ZONE_PREFIX_COLORS[zonePrefix(zoneClass)] ?? ZONE_FALLBACK;
  return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
}

export function capLabel(raw: string, max = 25): string {
  const clean = raw.charAt(0) + raw.slice(1).toLowerCase().replace(/_/g, " ");
  return clean.length > max ? clean.slice(0, max - 1) + "…" : clean;
}
