// Textures for the zoning families that depend least on hue (owner's pick after the color-blind check, Item 97):
// planned development (a pale gray) gets a diagonal hatch and transportation (a mid gray) a dot grid, so they no
// longer rely on color to be told from residential, business, parks or downtown. Drawn once on a canvas at 2x and
// handed to MapLibre as repeating fill patterns, in ink for light and white for dark.

export type PatternTheme = "light" | "dark";
export type PatternKind = "hatch" | "dots";

const SIZE = 8; // CSS px per repeat
const RATIO = 2;

export const PATTERN_IMAGE = (kind: PatternKind, theme: PatternTheme) => `pattern-${kind}-${theme}`;

/** The pattern colors: the lot's ink at low opacity, so the texture reads without competing with the lot. */
export const PATTERN_INK: Record<PatternTheme, string> = { light: "rgba(28,28,28,0.42)", dark: "rgba(255,255,255,0.38)" };

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
  if (kind === "hatch") {
    // A diagonal from bottom-left to top-right, plus the two corner pieces, so the lines join across repeats.
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, SIZE); ctx.lineTo(SIZE, 0);
    ctx.moveTo(-1, 1); ctx.lineTo(1, -1);
    ctx.moveTo(SIZE - 1, SIZE + 1); ctx.lineTo(SIZE + 1, SIZE - 1);
    ctx.stroke();
  } else {
    ctx.beginPath();
    ctx.arc(SIZE / 2, SIZE / 2, 1.1, 0, Math.PI * 2);
    ctx.fill();
  }
  const img = ctx.getImageData(0, 0, n, n);
  return { width: n, height: n, data: img.data };
}

/** Add the four pattern images once (idempotent). */
export function addPatternImages(map: { hasImage(id: string): boolean; addImage(id: string, img: { width: number; height: number; data: Uint8ClampedArray }, opts: { pixelRatio: number }): void }): void {
  for (const theme of ["light", "dark"] as const) {
    for (const kind of ["hatch", "dots"] as const) {
      const id = PATTERN_IMAGE(kind, theme);
      if (map.hasImage(id)) continue;
      const img = drawPattern(kind, theme);
      if (img) map.addImage(id, img, { pixelRatio: RATIO });
    }
  }
}

/** CSS for the key's swatches: the same textures over the family color. */
export function patternCss(kind: PatternKind, theme: PatternTheme): string {
  const ink = PATTERN_INK[theme];
  return kind === "hatch"
    ? `repeating-linear-gradient(135deg, ${ink} 0 1px, transparent 1px 4px)`
    : `radial-gradient(${ink} 0.9px, transparent 1.1px) 0 0 / 4px 4px`;
}
