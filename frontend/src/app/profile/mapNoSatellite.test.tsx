// The new UI's map has no satellite view (Jack, 2026-11-07, Item 78): since Phase 5 it is our own MapLibre style
// over our own tiles (Items 90-91), with no raster source at all, and nothing in the site loads Mapbox (the old UI's satellite place map
// went with it in Phase 10).
import { describe, expect, it } from "vitest";
import { buildStyle } from "../map/mapStyle";

const SOURCES = import.meta.glob("../../**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("the new map has no satellite", () => {
  it.each(["light", "dark"] as const)("its %s style has no raster or satellite source", (theme) => {
    const tiles = { base: { minZoom: 10, maxZoom: 16 }, parcels: { minZoom: 14, maxZoom: 16 }, zoning: { minZoom: 13, maxZoom: 16 } };
    const style = buildStyle({ theme, apiOrigin: "https://example.test", glyphsBase: "https://example.test/map/fonts", tiles });
    for (const src of Object.values(style.sources)) expect(["vector", "geojson"]).toContain(src.type);
    expect(style.layers.some((l) => l.type === "raster")).toBe(false);
    expect(JSON.stringify(style)).not.toMatch(/satellite|mapbox:\/\//i);
  });

  it("nothing in the site loads Mapbox", () => {
    const offenders = Object.entries(SOURCES)
      .filter(([path]) => !path.endsWith(".test.tsx") && !path.endsWith(".test.ts"))
      .filter(([, text]) => /from ["'](mapbox-gl|@deck\.gl\/mapbox)["']|components\/scorecard\/ParcelMap|useMapboxOverlay/.test(text))
      .map(([path]) => path);
    expect(offenders).toEqual([]);
  });
});
