// The M6 spike's 3D buildings (Item 106): measured heights in feet drawn in metres, neutral colors, dev-only switch.
import { describe, expect, it } from "vitest";
import { buildingsLayer, buildingsSource, wants3d } from "./buildings3d";

describe("buildings3d", () => {
  it("reads our own building tiles from an absolute URL", () => {
    const s = buildingsSource("https://example.test", { minZoom: 14, maxZoom: 16 });
    expect(s.tiles).toEqual(["https://example.test/api/map/tiles/buildings/{z}/{x}/{y}.mvt"]);
    expect(s.minzoom).toBe(14);
  });

  it("extrudes the height in feet converted to metres, from the ground", () => {
    const l = buildingsLayer("light", 14);
    expect(l.type).toBe("fill-extrusion");
    expect(JSON.stringify(l.paint?.["fill-extrusion-height"])).toContain("0.3048");
    expect(l.paint?.["fill-extrusion-base"]).toBe(0);
  });

  it("is switched on only by ?map3d=1 in development", () => {
    expect(wants3d("?map3d=1", true)).toBe(true);
    expect(wants3d("?map3d=1", false)).toBe(false);
    expect(wants3d("", true)).toBe(false);
  });
});
