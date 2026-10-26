import { describe, expect, it } from "vitest";
import { reviseMapStyleOrder, selectRoadLineInsertionPoint } from "./mapLayerOrder";

// Recorded, order-preserving slices around the first road line from Mapbox's
// dark-v11 and light-v11 styles. Non-road layers are retained so the selector
// cannot pass merely by choosing the first line in either fixture.
const DARK_V11_LAYERS = [
  { id: "background", type: "background" },
  { id: "land", type: "fill", "source-layer": "landuse" },
  { id: "admin-1-boundary-bg", type: "line", "source-layer": "admin" },
  { id: "road-path", type: "line", "source-layer": "road" },
  { id: "road-steps", type: "line", "source-layer": "road" },
  { id: "road-label-simple", type: "symbol", "source-layer": "road" },
] as const;

const LIGHT_V11_LAYERS = [
  { id: "background", type: "background" },
  { id: "land", type: "fill", "source-layer": "landuse" },
  { id: "admin-0-boundary-bg", type: "line", "source-layer": "admin" },
  { id: "road-minor-low", type: "line", "source-layer": "road" },
  { id: "road-street-low", type: "line", "source-layer": "road" },
  { id: "road-label", type: "symbol", "source-layer": "road" },
] as const;

describe("selectRoadLineInsertionPoint", () => {
  it("selects the first road line in the recorded dark-v11 layer order", () => {
    expect(selectRoadLineInsertionPoint(DARK_V11_LAYERS)).toBe("road-path");
  });

  it("selects the first road line in the recorded light-v11 layer order", () => {
    expect(selectRoadLineInsertionPoint(LIGHT_V11_LAYERS)).toBe("road-minor-low");
  });

  it("falls back deterministically when a style removes recognizable road ids", () => {
    expect(selectRoadLineInsertionPoint([
      { id: "base", type: "fill" },
      { id: "boundaries", type: "line" },
      { id: "labels", type: "symbol" },
    ])).toBe("boundaries");
  });
});

describe("reviseMapStyleOrder", () => {
  it("recomputes the insertion id and advances the style revision after a style swap", () => {
    const dark = reviseMapStyleOrder({ roadInsertionId: null, revision: 0 }, DARK_V11_LAYERS);
    const light = reviseMapStyleOrder(dark, LIGHT_V11_LAYERS);

    expect(dark).toEqual({ roadInsertionId: "road-path", revision: 1 });
    expect(light).toEqual({ roadInsertionId: "road-minor-low", revision: 2 });
  });
});
