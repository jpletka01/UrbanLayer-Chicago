// What each record in the evidence panel shows (wireframe v2): the same pieces as the Profile's tabs, built from what
// the answer carries. Near the lot (½ mile) when the chat placed the address; otherwise the whole community area, and
// the views say which. Pure.
import type { ContextObject, MapData, PropertySummary } from "../../lib/types";
import { HALF_MILE_M, buildKind, crimeKind, distanceM, lensView, permitUnits, type BuildKind, type CrimeKind } from "./chatLens";

export interface Place { lat: number; lon: number; label: string }

export function placeOf(map: MapData | undefined): Place | null {
  const q = map?.queried_address;
  return q ? { lat: q.latitude, lon: q.longitude, label: q.label } : null;
}

const near = (place: Place | null, p: { latitude: number; longitude: number }) =>
  Number.isFinite(p.latitude) && Number.isFinite(p.longitude) && (!place || distanceM(place.lat, place.lon, p.latitude, p.longitude) <= HALF_MILE_M);

export interface CrimeRecord {
  scope: "near" | "area";
  total: number;
  violent: number;
  property: number;
  arrests: number | null;
  byType: Array<{ type: string; n: number; kind: CrimeKind }>;
  moreTypes: { types: number; n: number };
  areaTotal: number | null;
}

/** Crime near the lot from the answer's points; the community area's summary when there is no point. */
export function crimeRecord(ctx: ContextObject | undefined, map: MapData | undefined): CrimeRecord | null {
  const place = placeOf(map);
  const counts = new Map<string, number>();
  let arrests: number | null = null;
  let total = 0;
  if (place && map && map.crimes.length > 0) {
    arrests = 0;
    for (const c of map.crimes) {
      if (!near(place, c)) continue;
      total += 1;
      counts.set(c.primary_type, (counts.get(c.primary_type) ?? 0) + 1);
      if (c.arrest === true || c.arrest === "true") arrests += 1;
    }
  } else if (ctx?.crime_last_90d) {
    for (const [type, n] of Object.entries(ctx.crime_last_90d.by_type)) { counts.set(type, n); total += n; }
  } else {
    return null;
  }
  const all = [...counts.entries()].map(([type, n]) => ({ type, n, kind: crimeKind({ primary_type: type }) })).sort((a, b) => b.n - a.n);
  const top = all.slice(0, 5);
  const rest = all.slice(5);
  return {
    scope: place && map && map.crimes.length > 0 ? "near" : "area",
    total,
    violent: all.filter((t) => t.kind === "violent").reduce((s, t) => s + t.n, 0),
    property: all.filter((t) => t.kind === "property").reduce((s, t) => s + t.n, 0),
    arrests,
    byType: top,
    moreTypes: { types: rest.length, n: rest.reduce((s, t) => s + t.n, 0) },
    areaTotal: ctx?.crime_last_90d?.total ?? null,
  };
}

export interface BuildCard { kind: BuildKind; units: number | null; cost: number; date: string; description: string; distanceM: number | null; lat: number; lon: number }
export interface ConstructionRecord { scope: "near" | "area"; cards: BuildCard[]; shown: number; leftOut: number }

/** New buildings, demolitions and big renovations: nearest first near the lot, else the biggest in the area. */
export function constructionRecord(map: MapData | undefined): ConstructionRecord | null {
  if (!map || map.building_permits.length === 0) return null;
  const place = placeOf(map);
  if (place) {
    const v = lensView(map, "construction");
    const big = map.building_permits
      .map((p) => ({ p, kind: buildKind(p), d: distanceM(place.lat, place.lon, p.latitude, p.longitude) }))
      .filter((x): x is typeof x & { kind: BuildKind } => x.kind !== null && x.d <= HALF_MILE_M)
      .sort((a, b) => a.d - b.d);
    return {
      scope: "near",
      shown: v.counts.shown,
      leftOut: map.building_permits.filter((p) => near(place, p)).length - v.counts.shown,
      cards: big.slice(0, 5).map(({ p, kind, d }) => ({ kind, units: permitUnits(p.work_description), cost: p.estimated_cost ?? 0, date: p.issue_date, description: p.work_description, distanceM: Math.round(d), lat: p.latitude, lon: p.longitude })),
    };
  }
  const big = map.building_permits
    .map((p) => ({ p, kind: buildKind(p) }))
    .filter((x): x is typeof x & { kind: BuildKind } => x.kind !== null)
    .sort((a, b) => (b.p.estimated_cost ?? 0) - (a.p.estimated_cost ?? 0));
  return {
    scope: "area",
    shown: big.length,
    leftOut: map.building_permits.length - big.length,
    cards: big.slice(0, 5).map(({ p, kind }) => ({ kind, units: permitUnits(p.work_description), cost: p.estimated_cost ?? 0, date: p.issue_date, description: p.work_description, distanceM: null, lat: p.latitude, lon: p.longitude })),
  };
}

export interface RequestsRecord { scope: "near" | "area"; total: number; rows: Array<{ type: string; n: number; open: number }> }

/** 311 requests by type, open ones counted apart; the area's top types when there are no points. */
export function requestsRecord(ctx: ContextObject | undefined, map: MapData | undefined): RequestsRecord | null {
  const place = placeOf(map);
  if (map && map.requests_311.length > 0) {
    const by = new Map<string, { n: number; open: number }>();
    let total = 0;
    for (const r of map.requests_311) {
      if (!near(place, r)) continue;
      total += 1;
      const row = by.get(r.sr_type) ?? { n: 0, open: 0 };
      row.n += 1;
      if (!/complete|closed/i.test(r.status ?? "")) row.open += 1;
      by.set(r.sr_type, row);
    }
    const rows = [...by.entries()].map(([type, v]) => ({ type, ...v })).sort((a, b) => b.n - a.n).slice(0, 5);
    return { scope: place ? "near" : "area", total, rows };
  }
  const s = ctx?.open_311_requests;
  if (!s) return null;
  return { scope: "area", total: s.total, rows: s.top_types.slice(0, 5).map((type) => ({ type, n: 0, open: 0 })) };
}

export interface FactTile { key: "lot" | "building" | "tax" | "sale"; value: number; note: string | number | null }

/** The lot's facts as the Profile's Overview tiles: only what the record has; a sale only when it was a market sale. */
export function factTiles(p: PropertySummary | null | undefined): FactTile[] {
  if (!p) return [];
  const out: FactTile[] = [];
  if (p.land_sqft) out.push({ key: "lot", value: p.land_sqft, note: null });
  if (p.units) out.push({ key: "building", value: p.units, note: p.bldg_sqft ?? null });
  if (p.estimated_annual_tax && !p.tax_exempt && !p.nominal_assessment) out.push({ key: "tax", value: p.estimated_annual_tax, note: p.tax_year ?? null });
  const sale = [...(p.sales_history ?? [])].filter((s) => s.arms_length === true && (s.price ?? 0) > 0 && s.date).sort((a, b) => (b.date! > a.date! ? 1 : -1))[0];
  if (sale) out.push({ key: "sale", value: sale.price!, note: sale.date });
  return out;
}
