// Discovery in the new UI (decision Item 104): the pure pieces. Nothing here evaluates a search (INV-1/INV-4): the
// quick filters only compile into a panel the server evaluates, and the map's measure colors read the tiles' own
// banded properties (display only, like the zoning colors).
import type { PanelState, Predicate, ResultRow } from "../../discovery/types";
import { rowTitle } from "../../discovery/rowFigures";

// ---------------------------------------------------------------- quick filters (the owner's five, 2026-11-10)

export type QuickId = "vacant" | "nearL" | "lot5k" | "sold2y" | "tif";
export const QUICK_FILTERS: Array<{ id: QuickId; filter: string; predicate: Predicate }> = [
  { id: "vacant", filter: "vacancy", predicate: { kind: "flag", value: true } },
  { id: "nearL", filter: "transit_proximity", predicate: { kind: "range", max: 0.5 } },
  { id: "lot5k", filter: "lot_size", predicate: { kind: "range", min: 5000 } },
  { id: "sold2y", filter: "sale_recency", predicate: { kind: "range", max: 730 } },
  { id: "tif", filter: "tif", predicate: { kind: "flag", value: true } },
];

/** The panel a set of quick filters compiles to (the server evaluates it). */
export function quickPanel(on: ReadonlySet<QuickId>, base: PanelState = {}): PanelState {
  const panel: PanelState = { ...base };
  for (const q of QUICK_FILTERS) {
    if (on.has(q.id)) panel[q.filter] = q.predicate as PanelState[string];
    else if (base[q.filter] && samePredicate(base[q.filter] as Predicate, q.predicate)) delete panel[q.filter];
  }
  return panel;
}

/** Which quick filters a panel already holds exactly (a goal can turn some on). */
export function quickFromPanel(panel: PanelState): Set<QuickId> {
  const on = new Set<QuickId>();
  for (const q of QUICK_FILTERS) {
    const p = panel[q.filter] as Predicate | undefined;
    if (p && samePredicate(p, q.predicate)) on.add(q.id);
  }
  return on;
}

function samePredicate(a: Predicate, b: Predicate): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

// ---------------------------------------------------------------- the map's measure

export type MeasureId = "room" | "lot" | "sale" | "use" | "zoning";
export const MEASURES: MeasureId[] = ["room", "lot", "sale", "use", "zoning"];
export const DEFAULT_MEASURE: MeasureId = "room";

/** The tile property each measure reads (`backend/discovery/lot_facts.measure_bands`; zoning is the family `g`). */
export const MEASURE_PROP: Record<MeasureId, string> = { room: "r", lot: "s", sale: "y", use: "u", zoning: "g" };

// Sequential steps from Sapphire to Spruce (Item 74: maps use Sapphire, Spruce and black); lighter = less.
const SEQ = ["#DCEDEB", "#A9D2CE", "#72B0AB", "#4A867E", "#2C4F4A"];
// Last sale: recent is darkest (where the market is moving).
const SALE = [SEQ[4], SEQ[3], SEQ[2], SEQ[1], SEQ[0]];
// The named "room" states: planned development gray (the zoning map's PD gray), park green, transportation peach.
const NAMED = { own: "#8F959C", park: "#A7E2B2", transport: "#FDC1B4" };
// Land use: Coastal's five and a gray, each named in the key (never color alone).
export const USE_COLORS = ["#B89D47", "#DCEDEB", "#72B0AB", "#FE9179", "#355E58", "#B4B4B4"];

export interface MeasureStep { value: string; color: string; key: string }

/** Each measure's steps in the key's order: the tile value, its color and its words (i18n key under `discovery.measure`). */
export function measureSteps(m: MeasureId): MeasureStep[] {
  switch (m) {
    case "room": return [
      ...SEQ.map((color, i) => ({ value: String(i), color, key: `room.${i}` })),
      // No base FAR is named, not unknown (owner's review): its own ordinance, open space, a transportation zone.
      { value: "x", color: NAMED.own, key: "room.own" },
      { value: "p", color: NAMED.park, key: "room.park" },
      { value: "t", color: NAMED.transport, key: "room.transport" },
    ];
    case "lot": return SEQ.map((color, i) => ({ value: String(i), color, key: `lot.${i}` }));
    case "sale": return SALE.map((color, i) => ({ value: String(i), color, key: `sale.${i}` }));
    case "use": return USE_COLORS.map((color, i) => ({ value: String(i), color, key: `use.${i}` }));
    case "zoning": return [];
  }
}

