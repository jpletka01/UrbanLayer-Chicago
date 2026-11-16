// The new map's style (map track M1, Items 90-91): our own tiles only, roads drawn over the fills, names only
// zoomed in, On / Dim / Off, and a theme switch that repaints every layer without a reload.
import { validateStyleMin } from "@maplibre/maplibre-gl-style-spec";
import { describe, expect, it } from "vitest";
import {
  CTA_COLORS, GROUPS, LAYER_IDS, ROAD_METERS, metersPerPixel, STREET_LABEL_MIN_ZOOM, ZONING_COLORS, buildStyle, groupLayerIds, modeOpacity, themePaint, versionedTiles,
  type MapTiles,
} from "./mapStyle";

const ALL: MapTiles = { base: { minZoom: 10, maxZoom: 16 }, parcels: { minZoom: 14, maxZoom: 16 }, zoning: { minZoom: 13, maxZoom: 16 } };
const input = (tiles: MapTiles = ALL) => ({ theme: "light" as const, apiOrigin: "https://urbanlayerchicago.com", glyphsBase: "https://urbanlayerchicago.com/map/fonts", tiles });

describe("the style document", () => {
  it("reads our tiles by absolute URL (the workers don't resolve relative ones, Item 68)", () => {
    const s = buildStyle(input());
    const urls = Object.values(s.sources).flatMap((src) => ("tiles" in src ? src.tiles ?? [] : []));
    expect(urls).toEqual([
      "https://urbanlayerchicago.com/api/map/tiles/base/{z}/{x}/{y}.mvt",
      "https://urbanlayerchicago.com/api/map/tiles/zoning/{z}/{x}/{y}.mvt",
      "https://urbanlayerchicago.com/api/discovery/tiles/{z}/{x}/{y}.mvt",
    ]);
    expect(s.glyphs).toBe("https://urbanlayerchicago.com/map/fonts/{fontstack}/{range}.pbf");
  });

  it("puts the parcel file's version in its tile URL, so a rebuild isn't hidden by the day-long cache (Item 112)", () => {
    const s = buildStyle(input({ ...ALL, parcels: { minZoom: 14, maxZoom: 16, version: "1800000000" } }));
    const parcels = s.sources.parcels as { tiles: string[] };
    expect(parcels.tiles).toEqual(["https://urbanlayerchicago.com/api/discovery/tiles/{z}/{x}/{y}.mvt?v=1800000000"]);
    expect(versionedTiles("/t/{z}.mvt", {})).toBe("/t/{z}.mvt");
  });

  it("draws streets above zoning and parcels, and the lot above the streets", () => {
    const ids = buildStyle(input()).layers.map((l) => l.id);
    const at = (id: string) => ids.indexOf(id);
    expect(at("road-local")).toBeGreaterThan(at("zoning-fill"));
    expect(at("road-local")).toBeGreaterThan(at("parcel-line"));
    expect(at("road-highway")).toBeGreaterThan(at("road-major"));
    expect(at("lot-line")).toBeGreaterThan(at("road-highway"));
    expect(at("road-label")).toBeGreaterThan(at("lot-line"));
    // Pins draw above everything, labels included, so a sale or a station is never hidden (Item 95).
    expect(at("sales-pin")).toBe(ids.length - 4);
    expect(at("transit-pin")).toBe(ids.length - 2);
    // The property's own pin is on top, and only when zoomed out (Item 96).
    expect(at("lot-pin")).toBe(ids.length - 1);
  });

  it("draws transit like Google Maps in its own Rail and transit group: colored lines with an edge, freight with ticks (Item 128)", () => {
    const ids = LAYER_IDS;
    expect(ids.indexOf("transit-line")).toBeGreaterThan(ids.indexOf("road-highway"));
    expect(ids.indexOf("transit-line")).toBeGreaterThan(ids.indexOf("transit-casing"));
    expect(ids.indexOf("transit-line")).toBeLessThan(ids.indexOf("lot-fill"));
    expect(groupLayerIds("rail")).toEqual(["rail-land", "rail", "rail-ties", "transit-casing", "transit-line", "station", "rail-label", "station-label"]);
    expect(groupLayerIds("streets")).not.toContain("rail");
    // rail land sits under the lots, so a lot paints over it and right-of-way with no lot still reads as rail land
    expect(ids.indexOf("rail-land")).toBeLessThan(ids.indexOf("parcel-line"));
    const s = buildStyle(input());
    const line = s.layers.find((l) => l.id === "transit-line") as { paint: Record<string, unknown> };
    const color = JSON.stringify(line.paint["line-color"]);
    for (const c of Object.values(CTA_COLORS)) expect(color).toContain(c);
    expect(color).toContain('["get","color"]');  // Metra in its own line colors
    expect(JSON.stringify(line.paint["line-offset"])).toContain('"o"');  // shared track side by side
    const label = s.layers.find((l) => l.id === "rail-label") as { minzoom?: number };
    expect(label.minzoom).toBe(STREET_LABEL_MIN_ZOOM);
    const station = s.layers.find((l) => l.id === "station") as { layout: Record<string, unknown> };
    expect(JSON.stringify(station.layout["icon-image"])).toContain("station-metra");
    // MapLibre's own validator accepts every layer (a nested zoom curve once blanked the whole map)
    for (const theme of ["light", "dark"] as const) {
      expect(validateStyleMin(buildStyle({ ...input(), theme }) as never).map((e) => e.message)).toEqual([]);
    }
    // no rail without the base tiles
    expect(buildStyle(input({ ...ALL, base: null })).layers.some((l) => l.id === "rail")).toBe(false);
  });

  it("puts the base file's version in its tile URL too, so the rebuilt base with rail shows at once (Item 128)", () => {
    const s = buildStyle(input({ ...ALL, base: { minZoom: 10, maxZoom: 16, version: "1800000001" } }));
    expect((s.sources.base as { tiles: string[] }).tiles).toEqual(["https://urbanlayerchicago.com/api/map/tiles/base/{z}/{x}/{y}.mvt?v=1800000001"]);
  });

  it("names streets only zoomed in", () => {
    const label = buildStyle(input()).layers.find((l) => l.id === "road-label")!;
    expect(label.minzoom).toBe(STREET_LABEL_MIN_ZOOM);
    expect(STREET_LABEL_MIN_ZOOM).toBeGreaterThanOrEqual(15);
  });

  it("leaves out the layers of a tile set the server doesn't have", () => {
    const ids = buildStyle(input({ base: null, parcels: null, zoning: null })).layers.map((l) => l.id);
    expect(ids).toEqual(["background", "lot-fill", "lot-edge", "lot-line", "sales-pin", "building-pin", "transit-pin", "lot-pin"]);
  });

  it("colors every zoning family in four steps", () => {
    for (const steps of Object.values(ZONING_COLORS)) expect(steps).toHaveLength(4);
  });
});

