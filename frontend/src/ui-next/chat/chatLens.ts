// What a chat answer's map shows, picked by the question (owner's review 2026-11-12; proposal "Chat maps by
// question"). One map, several lenses. Raw pins are never the default: an answer about a lot shows the lot and its
// rules, a safety question shows counts in small squares around the lot, a construction question shows only new
// buildings, demolitions and big renovations, each within a radius of the asked-about address. Pure: the map draws
// what these return.
import type { MapCrime, MapData, MapPermit, Message } from "../../lib/types";

export type Lens = "lot" | "safety" | "construction" | "area";

const SUBJECT_INTENTS = new Set(["incident_lookup", "trend_analysis", "event_query"]);

/** The lens for an answer: a question about incidents gets the lens of its subject (crime first, then permits); one
    with an address gets the lot; anything else the area summary. Null: nothing to map. */
export function chooseLens(message: Pick<Message, "plan" | "mapData">): Lens | null {
  const map = message.mapData;
  if (!map) return null;
  const sources = message.plan?.sources ?? [];
  const intent = message.plan?.intent ?? "";
  const hasAddress = !!map.queried_address;
  if (SUBJECT_INTENTS.has(intent) || !hasAddress) {
    if (sources.includes("crime_api") && map.crimes.length > 0) return "safety";
    if (sources.includes("permits_api") && map.building_permits.length > 0) return "construction";
  }
  if (hasAddress) return "lot";
  return map.crimes.length + map.building_permits.length + map.requests_311.length > 0 ? "area" : null;
}

/** Metres between two points (haversine). */
export function distanceM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const r = 6_371_000, rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad, dLon = (lon2 - lon1) * rad;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
}

export const QUARTER_MILE_M = 402;
export const HALF_MILE_M = 805;

/** A circle as a polygon, for the radius ring. */
export function circle(lat: number, lon: number, radiusM: number, steps = 64): GeoJSON.Polygon {
  const coords: Array<[number, number]> = [];
  const dLat = radiusM / 111_320;
  const dLon = radiusM / (111_320 * Math.cos((lat * Math.PI) / 180));
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * 2 * Math.PI;
    coords.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)]);
  }
  return { type: "Polygon", coordinates: [coords] };
}

/** Squares about a block wide (≈ 125 m), each with how many points fall in it. */
export function squareCounts(points: Array<{ latitude: number; longitude: number }>, sizeM = 125): GeoJSON.FeatureCollection<GeoJSON.Polygon> {
  if (points.length === 0) return { type: "FeatureCollection", features: [] };
  const lat0 = points[0].latitude;
  const dLat = sizeM / 111_320, dLon = sizeM / (111_320 * Math.cos((lat0 * Math.PI) / 180));
  const cells = new Map<string, { i: number; j: number; n: number }>();
  for (const p of points) {
    const i = Math.floor(p.longitude / dLon), j = Math.floor(p.latitude / dLat);
    const k = `${i}:${j}`;
    const c = cells.get(k) ?? { i, j, n: 0 };
    c.n += 1;
    cells.set(k, c);
  }
  const max = Math.max(...[...cells.values()].map((c) => c.n));
  return {
    type: "FeatureCollection",
    features: [...cells.values()].map(({ i, j, n }) => {
      const [w, s] = [i * dLon, j * dLat];
      return {
        type: "Feature",
        properties: { n, share: n / max },
        geometry: { type: "Polygon", coordinates: [[[w, s], [w + dLon, s], [w + dLon, s + dLat], [w, s + dLat], [w, s]]] },
      };
    }),
  };
}

// The same split as the Profile's crime figures (backend main.py CRIME_VIOLENT / CRIME_PROPERTY).
const VIOLENT = new Set(["HOMICIDE", "CRIMINAL SEXUAL ASSAULT", "CRIM SEXUAL ASSAULT", "ROBBERY", "ASSAULT", "BATTERY", "KIDNAPPING", "HUMAN TRAFFICKING"]);
const PROPERTY = new Set(["BURGLARY", "THEFT", "MOTOR VEHICLE THEFT", "ARSON", "CRIMINAL DAMAGE"]);
export type CrimeKind = "violent" | "property" | "other";
export function crimeKind(c: Pick<MapCrime, "primary_type">): CrimeKind {
  const t = (c.primary_type ?? "").toUpperCase();
  return VIOLENT.has(t) ? "violent" : PROPERTY.has(t) ? "property" : "other";
}

/** Big enough to change a block: new buildings, demolitions, and renovations of $500,000 or more. Express permits,
    signs, elevators and small renovations (most of the City's permits) are left out. */
export const MAJOR_RENOVATION_USD = 500_000;
export type BuildKind = "new" | "demolition" | "renovation";
export function buildKind(p: Pick<MapPermit, "permit_type" | "estimated_cost">): BuildKind | null {
  const t = (p.permit_type ?? "").toUpperCase();
  if (t.includes("NEW CONSTRUCTION")) return "new";
  if (t.includes("WRECKING") || t.includes("DEMOLITION")) return "demolition";
  if (t.includes("RENOVATION") && (p.estimated_cost ?? 0) >= MAJOR_RENOVATION_USD) return "renovation";
  return null;
}

