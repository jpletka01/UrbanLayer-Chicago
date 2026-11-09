// The new UI's map has no satellite view (Jack, 2026-11-07, Item 78): since Phase 5 it is our own MapLibre style
// over our own tiles (Items 90-91), with no raster source at all, and nothing in the new UI loads Mapbox. Today's
// place map keeps its satellite default.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildStyle } from "../map/mapStyle";

const seen: Array<{ style?: string; quiet?: boolean }> = [];
vi.mock("../../lib/useMapboxOverlay", () => ({
  useMapboxOverlay: (opts: { style?: string; quiet?: boolean }) => {
    seen.push({ style: opts.style, quiet: opts.quiet });
    return {
      containerRef: { current: null }, mapRef: { current: null }, overlayRef: { current: null },
      mapReady: false, mapError: null, contextRestored: 0, roadInsertionId: null, styleRevision: 0,
    };
  },
}));
vi.mock("../../contexts/ThemeContext", () => ({
  useThemeContext: () => ({ theme: "light", resolvedTheme: "light", setTheme: vi.fn() }),
}));
vi.mock("../../lib/api", () => ({ fetchTransitStations: () => Promise.resolve([]) }));

import { ParcelMap } from "../../components/scorecard/ParcelMap";

beforeEach(() => { seen.length = 0; vi.stubEnv("VITE_MAPBOX_TOKEN", "pk.test"); });
afterEach(() => { cleanup(); vi.unstubAllEnvs(); });

const SOURCES = import.meta.glob("../**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("the new map has no satellite", () => {
  it.each(["light", "dark"] as const)("its %s style has no raster or satellite source", (theme) => {
    const tiles = { base: { minZoom: 10, maxZoom: 16 }, parcels: { minZoom: 14, maxZoom: 16 }, zoning: { minZoom: 13, maxZoom: 16 } };
    const style = buildStyle({ theme, apiOrigin: "https://example.test", glyphsBase: "https://example.test/map/fonts", tiles });
    for (const src of Object.values(style.sources)) expect(["vector", "geojson"]).toContain(src.type);
    expect(style.layers.some((l) => l.type === "raster")).toBe(false);
    expect(JSON.stringify(style)).not.toMatch(/satellite|mapbox:\/\//i);
  });

  it("nothing in the new UI loads Mapbox or today's ParcelMap", () => {
    const offenders = Object.entries(SOURCES)
      .filter(([path]) => !path.endsWith(".test.tsx") && !path.endsWith(".test.ts"))
      .filter(([, text]) => /from ["'](mapbox-gl|@deck\.gl\/mapbox)["']|components\/scorecard\/ParcelMap|useMapboxOverlay/.test(text))
      .map(([path]) => path);
    expect(offenders).toEqual([]);
  });

  it("today's place map is unchanged: satellite by default, with its switch", () => {
    render(<ParcelMap variant="place" lat={41.9} lon={-87.7} />);
    expect(seen[0].style).toBe("mapbox://styles/mapbox/satellite-streets-v12");
    expect(seen[0].quiet).toBe(false);
    expect(screen.getByRole("button", { name: "Satellite" })).toBeTruthy();
  });
});
