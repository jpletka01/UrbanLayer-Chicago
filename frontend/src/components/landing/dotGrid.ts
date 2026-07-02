// LED dot-matrix halftone — pure sampling/layout logic for <DotMatrix>.
// (Named dotGrid, not dotmatrix: on a case-insensitive filesystem a
// `dotmatrix.ts` next to `DotMatrix.tsx` hijacks the `./DotMatrix` import.)
//
// Turns an image's luminance field into a uniform grid of dots whose size
// (and alpha) encode brightness — the "unit-grid feed" look: sky reads as a
// faint regular dot lattice, buildings as bright merged clusters. Pure
// functions, no DOM/canvas — the component owns pixel I/O.

export interface DotGridParams {
  cols: number;
  /** Cell aspect (height/width). 1 = square lattice. */
  cellAspect?: number;
  /** Gamma applied to luminance before sizing; >1 darkens mids (more contrast). */
  gamma?: number;
  /** Max dot radius as a fraction of the cell (0.5 = dots touch at full white). */
  maxRadius?: number;
  /** Min visible radius fraction for any cell above `cut` — keeps the faint lattice alive. */
  floorRadius?: number;
  /** Luminance below this renders nothing (true black stays empty). */
  cut?: number;
  /** Alpha ceiling — keeps merged-bright clusters below text contrast. */
  maxAlpha?: number;
  /**
   * Luminance below this renders as the uniform background lattice (exactly
   * floorRadius at skyAlpha) instead of the ramp — kills sampling noise in
   * flat regions so the figure pops against a perfectly regular field.
   */
  skyLevel?: number;
  skyAlpha?: number;
  /**
   * Skyline silhouette mode. Night-sky photos have NO luminance separation
   * between sky and dark tower bodies (measured: both ~0.03–0.05), so the
   * figure must be built structurally: per column, find the topmost cell
   * brighter than `threshold` (a roof/crown light) — everything above is sky
   * (uniform lattice), everything below is building, where only cells above
   * `lightCut` render (lit windows); dark body cells stay true black voids.
   * The tower then reads as a negative silhouette cut out of the lattice.
   */
  silhouette?: { threshold?: number; lightCut?: number };
}

export interface Dot {
  /** Center, in cell units (multiply by cell size for pixels). */
  cx: number;
  cy: number;
  /** Radius as a fraction of cell size. */
  r: number;
  /** 0..1 — brighter cells render more opaque. */
  alpha: number;
}

export interface DotGrid {
  cols: number;
  rows: number;
  dots: Dot[];
}

/** Minimal structural subset of ImageData, so tests can pass plain objects. */
export interface PixelSource {
  width: number;
  height: number;
  /** RGBA, 4 bytes per pixel, row-major — same layout as ImageData.data. */
  data: Uint8ClampedArray | number[];
}

export const DOT_DEFAULTS = {
  cellAspect: 1,
  gamma: 1.6,
  maxRadius: 0.46,
  floorRadius: 0.07,
  cut: 0.03,
  maxAlpha: 1,
  skyLevel: 0,
  skyAlpha: 0.25,
} as const;

export function luminanceAt(px: PixelSource, x: number, y: number): number {
  const i = (y * px.width + x) * 4;
  return (0.2126 * px.data[i] + 0.7152 * px.data[i + 1] + 0.0722 * px.data[i + 2]) / 255;
}

/**
 * Build the dot grid from an already-downsampled pixel buffer (one pixel per
 * grid cell — the component downsamples via canvas drawImage, which
 * area-averages, so any halftone/noise in the source melts into local
 * luminance).
 */
