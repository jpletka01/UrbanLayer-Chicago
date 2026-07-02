import { describe, expect, it } from "vitest";
import { generateFacade } from "./facade";

const SEEDS = [1, 2, 3, 5, 7, 11, 13, 42];

describe("generateFacade", () => {
  it("is deterministic for a given seed", () => {
    const a = generateFacade({ seed: 11 });
    const b = generateFacade({ seed: 11 });
    expect(JSON.stringify(a)).toEqual(JSON.stringify(b));
  });

  it("produces different facades for different seeds", () => {
    const a = generateFacade({ seed: 1 });
    const b = generateFacade({ seed: 2 });
    expect(JSON.stringify(a.paths)).not.toEqual(JSON.stringify(b.paths));
  });

  it.each(SEEDS)("seed %i: lit ratio is sparse but present (1.5–10%)", (seed) => {
    const { stats } = generateFacade({ seed });
    const ratio = stats.lit / stats.cells;
    expect(ratio).toBeGreaterThan(0.015);
    expect(ratio).toBeLessThan(0.1);
  });

  it.each(SEEDS)("seed %i: all stroke classes are non-empty (closed vocabulary present)", (seed) => {
    const { paths, litPath } = generateFacade({ seed });
    expect(paths.partyWalls.length).toBeGreaterThan(0);
    expect(paths.columns.length).toBeGreaterThan(0);
    expect(paths.floors.length).toBeGreaterThan(0);
    // guaranteed dialects: at least one chicagoSchool (mullions) + one braced (X-braces)
    expect(paths.mullions.length).toBeGreaterThan(0);
    expect(paths.braces.length).toBeGreaterThan(0);
    expect(litPath.length).toBeGreaterThan(0);
  });

  it.each(SEEDS)("seed %i: orange window sits in the left periphery zone", (seed) => {
    const { orange } = generateFacade({ seed });
    // target cell contains (150, 640); cell size is bounded by the largest module
    expect(orange.rect.x).toBeGreaterThan(80);
    expect(orange.rect.x).toBeLessThan(170);
    expect(orange.rect.y).toBeGreaterThan(585);
    expect(orange.rect.y).toBeLessThan(655);
    // never lit twice: the orange cell must not also appear as a lit rect
    const model = generateFacade({ seed });
    expect(model.litPath).not.toContain(model.orangePath);
  });

  it("respects custom dimensions", () => {
    const m = generateFacade({ seed: 3, width: 800, height: 400 });
    expect(m.width).toBe(800);
    expect(m.height).toBe(400);
  });

  it.each(SEEDS)("seed %i: cells are wider than tall (never square)", (seed) => {
    const model = generateFacade({ seed });
    // lit rects are cell rects inset by 2.5 on each side; w/h + 5 recovers the module
    const litRects = model.litPath.split("M").filter(Boolean);
    expect(litRects.length).toBe(model.stats.lit);
    const { rect } = model.orange;
    expect(rect.w + 5).toBeGreaterThan((rect.h + 5) * 1.3);
  });
});
