// Abstract hero backdrop. All line-work is drawn in currentColor under a `text-text-primary`
// wrapper, so it renders white-on-black in dark mode and inverts to black-on-white in light
// mode with no per-theme code. Orange appears only as a single "found parcel" marker.
//
// Variants (dev exploration, switch via ?bg=):
//   bloom   — current shipped design: warm orange bloom + faint grid (default)
//   plat    — abstract plat map: street grid, lot subdivisions, diagonal avenue
//   contour — topographic contour rings + survey crosses
//   geo     — fine grid + concentric survey arcs + block squares
//   curtain — procedural curtain-wall facade, the city in elevation (facade.ts)
//   skyline — LED dot-matrix halftone of the night skyline (DotMatrix + dotmatrix.ts)

import type { ReactElement } from "react";
import { CurtainWall } from "./CurtainWall";
import { DotMatrix } from "./DotMatrix";
import skylineUrl from "../../assets/skyline-night.jpg";

type Variant = "bloom" | "plat" | "contour" | "geo" | "curtain" | "skyline";

function activeVariant(): Variant {
  const v = new URLSearchParams(window.location.search).get("bg");
  return v === "bloom" || v === "contour" || v === "geo" || v === "curtain" || v === "skyline"
    ? v
    : "plat";
}

// Inverted mask: the hero's content (headline, input, preview card) lives in the middle of the
// viewport, and its surfaces are translucent — line-work showing through them reads as noise.
// So the backdrop is voided over the content zone and only draws in the periphery.
const MASK = {
  maskImage: "radial-gradient(ellipse 75% 70% at 46% 44%, transparent 42%, black 72%)",
  WebkitMaskImage: "radial-gradient(ellipse 75% 70% at 46% 44%, transparent 42%, black 72%)",
} as const;

/** Soft achromatic depth bloom — white haze in dark mode, faint gray in light. */
function NeutralBloom() {
  return (
    <div
      className="absolute left-[38%] top-[42%] -translate-x-1/2 -translate-y-1/2 rounded-full"
      style={{
        width: 820,
        height: 820,
        background: "radial-gradient(circle, rgb(var(--text-primary) / 0.06), transparent 70%)",
        filter: "blur(130px)",
      }}
    />
  );
}

function BloomVariant() {
  return (
    <>
      <div
        className="absolute left-[38%] top-[42%] -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          width: 820,
          height: 820,
          background: "radial-gradient(circle, rgba(249,164,116,0.16), transparent 70%)",
          filter: "blur(130px)",
        }}
      />
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(rgb(var(--text-primary) / 0.03) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--text-primary) / 0.03) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          ...MASK,
        }}
      />
    </>
  );
}

// ---------------------------------------------------------------------------
// plat — abstract subdivision map
// ---------------------------------------------------------------------------

const STREET_XS = [80, 250, 420, 590, 760, 930, 1100, 1270, 1440];
const STREET_YS = [60, 200, 340, 480, 620, 760, 900];
// Blocks (by street-grid cell) that get lot subdivisions. [colIndex, rowIndex]
const LOTTED_BLOCKS: Array<[number, number]> = [
  [1, 1], [2, 2], [3, 1], [4, 3], [5, 1], [5, 2], [2, 4], [6, 2], [3, 3], [0, 2], [6, 4], [1, 3],
];

function PlatBlock({ col, row }: { col: number; row: number }) {
  const x0 = STREET_XS[col];
  const x1 = STREET_XS[col + 1];
  const y0 = STREET_YS[row];
  const y1 = STREET_YS[row + 1];
  const midY = (y0 + y1) / 2;
  const inset = 12;
  const lots: ReactElement[] = [];
  // Lot lines run from street to alley; top and bottom rows are staggered like a real plat.
  for (let x = x0 + inset + 10; x < x1 - inset; x += 21) {
    lots.push(<line key={`t${x}`} x1={x} y1={y0 + inset} x2={x} y2={midY - 3} strokeOpacity={0.10} />);
  }
  for (let x = x0 + inset + 20; x < x1 - inset; x += 21) {
    lots.push(<line key={`b${x}`} x1={x} y1={midY + 3} x2={x} y2={y1 - inset} strokeOpacity={0.10} />);
  }
  return (
    <g>
      {/* alley */}
      <line x1={x0 + inset} y1={midY} x2={x1 - inset} y2={midY} strokeOpacity={0.09} strokeDasharray="4 5" />
      {lots}
    </g>
  );
}