/** The MapLibre color expression for a measure (zoning uses the map's own family colors, passed in). */
export function measureColorExpr(m: MeasureId, zoningFamily?: Record<string, string>): unknown {
  const prop = MEASURE_PROP[m];
  if (m === "zoning") {
    const expr: unknown[] = ["match", ["get", prop]];
    for (const [fam, color] of Object.entries(zoningFamily ?? {})) expr.push(fam, color);
    expr.push("rgba(0,0,0,0)");
    return expr;
  }
  const expr: unknown[] = ["match", ["get", prop]];
  for (const s of measureSteps(m)) expr.push(s.value, s.color);
  expr.push("rgba(0,0,0,0)");
  return expr;
}

/** Below this zoom the map shows community areas; lots from here up (the lot tiles start at 14). */
export const LOTS_MIN_ZOOM = 14;

// ---------------------------------------------------------------- list cards

export type CardWarning = NonNullable<ResultRow["warning"]>;

export interface CardModel {
  title: string;
  approx: boolean;
  zone: string | null;
  lotSqft: number | null;
  roomSqft: number | null;
  /** Where the building area behind "room to build" came from, when it isn't the Assessor's own record. */
  roomBasis: "commercial_valuation" | "footprint" | "city_land_inventory" | null;
  /** Why there is no room figure, when it isn't unknown: set by its own ordinance, open space, transportation. */
  roomNamed: "own_rules" | "open_space" | "transport" | null;
  /** A strip under 16 ft wide (hidden by default), with its width in feet. */
  narrowFt: number | null;
  /** The room is the multi-parcel site's (this many lots), not the lot's alone. */
  complexLots: number | null;
  sale: { price: number; year: string; transfer: boolean } | null;
  warning: CardWarning | null;
}

/** A sale under $10,000 is a transfer, not a market price (the County's own filter, Item 89). */
export const TRANSFER_BELOW = 10_000;

export function cardModel(row: ResultRow): CardModel {
  const { title, approx } = rowTitle(row);
  const src = row.bldg_sqft_source;
  const basis = src === "commercial_valuation" || src === "footprint" || src === "city_land_inventory" ? src : null;
  const named = row.room_scope === "own_rules" || row.room_scope === "open_space" || row.room_scope === "transport" ? row.room_scope : null;
  const room = row.room_sqft ?? null;
  return {
    title,
    approx,
    zone: row.zone_class ?? null,
    lotSqft: row.lot_sqft ?? null,
    roomSqft: room,
    roomBasis: room != null ? basis : null,
    roomNamed: room == null ? named : null,
    narrowFt: row.narrow_strip && row.lot_width_ft != null ? Math.round(row.lot_width_ft) : null,
    complexLots: room != null && row.room_scope === "complex" ? row.complex_lots ?? null : null,
    sale: row.last_sale_price != null && row.last_sale_date
      ? { price: row.last_sale_price, year: row.last_sale_date.slice(0, 4), transfer: row.last_sale_price < TRANSFER_BELOW }
      : null,
    warning: row.warning ?? (row.nominal_assessment ? { kind: "nominal" } : null),
  };
}

// ---------------------------------------------------------------- the search box

export type SearchKind =
  | { kind: "address" } | { kind: "area"; id: number; name: string } | { kind: "hood"; slug: string; name: string } | { kind: "describe" };

/** A place to search within: one of the City's 98 neighborhoods, else one of the 77 community areas (Item 104). */
export type Place = { kind: "hood"; slug: string; name: string } | { kind: "area"; id: number; name: string };
export const placeRegion = (p: Place) => (p.kind === "hood" ? `hood:${p.slug}` : `neighborhood:${p.id}`);

/** What the one search box was given: an address (starts with a house number), a community area by name, or a
    description for the rule-based compiler. */
