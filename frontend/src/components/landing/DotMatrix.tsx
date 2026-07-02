// Canvas renderer for the LED dot-matrix halftone (see dotmatrix.ts).
//
// Loads an image, downsamples it to one pixel per grid cell (drawImage
// area-averages, so source detail melts into local luminance), and draws a
// uniform lattice of dots whose size/alpha encode brightness. Dot color is
// the element's resolved `currentColor`, so it follows the theme wrapper.
// One optional orange accent dot marks the brightest window in a zone —
// the found parcel.

import { useEffect, useRef } from "react";
import type { CSSProperties } from "react";
import { DOT_DEFAULTS, computeDots, coverCrop, pickAccentDot } from "./dotGrid";
import type { DotGridParams } from "./dotGrid";

interface DotMatrixProps {
  src: string;
  /** Grid resolution across the container width. */
  cols?: number;
  /** Overall intensity multiplier applied to dot alpha (backdrop duty = keep < 1). */
  intensity?: number;
  /**
   * Translate the image down by N grid cells: the image's bottom N rows drop
   * off the canvas and the vacated top rows stay transparent — in silhouette
   * mode they render as synthesized sky lattice. Use to seat a skyline's
   * bright base on the container's bottom edge.
   */
  shiftDown?: number;
  accent?: boolean;
  className?: string;
  style?: CSSProperties;
  params?: Partial<DotGridParams>;
}

const ACCENT_ZONE = { x0: 0.05, x1: 0.3, y0: 0.55, y1: 0.85 };
const ACCENT_COLOR = "rgb(249 164 116";

export function DotMatrix({
  src,
  cols = 150,
  intensity = 1,
  shiftDown = 0,
  accent = true,
  className = "absolute inset-0 h-full w-full",
  style,
  params,
}: DotMatrixProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let cancelled = false;
    const img = new Image();
    img.decoding = "async";
    img.src = src;

    const draw = () => {
      if (cancelled || !img.naturalWidth) return;
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(rect.width * dpr);
      canvas.height = Math.round(rect.height * dpr);

      const cell = rect.width / cols;
      const rows = Math.max(1, Math.round(rect.height / cell));

      // downsample: one source pixel per grid cell, cover-cropped
      const off = document.createElement("canvas");
      off.width = cols;
      off.height = rows;
      const octx = off.getContext("2d", { willReadFrequently: true });
      const ctx = canvas.getContext("2d");
      if (!octx || !ctx) return;
      const { sx, sy, sw, sh } = coverCrop(img.naturalWidth, img.naturalHeight, rect.width / rect.height);
      const shift = Math.max(0, Math.min(Math.round(shiftDown), rows - 1));
      // translate down: drop the source's bottom `shift` cells, leave the top
      // `shift` destination rows transparent (scale unchanged)
      octx.drawImage(img, sx, sy, sw, sh * ((rows - shift) / rows), 0, shift, cols, rows - shift);
      const px = octx.getImageData(0, 0, cols, rows);

      const grid = computeDots(px, { ...DOT_DEFAULTS, ...params, cols });
      const accentCell = accent ? pickAccentDot(px, ACCENT_ZONE) : null;

      const dotColor = getComputedStyle(canvas).color;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.scale(dpr, dpr);
      ctx.fillStyle = dotColor;
      for (const d of grid.dots) {
        if (accentCell && Math.round(d.cx - 0.5) === accentCell.x && Math.round(d.cy - 0.5) === accentCell.y) {
          continue; // drawn in orange below
        }
        ctx.globalAlpha = Math.min(1, d.alpha * intensity);
        ctx.beginPath();
        ctx.arc(d.cx * cell, d.cy * cell, d.r * cell, 0, Math.PI * 2);
        ctx.fill();
      }
      if (accentCell) {
        const ax = (accentCell.x + 0.5) * cell;
        const ay = (accentCell.y + 0.5) * cell;
        ctx.globalAlpha = 0.95;
        ctx.fillStyle = `${ACCENT_COLOR} / 0.95)`;
        ctx.beginPath();
        ctx.arc(ax, ay, DOT_DEFAULTS.maxRadius * cell, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = `${ACCENT_COLOR} / 0.55)`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(ax, ay, cell * 1.6, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
    };

    img.onload = draw;
    if (img.complete) draw();
    const ro = new ResizeObserver(draw);
    ro.observe(canvas);
    return () => {
      cancelled = true;
      ro.disconnect();
    };
  }, [src, cols, intensity, shiftDown, accent, params]);

  return <canvas ref={canvasRef} className={className} style={style} aria-hidden="true" />;
}