function PlatVariant() {
  return (
    <>
      <NeutralBloom />
      <svg
        className="absolute inset-0 h-full w-full"
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
        style={MASK}
        stroke="currentColor"
        strokeWidth="1"
        fill="none"
      >
        {/* street grid */}
        {STREET_XS.map((x) => (
          <line key={`v${x}`} x1={x} y1={0} x2={x} y2={900} strokeOpacity={0.13} />
        ))}
        {STREET_YS.map((y) => (
          <line key={`h${y}`} x1={0} y1={y} x2={1440} y2={y} strokeOpacity={0.13} />
        ))}
        {/* subdivided blocks */}
        {LOTTED_BLOCKS.map(([c, r]) => (
          <PlatBlock key={`${c}-${r}`} col={c} row={r} />
        ))}
        {/* diagonal avenue (double line, Milwaukee-style) */}
        <line x1={150} y1={980} x2={1300} y2={-80} strokeOpacity={0.18} />
        <line x1={168} y1={990} x2={1318} y2={-70} strokeOpacity={0.18} />
        {/* survey crosses at a few intersections */}
        {[[420, 340], [930, 200], [760, 620], [1270, 480]].map(([x, y]) => (
          <g key={`${x}${y}`} strokeOpacity={0.25}>
            <line x1={x - 5} y1={y} x2={x + 5} y2={y} />
            <line x1={x} y1={y - 5} x2={x} y2={y + 5} />
          </g>
        ))}
        {/* the found parcel — one lot inside block [2,4], in the periphery below the input column */}
        <g>
          <rect x={452} y={632} width={21} height={57} stroke="rgb(249 164 116 / 0.85)" strokeWidth="1.5" fill="rgb(249 164 116 / 0.10)" />
          <circle cx={462.5} cy={660} r={2.5} fill="rgb(249 164 116 / 0.9)" stroke="none" />
        </g>
      </svg>
    </>
  );
}

// ---------------------------------------------------------------------------
// contour — topographic rings
// ---------------------------------------------------------------------------

const BLOB_CX = 540;
const BLOB_CY = 430;
const CONTOUR_SCALES = [0.35, 0.55, 0.75, 1, 1.3, 1.65, 2.05, 2.5];

function ContourVariant() {
  return (
    <>
      <NeutralBloom />
      <svg
        className="absolute inset-0 h-full w-full"
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
        style={MASK}
        stroke="currentColor"
        strokeWidth="1"
        fill="none"
      >
        <defs>
          <path
            id="hero-contour"
            d="M 380 430 C 380 340 460 280 560 290 C 660 300 730 360 720 450 C 710 540 620 590 520 580 C 420 570 380 520 380 430 Z"
          />
        </defs>
        {CONTOUR_SCALES.map((s, i) => (
          <use
            key={s}
            href="#hero-contour"
            vectorEffect="non-scaling-stroke"
            strokeOpacity={i % 3 === 2 ? 0.24 : 0.13}
            transform={`translate(${BLOB_CX * (1 - s)} ${BLOB_CY * (1 - s)}) scale(${s}) rotate(${(i - 3) * 3} ${BLOB_CX} ${BLOB_CY})`}
          />
        ))}
        {/* survey cross grid */}
        {Array.from({ length: 11 }, (_, i) => 100 + i * 130).flatMap((x) =>
          Array.from({ length: 7 }, (_, j) => 70 + j * 130).map((y) => (
            <g key={`${x}-${y}`} strokeOpacity={0.12}>
              <line x1={x - 4} y1={y} x2={x + 4} y2={y} />
              <line x1={x} y1={y - 4} x2={x} y2={y + 4} />
            </g>
          )),
        )}
        {/* benchmark at the summit */}
        <g>
          <circle cx={BLOB_CX} cy={BLOB_CY} r={7} stroke="rgb(249 164 116 / 0.8)" strokeWidth="1.5" />
          <circle cx={BLOB_CX} cy={BLOB_CY} r={2.5} fill="rgb(249 164 116 / 0.9)" stroke="none" />
        </g>
      </svg>
    </>
  );
}

// ---------------------------------------------------------------------------
// geo — grid + survey arcs
// ---------------------------------------------------------------------------

