// The new map's style (map track M1, Items 90-91): our own tiles only, roads drawn over the fills, names only
// zoomed in, On / Dim / Off, and a theme switch that repaints every layer without a reload.
import { describe, expect, it } from "vitest";
import {
  GROUPS, LAYER_IDS, ROAD_METERS, metersPerPixel, STREET_LABEL_MIN_ZOOM, ZONING_COLORS, buildStyle, groupLayerIds, modeOpacity, themePaint,
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

  it("draws streets above zoning and parcels, and the lot above the streets", () => {
    const ids = buildStyle(input()).layers.map((l) => l.id);
    const at = (id: string) => ids.indexOf(id);
    expect(at("road-local")).toBeGreaterThan(at("zoning-fill"));
    expect(at("road-local")).toBeGreaterThan(at("parcel-line"));
    expect(at("road-highway")).toBeGreaterThan(at("road-major"));
    expect(at("lot-line")).toBeGreaterThan(at("road-highway"));
    expect(at("road-label")).toBeGreaterThan(at("lot-line"));
    // Pins draw above everything, labels included, so a sale or a station is never hidden (Item 95).
    expect(at("sales-pin")).toBe(ids.length - 3);
    expect(at("transit-pin")).toBe(ids.length - 2);
    // The property's own pin is on top, and only when zoomed out (Item 96).
    expect(at("lot-pin")).toBe(ids.length - 1);
  });

  it("names streets only zoomed in", () => {
    const label = buildStyle(input()).layers.find((l) => l.id === "road-label")!;
    expect(label.minzoom).toBe(STREET_LABEL_MIN_ZOOM);
    expect(STREET_LABEL_MIN_ZOOM).toBeGreaterThanOrEqual(15);
  });

  it("leaves out the layers of a tile set the server doesn't have", () => {
    const ids = buildStyle(input({ base: null, parcels: null, zoning: null })).layers.map((l) => l.id);
    expect(ids).toEqual(["background", "lot-fill", "lot-edge", "lot-line", "sales-pin", "transit-pin", "lot-pin"]);
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
