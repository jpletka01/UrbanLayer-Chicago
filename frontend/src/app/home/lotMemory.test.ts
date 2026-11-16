import { beforeEach, describe, expect, it } from "vitest";
import { clearRecent, lotHref, lotKey, outlinePath, outlineRing, readRecent, readSaved, rememberRecent, toggleSaved, RECENT_KEY } from "./lotMemory";

const lot = (n: number) => ({ key: lotKey(`1400000000${String(n).padStart(4, "0")}`, `${n} N Milwaukee Ave`), address: `${n} N Milwaukee Ave`, pin: `1400000000${String(n).padStart(4, "0")}`, zone: "B3-2", area: "West Town", outline: null });

beforeEach(() => localStorage.clear());

describe("recent lots", () => {
  it("keeps the newest first, once each, six at most", () => {
    for (let i = 1; i <= 8; i++) rememberRecent(lot(i), i);
    rememberRecent(lot(5), 99);
    expect(readRecent().map((l) => l.address)).toEqual(["5 N Milwaukee Ave", "8 N Milwaukee Ave", "7 N Milwaukee Ave", "6 N Milwaukee Ave", "4 N Milwaukee Ave", "3 N Milwaukee Ave"]);
  });

  it("clears all at once", () => {
    rememberRecent(lot(1));
    clearRecent();
    expect(readRecent()).toEqual([]);
  });

  it("survives unreadable storage", () => {
    localStorage.setItem(RECENT_KEY, "{not json");
    expect(readRecent()).toEqual([]);
  });
});

describe("saved lots", () => {
  it("toggles: save, then unsave", () => {
    expect(toggleSaved(lot(1))).toBe(true);
    expect(readSaved().map((l) => l.key)).toEqual([lot(1).key]);
    expect(toggleSaved(lot(1))).toBe(false);
    expect(readSaved()).toEqual([]);
  });
});

describe("keys and links", () => {
  it("keys by PIN, else by address", () => {
    expect(lotKey("14313250010000", "1601 N Milwaukee Ave")).toBe("pin:14313250010000");
    expect(lotKey(null, " 1601 N Milwaukee Ave ")).toBe("addr:1601 n milwaukee ave");
  });
  it("links to the Profile by PIN when it has one", () => {
    expect(lotHref({ pin: "14313250010000", address: "1601 N Milwaukee Ave" })).toBe("/scorecard?pin=14313250010000&address=1601+N+Milwaukee+Ave");
    expect(lotHref({ pin: null, address: "1601 N Milwaukee Ave" })).toBe("/scorecard?address=1601+N+Milwaukee+Ave");
  });
});

describe("the outline drawing", () => {
  const square: GeoJSON.Polygon = { type: "Polygon", coordinates: [[[-87.68, 41.91], [-87.679, 41.91], [-87.679, 41.911], [-87.68, 41.911], [-87.68, 41.91]]] };
  it("keeps the outer ring, simplified", () => {
    expect(outlineRing(square)).toHaveLength(5);
    expect(outlineRing({ type: "Point", coordinates: [0, 0] })).toBeNull();
  });
  it("fits the ring into the box with north up", () => {
    const d = outlinePath(outlineRing(square)!, 100, 60);
    expect(d.startsWith("M")).toBe(true);
    expect(d.endsWith("Z")).toBe(true);
    const ys = [...d.matchAll(/[ML][\d.]+ ([\d.]+)/g)].map((m) => Number(m[1]));
    expect(Math.min(...ys)).toBeGreaterThanOrEqual(6 - 0.1);
    expect(Math.max(...ys)).toBeLessThanOrEqual(54 + 0.1);
  });
});
