// Textures for the zoning families that depend least on hue (owner's pick after the color-blind check, Item 97):
// planned development (a pale gray) gets small separate "+" marks and transportation (a mid gray) a dot grid, so they no
// longer rely on color to be told from residential, business, parks or downtown. No continuous lines: those read like
// lot lines (owner's review). Drawn once on a canvas at 2x and
// handed to MapLibre as repeating fill patterns, in ink for light and white for dark.

export type PatternTheme = "light" | "dark";
export type PatternKind = "plus" | "dots";

const SIZE = 10; // CSS px per repeat (sparser, owner: the lot lines must stay readable)
const RATIO = 2;

/** The dots take a color of their own (owner's try, Item 98): Coastal's Sapphire, so a planned development's gray
    reads as a family with an accent rather than a dull gray; deeper in light, lighter in dark. */
export const DOT_INK: Record<PatternTheme, string> = { light: "rgba(53,140,133,0.85)", dark: "rgba(140,214,206,0.75)" };

export const PATTERN_IMAGE = (kind: PatternKind, theme: PatternTheme) => `pattern-${kind}-${theme}`;

/** The pattern colors: the lot's ink at low opacity (toned down, owner), so the texture never competes with the lot
    lines or the lot. */
export const PATTERN_INK: Record<PatternTheme, string> = { light: "rgba(28,28,28,0.24)", dark: "rgba(255,255,255,0.22)" };

export function drawPattern(kind: PatternKind, theme: PatternTheme): { width: number; height: number; data: Uint8ClampedArray } | null {
  if (typeof document === "undefined") return null;
  const n = SIZE * RATIO;
  const canvas = document.createElement("canvas");
  canvas.width = n;
  canvas.height = n;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.scale(RATIO, RATIO);
  ctx.strokeStyle = PATTERN_INK[theme];
  ctx.fillStyle = PATTERN_INK[theme];
  if (kind === "plus") {
    // A small "+" (3 px arms) in the middle of each repeat: marks, never a line that could pass for a boundary.
    const c = SIZE / 2;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(c - 1.5, c); ctx.lineTo(c + 1.5, c);
    ctx.moveTo(c, c - 1.5); ctx.lineTo(c, c + 1.5);
    ctx.stroke();
  } else {
    ctx.fillStyle = DOT_INK[theme];
    ctx.beginPath();
    ctx.arc(SIZE / 2, SIZE / 2, 1.2, 0, Math.PI * 2);
    ctx.fill();
  }
  const img = ctx.getImageData(0, 0, n, n);
  return { width: n, height: n, data: img.data };
}

/** Add the four pattern images once (idempotent). */
export function addPatternImages(map: { hasImage(id: string): boolean; addImage(id: string, img: { width: number; height: number; data: Uint8ClampedArray }, opts: { pixelRatio: number }): void }): void {
  for (const theme of ["light", "dark"] as const) {
    for (const kind of ["plus", "dots"] as const) {
      const id = PATTERN_IMAGE(kind, theme);
      if (map.hasImage(id)) continue;
      const img = drawPattern(kind, theme);
      if (img) map.addImage(id, img, { pixelRatio: RATIO });
    }
  }
}

/** CSS for the key's swatches: the same textures over the family color, inked more strongly. */
export function patternCss(kind: PatternKind, theme: PatternTheme): string {
  // Stronger than on the map: a 16 px swatch needs it to read at all.
  const ink = theme === "dark" ? "rgba(255,255,255,0.85)" : "rgba(28,28,28,0.8)";
  if (kind === "dots") return `radial-gradient(${DOT_INK[theme]} 0.9px, transparent 1.1px) 0 0 / 4px 4px`;
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='6' height='6'><path d='M1.5 3h3M3 1.5v3' stroke='${ink}' stroke-width='1'/></svg>`;
  return `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}") 0 0 / 6px 6px`;
}