export function computeDots(px: PixelSource, params: DotGridParams): DotGrid {
  const { cols } = params;
  const gamma = params.gamma ?? DOT_DEFAULTS.gamma;
  const maxRadius = params.maxRadius ?? DOT_DEFAULTS.maxRadius;
  const floorRadius = params.floorRadius ?? DOT_DEFAULTS.floorRadius;
  const cut = params.cut ?? DOT_DEFAULTS.cut;
  const maxAlpha = params.maxAlpha ?? DOT_DEFAULTS.maxAlpha;
  const skyLevel = params.skyLevel ?? DOT_DEFAULTS.skyLevel;
  const skyAlpha = params.skyAlpha ?? DOT_DEFAULTS.skyAlpha;
  const rows = px.height;
  if (px.width !== cols) throw new Error(`pixel buffer width ${px.width} != cols ${cols}`);

  // silhouette mode: per-column roofline = topmost cell with a bright light
  let roofline: number[] | null = null;
  if (params.silhouette) {
    const threshold = params.silhouette.threshold ?? 0.4;
    roofline = new Array(cols).fill(rows);
    for (let x = 0; x < cols; x++) {
      for (let y = 0; y < rows; y++) {
        if (luminanceAt(px, x, y) > threshold) {
          roofline[x] = y;
          break;
        }
      }
    }
  }
  const lightCut = params.silhouette?.lightCut ?? 0.08;

  const dots: Dot[] = [];
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      const lum = luminanceAt(px, x, y);
      let isBuildingLight = false;
      if (roofline) {
        if (y < roofline[x]) {
          // sky above the roofline: perfectly uniform lattice
          dots.push({ cx: x + 0.5, cy: y + 0.5, r: floorRadius, alpha: skyAlpha });
          continue;
        }
        // building zone: lit windows on the ramp, dark body stays a void
        if (lum < lightCut) continue;
        isBuildingLight = true;
      } else {
        if (lum < cut) continue;
        if (lum < skyLevel) {
          dots.push({ cx: x + 0.5, cy: y + 0.5, r: floorRadius, alpha: skyAlpha });
          continue;
        }
      }
      const shaped = Math.pow(lum, gamma);
      // building lights start well above the sky lattice's alpha, so the
      // figure separates from the field even where dot sizes match
      const base = isBuildingLight ? 0.5 + 0.5 * shaped : 0.3 + 0.7 * shaped;
      dots.push({
        cx: x + 0.5,
        cy: y + 0.5,
        r: Math.max(floorRadius, maxRadius * shaped),
        alpha: Math.min(maxAlpha, base),
      });
    }
  }
  return { cols, rows, dots };
}

/**
 * Cover-fit source crop: the rect of the image (in source pixels) that fills
 * a target aspect ratio, cropping the excess — object-fit: cover semantics.
 */
export function coverCrop(
  imgW: number,
  imgH: number,
  targetAspect: number, // width / height
): { sx: number; sy: number; sw: number; sh: number } {
  const imgAspect = imgW / imgH;
  if (imgAspect > targetAspect) {
    const sw = imgH * targetAspect;
    return { sx: (imgW - sw) / 2, sy: 0, sw, sh: imgH };
  }
  const sh = imgW / targetAspect;
  // anchor the vertical crop to the image bottom: skylines sit on their base,
  // so the excess is always trimmed from the sky
  return { sx: 0, sy: imgH - sh, sw: imgW, sh };
}

/**
 * The one orange "found parcel" dot: the brightest cell inside a zone
 * (fractions of the grid), so it always lands on a lit window.
 */
export function pickAccentDot(
  px: PixelSource,
  zone: { x0: number; x1: number; y0: number; y1: number },
): { x: number; y: number } | null {
  let best: { x: number; y: number } | null = null;
  let bestLum = -1;
  const xa = Math.floor(zone.x0 * px.width);
  const xb = Math.ceil(zone.x1 * px.width);
  const ya = Math.floor(zone.y0 * px.height);
  const yb = Math.ceil(zone.y1 * px.height);
  for (let y = ya; y < Math.min(yb, px.height); y++) {
    for (let x = xa; x < Math.min(xb, px.width); x++) {
      const lum = luminanceAt(px, x, y);
      if (lum > bestLum) {
        bestLum = lum;
        best = { x, y };
      }
    }
  }
  return bestLum > 0.2 ? best : null;
}