describe("themes and modes", () => {
  it("a theme switch sets paint on every layer, and light and dark differ", () => {
    const light = themePaint("light");
    const dark = themePaint("dark");
    expect(light.map((l) => l.id)).toEqual(LAYER_IDS);
    expect(light.find((l) => l.id === "background")!.paint).not.toEqual(dark.find((l) => l.id === "background")!.paint);
    // "This lot" is black in light and white in dark (Item 74).
    expect(light.find((l) => l.id === "lot-line")!.paint["line-color"]).toBe("#1C1C1C");
    expect(dark.find((l) => l.id === "lot-line")!.paint["line-color"]).toBe("#FFFFFF");
  });

  it("On / Off only (no Dim): Off hides a group, On restores the theme's opacity", () => {
    const on = modeOpacity("zoning", "on", "light");
    const off = modeOpacity("zoning", "off", "light");
    expect(on.every((w) => w.visible)).toBe(true);
    expect(off.every((w) => !w.visible)).toBe(true);
    expect(on.find((w) => w.id === "zoning-fill")!.paint["fill-opacity"]).toBe(0.42);
  });

  it("draws streets at their real width close in, so they fill the gap between lots", () => {
    const local = buildStyle(input()).layers.find((l) => l.id === "road-local") as { paint: Record<string, unknown> };
    const expr = local.paint["line-width"] as unknown[];
    expect(expr[1]).toEqual(["exponential", 2]);
    // zoom 20 stop = the street's metres in pixels
    expect(expr[expr.length - 1]).toBeCloseTo(ROAD_METERS.local / metersPerPixel(20));
    // at zoom 16 a 16 m local street is about 9 px wide
    expect(ROAD_METERS.local / metersPerPixel(16)).toBeGreaterThan(8);
  });

  it("every group the key offers owns at least one layer", () => {
    for (const g of GROUPS) expect(groupLayerIds(g).length).toBeGreaterThan(0);
  });
});
