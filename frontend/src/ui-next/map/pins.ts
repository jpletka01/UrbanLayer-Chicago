// Map pins for points (owner's review, Item 95): recent sales and transit stations were small dots that disappeared
// under the zoning fills. Like Google Maps' pins: a teardrop with a white edge and a soft shadow, the point at its
// tip, an icon inside, drawn above every other layer. Drawn once on a canvas at 2x and handed to MapLibre as an image.

/** Icon strokes on Lucide's 24-unit grid (ISC licence): the same icons the rest of the new UI uses. */
const ICONS: Record<string, string[]> = {
  // Lucide "dollar-sign"
  sale: ["M12 2v20", "M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"],
  // Lucide "house": the property's own pin (Item 96)
  lot: ["M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8",
    "M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"],
  // Lucide "building-2": a new building nearby (Item 102)
  build: ["M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z", "M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2",
    "M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2", "M10 6h4", "M10 10h4", "M10 14h4", "M10 18h4"],
  // Lucide "wrench": a renovation nearby (owner's review: the two kinds need different icons, not two pinks)
  reno: ["M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"],
  // Lucide "train-front"
  transit: [
    "M8 3.1V7a4 4 0 0 0 8 0V3.1", "m9 15-1-1", "m15 15 1-1",
    "M9 19c-2.8 0-5-2.2-5-5v-4a8 8 0 0 1 16 0v4c0 2.8-2.2 5-5 5Z", "m8 19-2 3", "m16 19 2 3",
  ],
};

/** Pin fills: Coastal's Spruce for sales and ink for transit (Item 74: maps use Sapphire, Spruce and black); the
    Neighborhood tab's permits in two Coastal hues that read apart, with different icons (owner's review, Item 102):
    Ballet Slipper with a building for a new building, Pistachio with a wrench for a renovation; dark icons. */
export const PIN_COLORS = { sale: "#355E58", transit: "#1C1C1C", build: "#FE9179", reno: "#B89D47" } as const;
export type PinKind = keyof typeof PIN_COLORS | "lot-light" | "lot-dark";
export const PIN_IMAGE: Record<PinKind, string> = {
  sale: "pin-sale", transit: "pin-transit", build: "pin-build", reno: "pin-reno", "lot-light": "pin-lot-light", "lot-dark": "pin-lot-dark",
};

/** Fill, edge and icon per pin. The property's pin is "this lot" ink (Item 74): black with a white edge in light,
    white with a black edge in dark, a house inside. */
const STYLE: Record<PinKind, { fill: string; edge: string; icon: string; glyph: keyof typeof ICONS }> = {
  sale: { fill: PIN_COLORS.sale, edge: "#FFFFFF", icon: "#FFFFFF", glyph: "sale" },
  transit: { fill: PIN_COLORS.transit, edge: "#FFFFFF", icon: "#FFFFFF", glyph: "transit" },
  build: { fill: PIN_COLORS.build, edge: "#FFFFFF", icon: "#1C1C1C", glyph: "build" },
  reno: { fill: PIN_COLORS.reno, edge: "#FFFFFF", icon: "#1C1C1C", glyph: "reno" },
  "lot-light": { fill: "#1C1C1C", edge: "#FFFFFF", icon: "#FFFFFF", glyph: "lot" },
  "lot-dark": { fill: "#FFFFFF", edge: "#1C1C1C", icon: "#1C1C1C", glyph: "lot" },
};

/** CSS pixel size of a pin (the image is drawn at 2x). */
export const PIN_W = 32;
export const PIN_H = 42;
const RATIO = 2;

/** The pin as ImageData, or null where there is no 2D canvas (tests, very old browsers). */
export function drawPin(kind: PinKind): { width: number; height: number; data: Uint8ClampedArray } | null {
  if (typeof document === "undefined") return null;
  const w = PIN_W * RATIO, h = PIN_H * RATIO;
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.scale(RATIO, RATIO);
  const cx = PIN_W / 2, r = 14, cy = r + 2, tipY = PIN_H - 2;
  const head = () => {
    ctx.beginPath();
    // A circle that narrows to the tip: arcs to the tangents, then two straight sides.
    const a = Math.acos(r / (tipY - cy)); // the tangent points seen from the tip
    ctx.arc(cx, cy, r, Math.PI / 2 + a, Math.PI / 2 - a + 2 * Math.PI, false);
    ctx.lineTo(cx, tipY);
    ctx.closePath();
  };
  ctx.save();
  ctx.shadowColor = "rgba(0,0,0,0.35)";
  ctx.shadowBlur = 3;
  ctx.shadowOffsetY = 1;
  head();
  ctx.fillStyle = STYLE[kind].fill;
  ctx.fill();
  ctx.restore();
  head();
  ctx.lineWidth = 2;
  ctx.strokeStyle = STYLE[kind].edge;
  ctx.stroke();
  // The icon, 15 px, centered in the head.
  ctx.save();
  const s = 15 / 24;
  ctx.translate(cx - 7.5, cy - 7.5);
  ctx.scale(s, s);
  ctx.strokeStyle = STYLE[kind].icon;
  ctx.lineWidth = 2.4;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  if (typeof Path2D !== "undefined") for (const d of ICONS[STYLE[kind].glyph]) ctx.stroke(new Path2D(d));
  ctx.restore();
  const img = ctx.getImageData(0, 0, w, h);
  return { width: w, height: h, data: img.data };
}

/** Add every pin image to a map once (idempotent); MapLibre draws them at the 2x pixel ratio. */
export function addPinImages(map: { hasImage(id: string): boolean; addImage(id: string, img: { width: number; height: number; data: Uint8ClampedArray }, opts: { pixelRatio: number }): void }): void {
  for (const kind of Object.keys(PIN_IMAGE) as PinKind[]) {
    const id = PIN_IMAGE[kind];
    if (map.hasImage(id)) continue;
    const img = drawPin(kind);
    if (img) map.addImage(id, img, { pixelRatio: RATIO });
  }
}
