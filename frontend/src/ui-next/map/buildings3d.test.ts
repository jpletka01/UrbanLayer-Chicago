// The 3D mode (M6, Items 105-106): measured heights in feet drawn in metres, tinted by zoning family, unmeasured
// pieces apart, the 2D/3D rules for phones, and the tilt steps.
import { describe, expect, it } from "vitest";
import { buildingsLayer, buildingsSource, can3d, mix, nextPitch, PITCH_MAX, tintedColors, unmeasuredLayer } from "./buildings3d";

describe("buildings3d", () => {
  it("reads our own building tiles from an absolute URL", () => {
    const s = buildingsSource("https://example.test", { minZoom: 14, maxZoom: 16 });
    expect(s.tiles).toEqual(["https://example.test/api/map/tiles/buildings/{z}/{x}/{y}.mvt"]);
    expect(s.minzoom).toBe(14);
    expect(buildingsSource("https://example.test", { minZoom: 14, maxZoom: 16, version: "1762850000" }).tiles?.[0]).toMatch(/\.mvt\?v=1762850000$/);
  });

  it("extrudes the height in feet converted to metres, from the ground", () => {
    const l = buildingsLayer("light", 14);
    expect(l.type).toBe("fill-extrusion");
    expect(JSON.stringify(l.paint?.["fill-extrusion-height"])).toContain("0.3048");
    expect(l.paint?.["fill-extrusion-base"]).toBe(0);
  });

  it("draws measured and not-measured pieces in separate layers", () => {
    expect(buildingsLayer("dark", 14).filter).toEqual(["!=", ["get", "m"], "u"]);
    expect(unmeasuredLayer("dark", 14).filter).toEqual(["==", ["get", "m"], "u"]);
    expect(unmeasuredLayer("dark", 14).paint?.["fill-extrusion-opacity"]).toBeLessThan(buildingsLayer("dark", 14).paint?.["fill-extrusion-opacity"] as number);
  });

  it("tints each zoning family slightly, and leaves an unzoned building neutral", () => {
    expect(mix("#FF0000", "#FFFFFF", 0)).toBe("#ffffff");
    expect(mix("#FF0000", "#000000", 1)).toBe("#ff0000");
    const t = tintedColors("light");
    expect(Object.keys(t)).toContain("business");
    expect(t.business.low).not.toBe(t.residential.low);
    const color = JSON.stringify(buildingsLayer("light", 14).paint?.["fill-extrusion-color"]);
    expect(color).toContain('"business"');
    expect(color).toContain("#E3E7EC");
  });

  it("shows 3D on a phone only in the expanded map, and never without building tiles", () => {
    expect(can3d(true, false, false)).toBe(true);
    expect(can3d(true, true, false)).toBe(false);
    expect(can3d(true, true, true)).toBe(true);
    expect(can3d(false, false, true)).toBe(false);
  });

  it("tilts in steps between flat and the maximum", () => {
    expect(nextPitch(55, 1)).toBe(60);
    expect(nextPitch(54.99, 1)).toBe(60);
    expect(nextPitch(55, -1)).toBe(50);
    expect(nextPitch(50, -1)).toBe(40);
    expect(nextPitch(PITCH_MAX, 1)).toBe(PITCH_MAX);
    expect(nextPitch(5, -1)).toBe(0);
    expect(nextPitch(0, -1)).toBe(0);
  });
});
