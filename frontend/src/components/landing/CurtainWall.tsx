// Renders a procedural curtain-wall facade (see facade.ts) as a single SVG.
// Line-work is currentColor under the parent's text color, so it inverts with
// the theme; the opacity map below carries the structural line-weight
// hierarchy (party walls > braces > columns > floors > mullions).

import { useMemo } from "react";
import type { CSSProperties } from "react";
import { generateFacade } from "./facade";

const STROKE_OPACITY = {
  partyWalls: 0.2,
  columns: 0.12,
  floors: 0.09,
  mullions: 0.06,
  braces: 0.13,
} as const;

interface CurtainWallProps {
  seed: number;
  width?: number;
  height?: number;
  className?: string;
  style?: CSSProperties;
}

export function CurtainWall({
  seed,
  width = 1440,
  height = 900,
  className = "absolute inset-0 h-full w-full",
  style,
}: CurtainWallProps) {
  const model = useMemo(() => generateFacade({ seed, width, height }), [seed, width, height]);
  return (
    <svg
      className={className}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid slice"
      style={style}
      stroke="currentColor"
      strokeWidth="1"
      fill="none"
      aria-hidden="true"
    >
      {(Object.entries(model.paths) as Array<[keyof typeof STROKE_OPACITY, string]>).map(([k, d]) =>
        d ? <path key={k} d={d} strokeOpacity={STROKE_OPACITY[k]} vectorEffect="non-scaling-stroke" /> : null,
      )}
      {model.spandrelPath && (
        <path d={model.spandrelPath} fill="currentColor" fillOpacity={0.05} stroke="none" />
      )}
      {model.litPath && <path d={model.litPath} fill="currentColor" fillOpacity={0.15} stroke="none" />}
      {/* the one orange lit window — the found parcel */}
      <path d={model.orangePath} fill="rgb(249 164 116 / 0.9)" stroke="none" />
      <circle
        cx={model.orange.cx}
        cy={model.orange.cy}
        r={12}
        stroke="rgb(249 164 116 / 0.55)"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
