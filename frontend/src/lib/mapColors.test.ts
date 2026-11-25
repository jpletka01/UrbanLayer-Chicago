import { describe, expect, it } from "vitest";
import {
  boundaryFillColor,
  boundaryLineColor,
  incentiveZoneColor,
  parseZoneClass,
  zoneColor,
  zoneLineColor,
} from "./mapColors";

const rgbDistance = (a: readonly number[], b: readonly number[]) => Math.sqrt(
  ((a[0] - b[0]) ** 2) + ((a[1] - b[1]) ** 2) + ((a[2] - b[2]) ** 2),
);

const composite = (color: readonly number[], background: readonly number[]) => {
  const alpha = color[3] / 255;
  return [0, 1, 2].map((index) => Math.round(
    color[index] * alpha + background[index] * (1 - alpha),
  ));
};

describe("parseZoneClass", () => {
  it("parses integer intensity without losing the business subtype", () => {
    expect(parseZoneClass(" b3 - 2 ")).toEqual({
      exactClass: "B3-2",
      family: "B",
      series: "B3",
      intensity: 2,
      plannedDevelopment: false,
      knownFamily: true,
    });
  });

  it("parses decimal intensity", () => {
    expect(parseZoneClass("RM-4.5")).toMatchObject({
      exactClass: "RM-4.5",
      family: "RM",
      series: "RM",
      intensity: 4.5,
    });
  });

  it("does not interpret planned-development numbers as intensity", () => {
    expect(parseZoneClass("PD 799")).toMatchObject({
      family: "PD",
      series: "PD",
      intensity: null,
      plannedDevelopment: true,
      knownFamily: true,
    });
    expect(parseZoneClass("PMD 3").intensity).toBeNull();
  });

  it("handles suffix-free and unknown classes deterministically", () => {
    expect(parseZoneClass("T")).toMatchObject({ family: "T", intensity: null, knownFamily: true });
    expect(parseZoneClass("ZZ9-4.5")).toMatchObject({
      family: "ZZ",
      series: "ZZ9",
      intensity: 4.5,
      knownFamily: false,
    });
    expect(zoneColor("ZZ9-4.5", "dark")).toEqual(zoneColor(" zz9 - 4.5 ", "dark"));
  });
});

describe("exact zoning intensity colors", () => {
  it.each(["dark", "light"] as const)("gives visibly distinct adjacent steps in %s theme", (theme) => {
    const colors = ["B3-1", "B3-2", "B3-3", "B3-4.5"].map((zone) => zoneColor(zone, theme));
    for (let index = 1; index < colors.length; index += 1) {
      expect(rgbDistance(colors[index - 1], colors[index])).toBeGreaterThan(12);
    }
    expect(new Set(colors.map((color) => color.join(","))).size).toBe(colors.length);
  });

  it("keeps fills and outlines legible against both basemap themes", () => {
    const darkBackground = [24, 24, 24];
    const lightBackground = [244, 241, 235];
    for (const district of ["RS-3", "B3-2", "C1-3", "M2-3", "DX-7", "PD 799", "ZZ9-4.5"]) {
      expect(rgbDistance(composite(zoneColor(district, "dark"), darkBackground), darkBackground)).toBeGreaterThan(22);
      expect(rgbDistance(composite(zoneColor(district, "light"), lightBackground), lightBackground)).toBeGreaterThan(22);
      expect(rgbDistance(zoneLineColor(district, "dark"), darkBackground)).toBeGreaterThan(65);
      expect(rgbDistance(zoneLineColor(district, "light"), lightBackground)).toBeGreaterThan(65);
    }
  });
});

describe("semantic boundary palette", () => {
  it("uses fixed family colors rather than district-name hashing", () => {
    expect(incentiveZoneColor("Kinzie Industrial", "tif")).toEqual(
      incentiveZoneColor("Milwaukee Avenue", "tif"),
    );
    expect(incentiveZoneColor("Chicago Enterprise Zone 2", "enterprise_zone")).not.toEqual(
      incentiveZoneColor("Kinzie Industrial", "tif"),
    );
  });

  it("keeps fills low-opacity, outlines distinct, and orange reserved", () => {
    const families = ["overlay", "tif", "enterprise_zone"] as const;
    const accent = [249, 164, 116];
    const fills = families.map((family) => boundaryFillColor(family, "dark"));
    const lines = families.map((family) => boundaryLineColor(family, "dark"));

    expect(fills.every((color) => color[3] <= 7)).toBe(true);
    expect(new Set(lines.map((color) => color.slice(0, 3).join(","))).size).toBe(3);
    expect(lines.every((color) => rgbDistance(color, accent) > 45)).toBe(true);
  });
});
