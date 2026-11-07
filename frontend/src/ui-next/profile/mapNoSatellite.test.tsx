// The new UI's map has no satellite view (Jack, 2026-11-07): it opens on the quiet street base for the theme, and
// there is no satellite switch. Today's place map keeps its satellite default.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

describe("the new map has no satellite", () => {
  it("opens on the theme's street style, quiet, with no satellite switch", () => {
    render(<ParcelMap variant="place" look="next" lat={41.9} lon={-87.7} />);
    expect(seen[0].style).toBe("mapbox://styles/mapbox/light-v11");
    expect(seen[0].quiet).toBe(true);
    expect(screen.queryByRole("button", { name: "Satellite" })).toBeNull();
  });

  it("today's place map is unchanged: satellite by default, with its switch", () => {
    render(<ParcelMap variant="place" lat={41.9} lon={-87.7} />);
    expect(seen[0].style).toBe("mapbox://styles/mapbox/satellite-streets-v12");
    expect(seen[0].quiet).toBe(false);
    expect(screen.getByRole("button", { name: "Satellite" })).toBeTruthy();
  });
});
