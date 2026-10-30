import type { SourceTag } from "./types";
import i18n from "./i18n";

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

// JS port of backend.analytics._normalize_permit_type — keep the keyword
// list in sync or the sidebar buckets diverge from the chat context.
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

// Intents whose *subject* is the point data itself — the only case where the
// dot cloud auto-enables. A legal/overview question that happens to retrieve
// permits as supporting context keeps the dots behind the Points toggle.
const POINT_SUBJECT_INTENTS = new Set(["incident_lookup", "trend_analysis", "event_query"]);

export function pointsAreSubject(intent: string | null | undefined): boolean {
  return !!intent && POINT_SUBJECT_INTENTS.has(intent);
}

/** True when the map has anything renderable beyond the bare address pin —
 *  the sidebar hides the map entirely otherwise. */
export function hasSpatialMapContent(
  mapData: {
    crimes?: unknown[]; requests_311?: unknown[]; building_permits?: unknown[];
    zoning?: Record<string, unknown> | null;
    overlay_districts?: Record<string, unknown> | null;
    incentive_zones?: Record<string, unknown> | null;
  } | null | undefined,
  transitContext: boolean,
  parcelGeometry?: unknown,
): boolean {
  const feats = (g?: Record<string, unknown> | null) =>
    !!((g?.features as unknown[] | undefined)?.length);
  return !!(
    (mapData?.crimes?.length || mapData?.requests_311?.length || mapData?.building_permits?.length) ||
    feats(mapData?.zoning) || feats(mapData?.overlay_districts) || feats(mapData?.incentive_zones) ||
    transitContext || parcelGeometry
  );
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

// --- Zoning colors (exact Chicago district class + intensity) ---

export type MapTheme = "dark" | "light";

export interface ParsedZoneClass {
  /** Whitespace/case-normalized district identifier used for deterministic color. */
  exactClass: string;
  /** Title 17 family used by the existing labels/tooltips (B, RM, DX, PD, ...). */
  family: string;
  /** Family plus subtype where present (B3, C1, M2); never an intensity. */
  series: string;
  /** The dash suffix that communicates district intensity (including 4.5). */
  intensity: number | null;
  /** PD/PMD numbers identify an ordinance district; they are not intensity steps. */
  plannedDevelopment: boolean;
  knownFamily: boolean;
}

const ZONE_FAMILY_TONES: Record<string, { hue: number; saturation: number; darkLightness: number; lightLightness: number }> = {
  RS: { hue: 53, saturation: 88, darkLightness: 70, lightLightness: 55 },
  RT: { hue: 45, saturation: 86, darkLightness: 70, lightLightness: 56 },
  RM: { hue: 38, saturation: 88, darkLightness: 68, lightLightness: 53 },
  B: { hue: 215, saturation: 78, darkLightness: 70, lightLightness: 55 },
  C: { hue: 282, saturation: 62, darkLightness: 70, lightLightness: 54 },
  M: { hue: 334, saturation: 74, darkLightness: 69, lightLightness: 53 },
  D: { hue: 174, saturation: 70, darkLightness: 65, lightLightness: 46 },
  DC: { hue: 174, saturation: 72, darkLightness: 64, lightLightness: 44 },
  DX: { hue: 169, saturation: 66, darkLightness: 66, lightLightness: 47 },
  DR: { hue: 183, saturation: 58, darkLightness: 68, lightLightness: 48 },
  DS: { hue: 164, saturation: 72, darkLightness: 63, lightLightness: 43 },
  T: { hue: 24, saturation: 30, darkLightness: 67, lightLightness: 47 },
  P: { hue: 126, saturation: 50, darkLightness: 65, lightLightness: 44 },
  POS: { hue: 137, saturation: 43, darkLightness: 68, lightLightness: 48 },
};

const PLANNED_FAMILIES = new Set(["PD", "PMD"]);

function normalizeZoneClass(zoneClass: string): string {
  return (zoneClass || "")
    .trim()
    .toUpperCase()
    .replace(/\s*-\s*/g, "-")
    .replace(/\s+/g, " ");
}

/** Parse Chicago's exact district syntax without mistaking PD 799 for intensity 799. */
export function parseZoneClass(zoneClass: string): ParsedZoneClass {
  const exactClass = normalizeZoneClass(zoneClass);
  const leading = exactClass.match(/^([A-Z]+)/)?.[1] ?? "";
  if (PLANNED_FAMILIES.has(leading)) {
    return {
      exactClass,
      family: leading,
      series: leading,
      intensity: null,
      plannedDevelopment: true,
      knownFamily: true,
    };
  }

  // B3-2 / C1-3 / M2-3 carry a numeric subtype before the dash. RS-3,
  // RM-4.5 and DX-7 do not. In every case only the final dash value is the
  // intensity that controls the lightness step.
  const match = exactClass.match(/^([A-Z]+)(\d+)?(?:-(\d+(?:\.\d+)?))?$/);
  const family = match?.[1] ?? leading;
  const subtype = match?.[2] ?? "";
  const rawIntensity = match?.[3];
  const intensity = rawIntensity == null ? null : Number(rawIntensity);
  return {
    exactClass,
    family,
    series: `${family}${subtype}`,
    intensity: Number.isFinite(intensity) ? intensity : null,
    plannedDevelopment: false,
    knownFamily: family in ZONE_FAMILY_TONES,
  };
}

export function zonePrefix(zoneClass: string): string {
  return parseZoneClass(zoneClass).family;
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

function zoneRgb(zoneClass: string, theme: MapTheme): [number, number, number] {
  const parsed = parseZoneClass(zoneClass);
  if (parsed.plannedDevelopment) {
    const lightness = parsed.family === "PMD"
      ? (theme === "dark" ? 69 : 51)
      : (theme === "dark" ? 63 : 44);
    return hslToRgb(218, 8 / 100, lightness / 100);
  }

  const tone = ZONE_FAMILY_TONES[parsed.family];
  if (!tone) {
    // Unknown classes remain visibly neutral rather than acquiring a misleading
    // family hue. The small exact-class step makes the fallback deterministic.
    const lightness = (theme === "dark" ? 61 : 43) + ((hashStr(parsed.exactClass) % 7) - 3);
    return hslToRgb(215, 7 / 100, lightness / 100);
  }

  const base = theme === "dark" ? tone.darkLightness : tone.lightLightness;
  const intensityStep = parsed.intensity == null
    ? 0
    : Math.max(0, Math.min(22, (parsed.intensity - 1) * 5));
  const minLightness = theme === "dark" ? 45 : 31;
  const lightness = Math.max(minLightness, base - intensityStep);
  return hslToRgb(tone.hue, tone.saturation / 100, lightness / 100);
}

export function zoneColor(zoneClass: string, theme: MapTheme = "dark"): [number, number, number, number] {
  const rgb = zoneRgb(zoneClass, theme);
  return [rgb[0], rgb[1], rgb[2], 78];
}

export function zoneLineColor(zoneClass: string, theme: MapTheme = "dark"): [number, number, number, number] {
  const rgb = zoneRgb(zoneClass, theme);
  return [rgb[0], rgb[1], rgb[2], 220];
}

export function zoneColorCSS(zoneClass: string, theme: MapTheme = "dark"): string {
  const rgb = zoneRgb(zoneClass, theme);
  return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
}

// --- Boundary family colors (fixed semantics; orange stays parcel/action-only) ---

export type BoundaryFamily = "overlay" | "tif" | "enterprise_zone" | "other_incentive";

const BOUNDARY_FAMILY_COLORS: Record<MapTheme, Record<BoundaryFamily, [number, number, number]>> = {
  dark: {
    overlay: [92, 174, 255],
    tif: [190, 142, 255],
    enterprise_zone: [67, 205, 151],
    other_incentive: [95, 196, 207],
  },
  light: {
    overlay: [29, 101, 166],
    tif: [104, 61, 173],
    enterprise_zone: [5, 118, 83],
    other_incentive: [20, 109, 120],
  },
};

export function incentiveBoundaryFamily(zoneType: string, name = ""): BoundaryFamily {
  const value = `${zoneType} ${name}`.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (value.includes("enterprise_zone") || value.includes("enterprise")) return "enterprise_zone";
  if (value.includes("tif")) return "tif";
  return "other_incentive";
}

export function boundaryFillColor(family: BoundaryFamily, theme: MapTheme = "dark"): [number, number, number, number] {
  const rgb = BOUNDARY_FAMILY_COLORS[theme][family];
  // Boundary polygons overlap heavily at parcel scale. Keep identity on the
  // outline; even six stacked special-purpose overlays stay below a 15% wash.
  const alpha = family === "overlay" ? 6 : 7;
  return [rgb[0], rgb[1], rgb[2], alpha];
}

export function boundaryLineColor(family: BoundaryFamily, theme: MapTheme = "dark"): [number, number, number, number] {
  const rgb = BOUNDARY_FAMILY_COLORS[theme][family];
  return [rgb[0], rgb[1], rgb[2], 230];
}

export function boundaryColorCSS(family: BoundaryFamily, theme: MapTheme = "dark"): string {
  const rgb = BOUNDARY_FAMILY_COLORS[theme][family];
  return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
}

export function overlayColor(_type: string, theme: MapTheme = "dark"): [number, number, number, number] {
  return boundaryFillColor("overlay", theme);
}

export function overlayLineColor(_type: string, theme: MapTheme = "dark"): [number, number, number, number] {
  return boundaryLineColor("overlay", theme);
}

export function overlayColorCSS(_type: string, theme: MapTheme = "dark"): string {
  return boundaryColorCSS("overlay", theme);
}

export const OVERLAY_INFO: Record<string, { label: string; description: string; implications: string[] }> = {
  planned_development: {
    label: "Planned Development",
    description: "Custom zoning with site-specific rules negotiated with the city",
    implications: ["Special setback/FAR/height rules", "May require aldermanic review for changes"],
  },
  lakefront_protection: {
    label: "Lakefront Protection",
    description: "Extra design review and density limits near Lake Michigan",
    implications: ["Dept. of Planning review required", "Height/setback restrictions"],
  },
  pedestrian_street: {
    label: "Pedestrian Street",
    description: "Street-level retail required; no drive-throughs or parking lot frontage",
    implications: ["Ground-floor commercial mandatory", "No curb cuts on designated frontage"],
  },
  landmark_district: {
    label: "Landmark District",
    description: "Commission on Chicago Landmarks review for exterior alterations",
    implications: ["Permit review by Landmarks Commission", "Demolition restrictions"],
  },
  historic_district: {
    label: "Historic District",
    description: "State/local historic designation with preservation standards",
    implications: ["Tax credit eligibility", "Exterior modification review"],
  },
  landmark_building: {
    label: "Individual Landmark",
    description: "Single building designated as a Chicago Landmark",
    implications: ["Landmarks Commission permit review", "Demolition delay/prohibition"],
  },
  national_register: {
    label: "National Register District",
    description: "Listed on the National Register of Historic Places",
    implications: ["Federal tax credit eligibility (20%)", "Section 106 review for federal projects"],
  },
  special_district: {
    label: "Special District",
    description: "Additional regulations beyond the base zoning classification",
    implications: ["May impose design standards", "Additional use restrictions"],
  },
  fema_floodplain: {
    label: "FEMA Floodplain",
    description: "Federally-mapped flood hazard area",
    implications: ["Flood insurance required for mortgages", "Elevated construction may be required"],
  },
  pmd_subarea: {
    label: "PMD Subarea",
    description: "Protected manufacturing district with industrial use protections",
    implications: ["Residential conversion restricted", "Industrial uses protected"],
  },
  tod_cta: {
    label: "TOD (CTA)",
    description: "Transit-Oriented Development zone near CTA rail stations",
    implications: ["Reduced parking requirements", "Density bonuses only in dash-3 districts (with approval)"],
  },
  tod_metra: {
    label: "TOD (Metra)",
    description: "Transit-Oriented Development zone near Metra stations",
    implications: ["Reduced parking requirements", "Density bonuses only in dash-3 districts (with approval)"],
  },
  adu_area: {
    label: "ADU Eligible Area",
    description: "Eligible for Accessory Dwelling Units under the 2020 ADU ordinance",
    implications: ["Can add coach house/garden unit", "Converted garage units allowed"],
  },
  aro_zone: {
    label: "ARO Zone",
    description: "Affordable Requirements Ordinance area requiring affordable set-aside",
    implications: ["10–20% affordable units in new developments (10+ units)", "In-lieu fee option available"],
  },
  ssa: {
    label: "Special Service Area",
    description: "Local tax district funding streetscape, marketing, and maintenance",
    implications: ["Additional property tax levy", "Enhanced neighborhood services"],
  },
};

export function overlayLabel(type: string): string {
  const key = `map:overlays.${type}.label`;
  const translated = i18n.t(key);
  if (translated !== key) return translated;
  return OVERLAY_INFO[type]?.label ?? type.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let r = 0, g = 0, b = 0;
  if (h < 60) { r = c; g = x; }
  else if (h < 120) { r = x; g = c; }
  else if (h < 180) { g = c; b = x; }
  else if (h < 240) { g = x; b = c; }
  else if (h < 300) { r = x; b = c; }
  else { r = c; b = x; }
  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
}

export function incentiveZoneColor(
  name: string,
  zoneType = "",
  theme: MapTheme = "dark",
): [number, number, number, number] {
  return boundaryFillColor(incentiveBoundaryFamily(zoneType, name), theme);
}

export function incentiveZoneLineColor(
  name: string,
  zoneType = "",
  theme: MapTheme = "dark",
): [number, number, number, number] {
  return boundaryLineColor(incentiveBoundaryFamily(zoneType, name), theme);
}

export function incentiveZoneColorCSS(name: string, zoneType = "", theme: MapTheme = "dark"): string {
  return boundaryColorCSS(incentiveBoundaryFamily(zoneType, name), theme);
}

export function incentiveLabel(zoneType: string): string {
  const key = `map:incentiveLabels.${zoneType}`;
  const translated = i18n.t(key);
  if (translated !== key) return translated;
  return zoneType.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

export function zonePrefixLabel(prefix: string): string {
  const key = `map:zonePrefixLabels.${prefix}`;
  const translated = i18n.t(key);
  if (translated !== key) return translated;
  return ZONE_PREFIX_LABELS[prefix] ?? prefix;
}

export function capLabel(raw: string, max = 25): string {
  const upper = raw.toUpperCase();
  const crimeLabel = i18n.t(`crimeLabels.${upper}`, { ns: "map", defaultValue: "" });
  if (crimeLabel) return crimeLabel.length > max ? crimeLabel.slice(0, max - 1) + "…" : crimeLabel;
  const permitLabel = i18n.t(`permitLabels.${upper}`, { ns: "map", defaultValue: "" });
  if (permitLabel) return permitLabel.length > max ? permitLabel.slice(0, max - 1) + "…" : permitLabel;
  const srLabel = i18n.t(`srTypeLabels.${raw}`, { ns: "map", defaultValue: "" });
  if (srLabel) return srLabel.length > max ? srLabel.slice(0, max - 1) + "…" : srLabel;
  const deptLabel = i18n.t(`deptLabels.${raw}`, { ns: "map", defaultValue: "" });
  if (deptLabel) return deptLabel.length > max ? deptLabel.slice(0, max - 1) + "…" : deptLabel;
  const clean = raw.charAt(0) + raw.slice(1).toLowerCase().replace(/_/g, " ");
  return clean.length > max ? clean.slice(0, max - 1) + "…" : clean;
}