/** Dwelling units a permit's own words name ("3 DWELLING UNITS", "4 RESIDENTIAL UNIT(S)"), else null. */
export function permitUnits(description: string | null | undefined): number | null {
  const m = /(\d{1,4})\s+(?:NEW\s+)?(?:DWELLING|RESIDENTIAL)\s+UNIT/i.exec(description ?? "");
  const n = m ? Number(m[1]) : NaN;
  return Number.isFinite(n) && n > 0 ? n : null;
}

export interface LensView {
  lens: Lens;
  center: { lat: number; lon: number; label: string } | null;
  ring: GeoJSON.Polygon | null;
  radiusM: number | null;
  /** Counts by square (safety, area). */
  squares: GeoJSON.FeatureCollection<GeoJSON.Polygon> | null;
  /** The few points shown one by one. */
  pins: GeoJSON.FeatureCollection<GeoJSON.Point>;
  /** Counts for the key. */
  counts: { shown: number; inArea: number; violent?: number; property?: number; recentNear?: number };
  /** Construction: the closest ones, nearest first, for the list beside the map. */
  closest: Array<{ kind: BuildKind; description: string; cost: number; units: number | null; date: string; distanceM: number }>;
}

/** Recent safety pins: the last 30 days within a quarter mile, only when there are few enough to read. */
export const SAFETY_PIN_DAYS = 30;
export const SAFETY_PIN_MAX = 50;

export function lensView(map: MapData, lens: Lens, now = Date.now()): LensView {
  const q = map.queried_address;
  const center = q ? { lat: q.latitude, lon: q.longitude, label: q.label } : null;
  const near = (p: { latitude: number; longitude: number }, r: number) =>
    !center || distanceM(center.lat, center.lon, p.latitude, p.longitude) <= r;
  const located = <T extends { latitude: number; longitude: number }>(xs: T[]) => xs.filter((p) => Number.isFinite(p.latitude) && Number.isFinite(p.longitude));
  const empty: GeoJSON.FeatureCollection<GeoJSON.Point> = { type: "FeatureCollection", features: [] };
  const base: Omit<LensView, "lens" | "counts"> = { center, ring: null, radiusM: null, squares: null, pins: empty, closest: [] };

  if (lens === "lot") {
    return { ...base, lens, counts: { shown: 0, inArea: 0 } };
  }

  if (lens === "safety" || lens === "area") {
    const all = located(lens === "safety" ? map.crimes : [...map.crimes, ...map.requests_311, ...map.building_permits]);
    const radius = center ? HALF_MILE_M : null;
    const within = all.filter((p) => near(p, HALF_MILE_M));
    const crimes = within as MapCrime[];
    const recent = lens === "safety" && center
      ? located(map.crimes).filter((c) => near(c, QUARTER_MILE_M) && now - Date.parse(c.date) <= SAFETY_PIN_DAYS * 86_400_000)
      : [];
    const pins: GeoJSON.FeatureCollection<GeoJSON.Point> = recent.length > 0 && recent.length < SAFETY_PIN_MAX
      ? { type: "FeatureCollection", features: recent.map((c) => ({ type: "Feature", geometry: { type: "Point", coordinates: [c.longitude, c.latitude] }, properties: { kind: crimeKind(c), label: c.primary_type, date: c.date } })) }
      : empty;
    return {
      ...base,
      lens,
      ring: center && radius ? circle(center.lat, center.lon, radius) : null,
      radiusM: radius,
      squares: squareCounts(within),
      pins,
      counts: {
        shown: within.length,
        inArea: all.length,
        ...(lens === "safety" ? { violent: crimes.filter((c) => crimeKind(c) === "violent").length, property: crimes.filter((c) => crimeKind(c) === "property").length, recentNear: recent.length } : {}),
      },
    };
  }

  // construction
  const permits = located(map.building_permits);
  const big = permits
    .map((p) => ({ p, kind: buildKind(p), d: center ? distanceM(center.lat, center.lon, p.latitude, p.longitude) : 0 }))
    .filter((x): x is { p: MapPermit; kind: BuildKind; d: number } => x.kind !== null && (!center || x.d <= HALF_MILE_M))
    .sort((a, b) => a.d - b.d);
  return {
    ...base,
    lens,
    ring: center ? circle(center.lat, center.lon, HALF_MILE_M) : null,
    radiusM: center ? HALF_MILE_M : null,
    pins: {
      type: "FeatureCollection",
      features: big.map(({ p, kind }) => ({ type: "Feature", geometry: { type: "Point", coordinates: [p.longitude, p.latitude] }, properties: { kind, cost: p.estimated_cost ?? 0, units: permitUnits(p.work_description) ?? 0 } })),
    },
    counts: { shown: big.length, inArea: permits.length },
    closest: big.slice(0, 5).map(({ p, kind, d }) => ({ kind, description: p.work_description, cost: p.estimated_cost ?? 0, units: permitUnits(p.work_description), date: p.issue_date, distanceM: Math.round(d) })),
  };
}
