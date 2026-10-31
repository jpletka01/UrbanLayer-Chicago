import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import i18n from "i18next";

vi.mock("../../lib/api", () => ({ fetchCapacityMap: vi.fn() }));
vi.mock("../../contexts/ThemeContext", () => ({ useThemeContext: () => ({ resolvedTheme: "light" }) }));
// No GL in jsdom: the canvas is a plain div, the panel (what these tests read) is real.
vi.mock("../../lib/useMapboxOverlay", () => ({
  useMapboxOverlay: () => ({
    containerRef: { current: null }, mapRef: { current: null }, overlayRef: { current: null },
    mapReady: false, contextRestored: 0, styleRevision: 0, roadInsertionId: null,
  }),
}));

import { fetchCapacityMap } from "../../lib/api";
import { CapacityMap } from "./CapacityMap";
import type { CapacityFeatureProps, CapacityMapResponse } from "./capacityMapModel";

const square: GeoJSON.Polygon = { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] };
const feat = (over: Partial<CapacityFeatureProps>) => ({
  type: "Feature" as const,
  geometry: square,
  properties: {
    pin10: "17-09-100-001", pin: null, state: "computable" as const, existing_far: 0.6, allowed_far: 1.2,
    utilization: 0.5, zone_class: "RT-4", confidence: "standard" as const, reason: null, ...over,
  },
});

function resp(over: Partial<CapacityMapResponse> = {}): CapacityMapResponse {
  const features = [feat({}), feat({ utilization: 0.1 }), feat({ state: "multi_pin_member", utilization: null })];
  return {
    radius_mi: 0.1,
    features: { type: "FeatureCollection", features },
    summary: { polygons: 3, colorable: 2, colorable_share: 0.6667, verdict: "standard", states: {} },
    sources: { index: { built_at: "2026-10-29" }, commercial_valuation: { year: "2024" } },
    unchecked: [],
    ...over,
  };
}

beforeEach(() => {
  vi.mocked(fetchCapacityMap).mockReset();
});
afterEach(async () => {
  cleanup();
  await i18n.changeLanguage("en");
});

describe("CapacityMap", () => {
  it("says how much of the view is colored and keys every parcel", async () => {
    vi.mocked(fetchCapacityMap).mockResolvedValue(resp());
    render(<CapacityMap pin="17-09-100-001-0000" lat={41.9} lon={-87.68} />);
    expect((await screen.findByTestId("capacity-coverage")).textContent).toContain("Colored: 2 of 3 parcels (67%).");
    const key = screen.getAllByTestId("capacity-key")[0];
    expect(within(key).getByText("Part of a multi-parcel complex (its total area covers several lots)")).toBeTruthy();
    expect(within(key).getByText("Under 25%")).toBeTruthy();
    expect((screen.getByTestId("capacity-sources")).textContent).toContain("2024 reassessment");
    expect(fetchCapacityMap).toHaveBeenCalledWith("17-09-100-001-0000", 41.9, -87.68);
  });

  it("a withheld view colors nothing and says why", async () => {
    vi.mocked(fetchCapacityMap).mockResolvedValue(resp({
      features: { type: "FeatureCollection", features: [feat({ utilization: null }), feat({ state: "unknown_gfa", utilization: null })] },
      summary: { polygons: 2, colorable: 1, colorable_share: 0.05, verdict: "withheld", states: {} },
    }));
    render(<CapacityMap lat={41.9} lon={-87.68} />);
    const cov = await screen.findByTestId("capacity-coverage");
    expect((cov).textContent).toContain("Only 1 of 2 parcels");
    expect((cov).textContent).toContain("too little to draw honestly");
    expect(within(screen.getAllByTestId("capacity-key")[0]).queryByText("Under 25%")).toBeNull();
  });

  it("a failed source is named, never read as none", async () => {
    vi.mocked(fetchCapacityMap).mockResolvedValue(resp({
      features: { type: "FeatureCollection", features: [] },
      summary: { polygons: 0, colorable: 0, colorable_share: 0, verdict: "unavailable", states: {} },
      unchecked: ["zoning"],
    }));
    render(<CapacityMap lat={41.9} lon={-87.68} />);
    expect((await screen.findByTestId("capacity-unchecked")).textContent).toContain("Couldn't check: the zoning map.");
  });

  it("a failed request says it is not a finding", async () => {
    vi.mocked(fetchCapacityMap).mockResolvedValue(null);
    render(<CapacityMap lat={41.9} lon={-87.68} />);
    await waitFor(() => expect((screen.getByRole("status")).textContent).toContain("not a finding"));
  });

  it("renders in Spanish", async () => {
    await i18n.changeLanguage("es");
    vi.mocked(fetchCapacityMap).mockResolvedValue(resp());
    render(<CapacityMap lat={41.9} lon={-87.68} />);
    expect((await screen.findByTestId("capacity-coverage")).textContent).toContain("Coloreadas: 2 de 3 parcelas");
    expect(screen.getByText("Cuánto de lo permitido está construido")).toBeTruthy();
  });
});
