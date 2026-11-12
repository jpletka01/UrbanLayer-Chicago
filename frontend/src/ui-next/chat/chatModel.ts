// The full chat page's pure model (Phase 8; brief "Chat"): what an answer offers as small previews (the lot, a
// map, its sources), the map's points, and the conversation's title. Answers lead with text; a preview opens only
// when the visitor asks for it.
import type { ContextObject, MapData, Message } from "../../lib/types";
import { countDataCategories } from "../../lib/contextSummary";

export type PreviewKind = "lot" | "map" | "data" | "sources";

export interface LotPreview { kind: "lot"; address: string; pin: string | null; href: string }
export interface MapPreview { kind: "map"; points: number; hasAddress: boolean }
export interface DataPreview { kind: "data"; count: number }
export interface SourcesPreview { kind: "sources"; count: number }
export type Preview = LotPreview | MapPreview | DataPreview | SourcesPreview;

/** The Profile link for an answer's lot: by PIN when the answer resolved one, else by address. */
export function lotHref(address: string, pin: string | null): string {
  const p = new URLSearchParams(pin ? { pin, address } : { address });
  return `/scorecard?${p}`;
}

/** Points the chat map would draw (crimes, 311 requests, permits with a location). */
export function mapPointCount(map: MapData | null | undefined): number {
  if (!map) return 0;
  const ok = (r: { latitude: number; longitude: number }) => Number.isFinite(r.latitude) && Number.isFinite(r.longitude);
  return map.crimes.filter(ok).length + map.requests_311.filter(ok).length + map.building_permits.filter(ok).length;
}

/** The previews under one finished answer, in a fixed order: the lot, the map, the data, the sources. */
export function previewsFor(message: Message): Preview[] {
  if (message.role !== "assistant" || !message.content) return [];
  const ctx: ContextObject | undefined = message.context;
  const out: Preview[] = [];
  const pin = ctx?.property?.pin14 ?? null;
  const address = ctx?.resolved_address ?? null;
  // A lot only when the answer resolved a parcel (its PIN, or zoning at the address), as today's chat links it.
  if (address && (pin || ctx?.parcel_zoning)) out.push({ kind: "lot", address, pin, href: lotHref(address, pin) });
  const points = mapPointCount(message.mapData);
  if (points > 0) out.push({ kind: "map", points, hasAddress: !!message.mapData?.queried_address });
  // The records the answer read (property, zoning rules, crime, permits, 311 …), the cards a data citation opens.
  const data = countDataCategories(ctx ?? null);
  if (data > 0) out.push({ kind: "data", count: data });
  const count = ctx?.code_chunks?.length ?? 0;
  if (count > 0) out.push({ kind: "sources", count });
  return out;
}

export type PointKind = "crime" | "request" | "permit";

/** The answer's points as GeoJSON for the chat map, each with its kind and a short label. */
export function mapPoints(map: MapData): GeoJSON.FeatureCollection<GeoJSON.Point> {
  const features: GeoJSON.Feature<GeoJSON.Point>[] = [];
  const add = (lon: number, lat: number, kind: PointKind, label: string, date: string) => {
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
    features.push({ type: "Feature", geometry: { type: "Point", coordinates: [lon, lat] }, properties: { kind, label, date } });
  };
  for (const c of map.crimes) add(c.longitude, c.latitude, "crime", c.primary_type, c.date);
  for (const r of map.requests_311) add(r.longitude, r.latitude, "request", r.sr_type, r.created_date);
  for (const p of map.building_permits) add(p.longitude, p.latitude, "permit", p.permit_type, p.issue_date);
  return { type: "FeatureCollection", features };
}

/** The map's frame: the asked-about address with its points, else the points alone. Null with nothing to frame. */
export function mapBounds(map: MapData): [[number, number], [number, number]] | null {
  const coords = mapPoints(map).features.map((f) => f.geometry.coordinates as [number, number]);
  const q = map.queried_address;
  if (q && Number.isFinite(q.latitude) && Number.isFinite(q.longitude)) coords.push([q.longitude, q.latitude]);
  if (coords.length === 0) return null;
  let [w, s, e, n] = [Infinity, Infinity, -Infinity, -Infinity];
  for (const [x, y] of coords) { w = Math.min(w, x); e = Math.max(e, x); s = Math.min(s, y); n = Math.max(n, y); }
  return [[w, s], [e, n]];
}

/** Counts by kind, for the map's key. */
export function pointCounts(map: MapData): Record<PointKind, number> {
  const out: Record<PointKind, number> = { crime: 0, request: 0, permit: 0 };
  for (const f of mapPoints(map).features) out[(f.properties as { kind: PointKind }).kind] += 1;
  return out;
}

/** The conversation's title: its first question, shortened like the stored title. */
export function chatTitle(messages: Message[]): string | null {
  const first = messages.find((m) => m.role === "user" && m.content.trim());
  if (!first) return null;
  const text = first.content.trim();
  return text.length > 50 ? `${text.slice(0, 47)}...` : text;
}