export function classifyQuery(text: string, areas: Record<number, string>, hoods: Array<{ slug: string; name: string }> = []): SearchKind {
  const t = text.trim();
  if (/^\d+\s+\S/.test(t)) return { kind: "address" };
  const lower = t.toLowerCase();
  for (const h of hoods) if (h.name.toLowerCase() === lower) return { kind: "hood", slug: h.slug, name: h.name };
  for (const [id, name] of Object.entries(areas)) {
    if (name.toLowerCase() === lower) return { kind: "area", id: Number(id), name };
  }
  return { kind: "describe" };
}

/** Community areas whose name starts with (or has a word starting with) the typed text: the box's suggestions. */
export function areaSuggestions(text: string, areas: Record<number, string>, limit = 4): Array<{ id: number; name: string }> {
  const t = text.trim().toLowerCase();
  if (t.length < 2 || /^\d/.test(t)) return [];
  return Object.entries(areas)
    .filter(([, name]) => matchesStart(name, t))
    .slice(0, limit)
    .map(([id, name]) => ({ id: Number(id), name }));
}

const matchesStart = (name: string, t: string) => name.toLowerCase().startsWith(t) || name.toLowerCase().split(/[\s-]+/).some((w) => w.startsWith(t));

/** Places matching the typed text: neighborhoods first, then community areas not already named that way. */
export function placeSuggestions(text: string, areas: Record<number, string>, hoods: Array<{ slug: string; name: string }>, limit = 5): Place[] {
  const t = text.trim().toLowerCase();
  if (t.length < 2 || /^\d/.test(t)) return [];
  const out: Place[] = hoods.filter((h) => matchesStart(h.name, t)).map((h) => ({ kind: "hood", slug: h.slug, name: h.name }));
  const named = new Set(out.map((p) => p.name.toLowerCase()));
  for (const a of areaSuggestions(text, areas, limit)) if (!named.has(a.name.toLowerCase())) out.push({ kind: "area", id: a.id, name: a.name });
  return out.slice(0, limit);
}

/** The new page's default order: most room to build first (lots with no figure last; the server sorts). */
export const ROOM_SORT = { key: "room_to_build", dir: "desc" } as const;

/** The miles in a ring's region handle (`radius:<lat>,<lon>,<mi>`), for its chip. */
export function ringMiles(region: string | undefined): number | null {
  const m = /^radius:[^,]+,[^,]+,([\d.]+)$/.exec(region ?? "");
  return m ? Number(m[1]) : null;
}

/** Transit as one control: a walk in minutes to the nearest L stop (the index has L stations only, 20 min a mile). */
export const TRANSIT_WALKS = [{ minutes: 5, mi: 0.25 }, { minutes: 10, mi: 0.5 }, { minutes: 15, mi: 0.75 }];

// ---------------------------------------------------------------- the ring

export const RING_MILES = [0.25, 0.5, 1] as const;
export const RING_MIN_MI = 0.1;
export const RING_MAX_MI = 2;

/** The radius filter's region handle (`parcel_index`: `radius:<lat>,<lon>,<mi>`). */
export function ringRegion(lat: number, lon: number, miles: number): string {
  return `radius:${lat.toFixed(6)},${lon.toFixed(6)},${miles.toFixed(2)}`;
}

/** A circle polygon (lon/lat) of `miles` around a point, for drawing the ring. */
export function ringPolygon(lat: number, lon: number, miles: number, steps = 72): GeoJSON.Polygon {
  const km = miles * 1.609344;
  const dLat = km / 111.132;
  const dLon = km / (111.32 * Math.cos((lat * Math.PI) / 180));
  const ring: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * 2 * Math.PI;
    ring.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)]);
  }
  return { type: "Polygon", coordinates: [ring] };
}

/** Miles from a point to another (the drag handle's new radius). */
export function milesBetween(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const r = Math.PI / 180;
  const x = (bLon - aLon) * r * Math.cos(((aLat + bLat) / 2) * r);
  const y = (bLat - aLat) * r;
  return (Math.sqrt(x * x + y * y) * 6371) / 1.609344;
}

export const clampMiles = (mi: number) => Math.min(RING_MAX_MI, Math.max(RING_MIN_MI, Math.round(mi * 20) / 20));