const GEO_SQUARES: Array<[number, number]> = [
  [448, 256], [704, 192], [1024, 320], [576, 512], [896, 448], [320, 384], [1152, 576], [768, 640], [1216, 128], [192, 576],
];

function GeoVariant() {
  return (
    <>
      <NeutralBloom />
      <svg
        className="absolute inset-0 h-full w-full"
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
        style={MASK}
        stroke="currentColor"
        strokeWidth="1"
        fill="none"
      >
        {/* fine grid */}
        {Array.from({ length: 23 }, (_, i) => (i + 1) * 64).map((x) => (
          <line key={`v${x}`} x1={x} y1={0} x2={x} y2={900} strokeOpacity={0.08} />
        ))}
        {Array.from({ length: 14 }, (_, i) => (i + 1) * 64).map((y) => (
          <line key={`h${y}`} x1={0} y1={y} x2={1440} y2={y} strokeOpacity={0.08} />
        ))}
        {/* concentric survey arcs */}
        {[380, 520, 660].map((r) => (
          <circle key={r} cx={1150} cy={200} r={r} strokeOpacity={0.17} />
        ))}
        {[300, 420].map((r) => (
          <circle key={r} cx={250} cy={750} r={r} strokeOpacity={0.14} />
        ))}
        {/* crosshair at the survey origin */}
        <g strokeOpacity={0.45}>
          <line x1={1150 - 14} y1={200} x2={1150 + 14} y2={200} />
          <line x1={1150} y1={200 - 14} x2={1150} y2={200 + 14} />
        </g>
        {/* block squares on grid intersections */}
        {GEO_SQUARES.map(([x, y]) => (
          <rect key={`${x}${y}`} x={x - 3} y={y - 3} width={6} height={6} fill="currentColor" fillOpacity={0.3} stroke="none" />
        ))}
        {/* the found block */}
        <rect x={893} y={317} width={6} height={6} fill="rgb(249 164 116 / 0.9)" stroke="none" />
        <circle cx={896} cy={320} r={14} stroke="rgb(249 164 116 / 0.5)" />
      </svg>
    </>
  );
}

// ---------------------------------------------------------------------------
// curtain — procedural curtain-wall facade (the city in elevation)
// ---------------------------------------------------------------------------

function CurtainVariant() {
  return (
    <>
      <NeutralBloom />
      <CurtainWall seed={11} style={MASK} />
    </>
  );
}

// ---------------------------------------------------------------------------
// skyline — LED dot-matrix halftone of the night skyline
// ---------------------------------------------------------------------------

// Unlike the line-work variants, the skyline is a *figure* — voiding or
// heavily dimming the content zone amputates it. The mask dims ONLY the left
// text/input column (the preview card is opaque enough to occlude on its
// own); the Hancock corridor at viewport center runs at full strength, so
// the tower reads as a dark silhouette cut out of the bright sky lattice.
const SKYLINE_MASK = {
  maskImage:
    "radial-gradient(ellipse 46% 58% at 25% 42%, rgb(0 0 0 / 0.3) 42%, black 80%)",
  WebkitMaskImage:
    "radial-gradient(ellipse 46% 58% at 25% 42%, rgb(0 0 0 / 0.3) 42%, black 80%)",
} as const;

// silhouette mode builds the figure structurally (sky lattice above each
// column's roofline, black tower voids with lit windows below) — measured
// luminance alone can't separate sky from tower bodies (both ~0.04).
const SKYLINE_PARAMS = {
  gamma: 0.95,
  maxAlpha: 0.85,
  floorRadius: 0.2,
  skyAlpha: 0.38,
  silhouette: { threshold: 0.4, lightCut: 0.08 },
};

function SkylineVariant() {
  return (
    <DotMatrix
      src={skylineUrl}
      cols={150}
      accent={false}
      shiftDown={6}
      params={SKYLINE_PARAMS}
      style={SKYLINE_MASK}
    />
  );
}

export function HeroBackdrop() {
  const variant = activeVariant();
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden text-text-primary" aria-hidden="true">
      {variant === "bloom" && <BloomVariant />}
      {variant === "plat" && <PlatVariant />}
      {variant === "contour" && <ContourVariant />}
      {variant === "geo" && <GeoVariant />}
      {variant === "curtain" && <CurtainVariant />}
      {variant === "skyline" && <SkylineVariant />}
    </div>
  );
}
