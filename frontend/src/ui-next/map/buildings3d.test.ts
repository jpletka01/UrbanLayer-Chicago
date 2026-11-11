// The 3D mode (M6, Items 105-106): measured heights in feet drawn in metres, tinted by zoning family, unmeasured
// pieces apart, the 2D/3D rules for phones, and the tilt steps.
import { describe, expect, it } from "vitest";
import { buildingsLayer, buildingsSource, can3d, massData, measuredFilter, mix, nextPitch, PITCH_MAX, pointInLot, ringMiddle, tintedColors, unmeasuredLayer, zoningFamily } from "./buildings3d";

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
    expect(measuredFilter([7, 9])).toEqual(["all", ["!=", ["get", "m"], "u"], ["!", ["in", ["id"], ["literal", [7, 9]]]]]);
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

  it("names a district's color family like the zoning tiles", () => {
    expect(zoningFamily("B3-2")).toBe("business");
    expect(zoningFamily("RS-3")).toBe("residential");
    expect(zoningFamily("DX-12")).toBe("downtown");
    expect(zoningFamily("PMD 4")).toBe("manufacturing");
    expect(zoningFamily("PD 306")).toBe("planned");
  });

  it("raises the lot to the mass height in metres in its district's darkest color, or nothing", () => {
    const lot: GeoJSON.Polygon = { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] };
    const d = massData(lot, 26.4, "B3-2");
    expect(d.features[0].properties).toEqual({ m: 26.4 * 0.3048, c: "#B8464C" });
    expect(massData(null, 26.4).features).toEqual([]);
    expect(massData(lot, 0).features).toEqual([]);
  });

  it("finds the buildings standing on the lot by their middle, holes respected", () => {
    const lot: GeoJSON.Polygon = { type: "Polygon", coordinates: [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]], [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]] };
    expect(pointInLot(2, 2, lot)).toBe(true);
    expect(pointInLot(5, 5, lot)).toBe(false);
    expect(pointInLot(12, 2, lot)).toBe(false);
    expect(ringMiddle({ type: "Polygon", coordinates: [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]] })).toEqual([1, 1]);
  });
});
