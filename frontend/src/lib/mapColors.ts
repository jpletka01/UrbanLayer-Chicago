import type { SourceTag } from "./types";

export const CRIME_TYPE_COLORS: Record<string, [number, number, number, number]> = {
  THEFT: [239, 159, 39, 180],
  BATTERY: [226, 75, 74, 180],
  ASSAULT: [226, 75, 74, 180],
  ROBBERY: [220, 50, 50, 200],
  NARCOTICS: [127, 119, 221, 180],
  "CRIMINAL DAMAGE": [255, 167, 38, 160],
  BURGLARY: [255, 112, 67, 180],
  "MOTOR VEHICLE THEFT": [171, 71, 188, 180],
};

export function crimeColor(type: string): [number, number, number, number] {
  return CRIME_TYPE_COLORS[type] ?? [136, 135, 128, 140];
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

export const CRIME_TYPE_ORDER = ["THEFT", "BATTERY", "ASSAULT", "ROBBERY", "NARCOTICS", "CRIMINAL DAMAGE", "BURGLARY", "MOTOR VEHICLE THEFT"];

export function crimeColorCSS(type: string): string {
  const c = CRIME_TYPE_COLORS[type];
  if (!c) return "rgb(136,135,128)";
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function deptColorCSS(dept: string): string {
  const normalized = normalizeDept(dept);
  const c = DEPT_COLORS[normalized];
  if (!c) return "rgb(158,158,158)";
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function permitColorCSS(): string {
  return `rgb(${PERMIT_COLOR[0]},${PERMIT_COLOR[1]},${PERMIT_COLOR[2]})`;
}

export function isArrested(arrest: boolean | string): boolean {
  return arrest === true || arrest === "true";
}
