import type { MapData } from "./types";

// Wicker Park / West Town (CA 24) bounding box: approx 41.895–41.915 lat, -87.665–-87.685 lon
function lat() { return 41.895 + Math.random() * 0.02; }
function lon() { return -87.685 + Math.random() * 0.02; }
function daysAgo(d: number) {
  const dt = new Date();
  dt.setDate(dt.getDate() - d);
  return dt.toISOString();
}

const CRIME_DIST: [string, string, number][] = [
  ["THEFT", "OVER $500", 22],
  ["THEFT", "$500 AND UNDER", 18],
  ["BATTERY", "SIMPLE", 14],
  ["BATTERY", "DOMESTIC BATTERY SIMPLE", 8],
  ["CRIMINAL DAMAGE", "TO PROPERTY", 10],
  ["MOTOR VEHICLE THEFT", "AUTOMOBILE", 7],
  ["ASSAULT", "SIMPLE", 5],
  ["DECEPTIVE PRACTICE", "FRAUD OR CONFIDENCE GAME", 4],
  ["BURGLARY", "FORCIBLE ENTRY", 3],
  ["ROBBERY", "ARMED - HANDGUN", 3],
  ["NARCOTICS", "POSSESS - CANNABIS 30GMS OR LESS", 2],
  ["OTHER OFFENSE", "HARASSMENT BY TELEPHONE", 2],
  ["CRIMINAL TRESPASS", "TO LAND", 2],
];

const SR_TYPES: [string, string, number][] = [
  ["Pothole in Street Complaint", "Streets & Sanitation", 12],
  ["Graffiti Removal Request", "Streets & Sanitation", 8],
  ["Rodent Baiting/Rat Complaint", "Streets & Sanitation", 7],
  ["Street Light Out Complaint", "CDOT", 5],
  ["Tree Trim Request", "Streets & Sanitation", 4],
  ["Abandoned Vehicle Complaint", "Streets & Sanitation", 4],
  ["Building Violation", "Buildings", 3],
  ["Alley Light Out Complaint", "CDOT", 3],
  ["Garbage Cart Complaint", "Streets & Sanitation", 2],
  ["Water in Street Complaint", "Water Management", 2],
];

const PERMIT_TYPES: [string, string, number, number][] = [
  ["PERMIT - RENOVATION/ALTERATION", "INTERIOR AND EXTERIOR RENOVATION", 6, 75000],
  ["PERMIT - EASY PERMIT PROCESS", "REPLACE WINDOWS AND DOORS", 4, 12000],
  ["PERMIT - SIGNS", "INSTALL SIGN ON BUILDING FRONT", 3, 5000],
  ["PERMIT - WRECKING/DEMOLITION", "DEMOLISH EXISTING STRUCTURE", 2, 25000],
  ["PERMIT - NEW CONSTRUCTION", "ERECT NEW ADDITION", 2, 180000],
  ["PERMIT - RENOVATION/ALTERATION", "ELECTRICAL WORK", 3, 8000],
];

function buildCrimes() {
  const crimes: MapData["crimes"] = [];
  for (const [type, desc, count] of CRIME_DIST) {
    for (let i = 0; i < count; i++) {
      crimes.push({
        latitude: lat(), longitude: lon(),
        primary_type: type, description: desc,
        date: daysAgo(Math.floor(Math.random() * 85) + 1),
        arrest: Math.random() < 0.18,
      });
    }
  }
  return crimes;
}

function buildRequests() {
  const reqs: MapData["requests_311"] = [];
  for (const [srType, dept, count] of SR_TYPES) {
    for (let i = 0; i < count; i++) {
      reqs.push({
        latitude: lat(), longitude: lon(),
        sr_type: srType, owner_department: dept,
        status: Math.random() < 0.6 ? "Open" : "Completed",
        created_date: daysAgo(Math.floor(Math.random() * 85) + 1),
      });
    }
  }
  return reqs;
}

function buildPermits() {
  const permits: MapData["building_permits"] = [];
  for (const [type, desc, count, baseCost] of PERMIT_TYPES) {
    for (let i = 0; i < count; i++) {
      permits.push({
        latitude: lat(), longitude: lon(),
        permit_type: type, work_description: desc,
        estimated_cost: baseCost + Math.floor(Math.random() * baseCost * 0.5),
        issue_date: daysAgo(Math.floor(Math.random() * 85) + 1),
      });
    }
  }
  return permits;
}

let cached: MapData | null = null;

export function getDummyMapData(): MapData {
  if (cached) return cached;
  cached = {
    crimes: buildCrimes(),
    requests_311: buildRequests(),
    building_permits: buildPermits(),
    zoning: null,
    queried_address: null,
    capped: {},
  };
  return cached;
}

export const DUMMY_COMMUNITY_AREA = 24;
export const DUMMY_COMMUNITY_AREA_NAME = "West Town";
