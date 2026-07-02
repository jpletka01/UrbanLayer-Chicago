import { describe, expect, it } from "vitest";
import { DOT_DEFAULTS, computeDots, coverCrop, luminanceAt, pickAccentDot } from "./dotGrid";
import type { PixelSource } from "./dotGrid";

/** Build a PixelSource from a row-major array of 0..1 luminance values. */
function gray(width: number, height: number, lums: number[]): PixelSource {
  const data = new Uint8ClampedArray(width * height * 4);
  lums.forEach((l, i) => {
    const v = Math.round(l * 255);
    data[i * 4] = v;
    data[i * 4 + 1] = v;
    data[i * 4 + 2] = v;
    data[i * 4 + 3] = 255;
  });
  return { width, height, data };
}

describe("luminanceAt", () => {
  it("returns 0 for black and 1 for white", () => {
    const px = gray(2, 1, [0, 1]);
    expect(luminanceAt(px, 0, 0)).toBeCloseTo(0);
    expect(luminanceAt(px, 1, 0)).toBeCloseTo(1);
  });
});

describe("computeDots", () => {
  it("skips cells below the cut (true black stays empty)", () => {
    const px = gray(3, 1, [0, 0.01, 0.8]);
    const grid = computeDots(px, { cols: 3 });
    expect(grid.dots.length).toBe(1);
    expect(grid.dots[0].cx).toBe(2.5);
  });

  it("sizes dots monotonically with luminance", () => {
    const px = gray(3, 1, [0.2, 0.5, 1]);
    const [a, b, c] = computeDots(px, { cols: 3 }).dots;
    expect(a.r).toBeLessThan(b.r);
    expect(b.r).toBeLessThan(c.r);
    expect(c.r).toBeCloseTo(DOT_DEFAULTS.maxRadius);
    expect(a.alpha).toBeLessThan(c.alpha);
  });

  it("keeps a visible floor for faint-but-present cells (the sky lattice)", () => {
    const px = gray(1, 1, [0.06]);
    const [d] = computeDots(px, { cols: 1 }).dots;
    expect(d.r).toBe(DOT_DEFAULTS.floorRadius);
  });

  it("quantizes sub-skyLevel cells to one uniform lattice dot", () => {
    const px = gray(3, 1, [0.05, 0.15, 0.6]);
    const grid = computeDots(px, { cols: 3, skyLevel: 0.2, skyAlpha: 0.22, floorRadius: 0.14 });
    const [a, b, c] = grid.dots;
    expect(a.r).toBe(0.14);
    expect(b.r).toBe(0.14);
    expect(a.alpha).toBe(0.22);
    expect(b.alpha).toBe(0.22);
    expect(c.r).toBeGreaterThan(0.14); // above the threshold, back on the ramp
  });

  it("caps alpha at maxAlpha", () => {
    const px = gray(1, 1, [1]);
    const [d] = computeDots(px, { cols: 1, maxAlpha: 0.6 }).dots;
    expect(d.alpha).toBe(0.6);
  });

  it("applies gamma: higher gamma shrinks midtones", () => {
    const px = gray(1, 1, [0.5]);
    const soft = computeDots(px, { cols: 1, gamma: 1 }).dots[0];
    const hard = computeDots(px, { cols: 1, gamma: 2.4 }).dots[0];
    expect(hard.r).toBeLessThan(soft.r);
  });

  it("throws when the buffer was not downsampled to cols", () => {
    const px = gray(4, 1, [0, 0, 0, 0]);
    expect(() => computeDots(px, { cols: 3 })).toThrow();
  });
});

describe("coverCrop", () => {
  it("crops width when the image is wider than the target", () => {
    const c = coverCrop(2000, 1000, 1); // square target
    expect(c.sh).toBe(1000);
    expect(c.sw).toBe(1000);
    expect(c.sx).toBe(500);
  });

  it("crops height with a bottom bias when the image is taller", () => {
    const c = coverCrop(1000, 2000, 2); // wide target
    expect(c.sw).toBe(1000);
    expect(c.sh).toBe(500);
    expect(c.sy).toBeGreaterThan((2000 - 500) / 2); // biased below center
    expect(c.sy).toBeLessThanOrEqual(2000 - 500);
  });
});

describe("pickAccentDot", () => {
  it("finds the brightest cell inside the zone", () => {
    // 4x4: brightest overall at (3,0) but zone is the lower-left quadrant
    const lums = [
      0, 0, 0, 1,
      0, 0, 0, 0,
      0.3, 0.6, 0, 0,
      0.2, 0.1, 0, 0,
    ];
    const px = gray(4, 4, lums);
    const hit = pickAccentDot(px, { x0: 0, x1: 0.5, y0: 0.5, y1: 1 });
    expect(hit).toEqual({ x: 1, y: 2 });
  });

  it("returns null when the zone has no lit window", () => {
    const px = gray(2, 2, [0.05, 0.05, 0.05, 0.05]);
    expect(pickAccentDot(px, { x0: 0, x1: 1, y0: 0, y1: 1 })).toBeNull();
  });
});
