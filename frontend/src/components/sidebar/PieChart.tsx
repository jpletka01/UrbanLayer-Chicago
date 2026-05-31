import { useState, useRef, useCallback, useEffect } from "react";
import type { PieSlice } from "../../lib/analytics";
import { capLabel } from "../../lib/mapColors";

interface Props {
  slices: PieSlice[];
  size?: number;
  innerRadiusRatio?: number;
  thinThreshold?: number;
}

const EXPAND_PX = 3;
const RING_GAP = 3;
const RING_WIDTH = 10;
const RING_EXPAND_PX = 3;
const RING_FADE_MS = 250;
const RING_GRACE_MS = 100;
const RING_MARGIN = 1 + RING_EXPAND_PX + RING_WIDTH + RING_GAP + EXPAND_PX;

function polar(cx: number, cy: number, r: number, a: number) {
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
}

function arcPath(
  cx: number, cy: number,
  oR: number, iR: number,
  sa: number, ea: number,
): string {
  const os = polar(cx, cy, oR, sa);
  const oe = polar(cx, cy, oR, ea);
  const ie = polar(cx, cy, iR, ea);
  const is_ = polar(cx, cy, iR, sa);
  const lg = ea - sa > Math.PI ? 1 : 0;
  return [
    `M ${os.x} ${os.y}`,
    `A ${oR} ${oR} 0 ${lg} 1 ${oe.x} ${oe.y}`,
    `L ${ie.x} ${ie.y}`,
    `A ${iR} ${iR} 0 ${lg} 0 ${is_.x} ${is_.y}`,
    "Z",
  ].join(" ");
}

interface Geo {
  sa: number;
  ea: number;
  mid: number;
}

export function PieChart({
  slices,
  size = 160,
  innerRadiusRatio = 0.6,
  thinThreshold = 0.02,
}: Props) {
  const [hoveredMain, setHoveredMain] = useState<number | null>(null);
  const [hoveredRing, setHoveredRing] = useState<number | null>(null);
  const [ringVisible, setRingVisible] = useState(false);
  const [legendExpanded, setLegendExpanded] = useState(false);
  const graceRef = useRef<number>(0);

  useEffect(() => () => { clearTimeout(graceRef.current); }, []);

  if (!slices.length) return null;
  const sliceTotal = slices.reduce((a, s) => a + s.value, 0);
  if (!sliceTotal) return null;

  const cx = size / 2;
  const cy = size / 2;
  const outerR = size / 2 - RING_MARGIN;
  const innerR = outerR * innerRadiusRatio;
  const ringIR = outerR + RING_GAP;
  const ringOR = ringIR + RING_WIDTH;

  // --- Geometry ---

  const geos: Geo[] = [];
  let angle = -Math.PI / 2;
  for (const s of slices) {
    const sweep = (s.value / sliceTotal) * Math.PI * 2;
    geos.push({ sa: angle, ea: angle + sweep, mid: angle + sweep / 2 });
    angle += sweep;
  }

  const thinMap: { mi: number; val: number }[] = [];
  for (let i = 0; i < slices.length; i++) {
    if (slices[i].value / sliceTotal <= thinThreshold) {
      thinMap.push({ mi: i, val: slices[i].value });
    }
  }
  const hasThin = thinMap.length > 0;

  const thinTotal = thinMap.reduce((s, t) => s + t.val, 0);
  const ringGeos: Geo[] = [];
  if (hasThin && thinTotal > 0) {
    let ra = -Math.PI / 2;
    for (const t of thinMap) {
      const sw = (t.val / thinTotal) * Math.PI * 2;
      ringGeos.push({ sa: ra, ea: ra + sw, mid: ra + sw / 2 });
      ra += sw;
    }
  }

  // --- Ring visibility with grace period ---

  const cancelGrace = useCallback(() => {
    clearTimeout(graceRef.current);
    graceRef.current = 0;
  }, []);

  const showRingNow = useCallback(() => {
    cancelGrace();
    setRingVisible(true);
  }, [cancelGrace]);

  const hideRingLater = useCallback(() => {
    cancelGrace();
    graceRef.current = window.setTimeout(() => {
      setRingVisible(false);
      setHoveredRing(null);
    }, RING_GRACE_MS);
  }, [cancelGrace]);

  // --- Active hover resolution ---

  let activeIdx: number | null = null;
  if (hoveredRing !== null && thinMap[hoveredRing]) {
    activeIdx = thinMap[hoveredRing].mi;
  } else if (hoveredMain !== null) {
    activeIdx = hoveredMain;
  }

  const activeSlice = activeIdx !== null ? slices[activeIdx] : null;
  const activePct = activeSlice
    ? ((activeSlice.value / sliceTotal) * 100).toFixed(1)
    : null;

  // --- Render main donut ---

  const mainPaths: React.ReactNode[] = [];

  if (slices.length === 1) {
    mainPaths.push(
      <circle
        key="solo"
        cx={cx}
        cy={cy}
        r={outerR}
        fill={slices[0].color}
        onMouseEnter={() => setHoveredMain(0)}
        onMouseLeave={() => setHoveredMain(null)}
        style={{ cursor: "pointer" }}
      />,
      <circle
        key="hole"
        cx={cx}
        cy={cy}
        r={innerR}
        fill="var(--color-dark-surface, #1a1a1a)"
        style={{ pointerEvents: "none" }}
      />,
    );
  } else {
    for (let i = 0; i < slices.length; i++) {
      const g = geos[i];
      const thin = slices[i].value / sliceTotal <= thinThreshold;
      const hovered = activeIdx === i;
      const dx = hovered ? Math.cos(g.mid) * EXPAND_PX : 0;
      const dy = hovered ? Math.sin(g.mid) * EXPAND_PX : 0;
      const opacity = activeIdx !== null && activeIdx !== i ? 0.4 : 1;

      mainPaths.push(
        <path
          key={`m${i}`}
          d={arcPath(cx, cy, outerR, innerR, g.sa, g.ea)}
          fill={slices[i].color}
          opacity={opacity}
          style={{
            transform: `translate(${dx}px,${dy}px)`,
            transition: "transform 150ms ease-out, opacity 150ms ease",
            pointerEvents: thin ? "none" : undefined,
            cursor: thin ? undefined : "pointer",
          }}
          onMouseEnter={
            thin
              ? undefined
              : () => setHoveredMain(i)
          }
          onMouseLeave={
            thin
              ? undefined
              : () => setHoveredMain(null)
          }
        />,
      );
    }

    // Enlarged invisible hit areas for thin slices, rendered on top
    for (let i = 0; i < slices.length; i++) {
      if (slices[i].value / sliceTotal > thinThreshold) continue;
      const g = geos[i];
      mainPaths.push(
        <path
          key={`hit${i}`}
          d={arcPath(cx, cy, outerR + 5, Math.max(0, innerR - 5), g.sa, g.ea)}
          fill="transparent"
          style={{ pointerEvents: "all", cursor: "pointer" }}
          onMouseEnter={() => {
            setHoveredMain(i);
            showRingNow();
          }}
          onMouseLeave={() => {
            setHoveredMain(null);
            hideRingLater();
          }}
        />,
      );
    }
  }

  // --- Render outer ring for thin slices ---

  const ringPaths: React.ReactNode[] = [];

  if (hasThin) {
    for (let ri = 0; ri < thinMap.length; ri++) {
      const g = ringGeos[ri];
      const mi = thinMap[ri].mi;
      const hovered = hoveredRing === ri;
      const dx = hovered ? Math.cos(g.mid) * RING_EXPAND_PX : 0;
      const dy = hovered ? Math.sin(g.mid) * RING_EXPAND_PX : 0;

      let opacity = 1;
      if (hoveredRing !== null) {
        opacity = hoveredRing === ri ? 1 : 0.25;
      } else if (activeIdx !== null) {
        opacity = mi === activeIdx ? 1 : 0.25;
      }

      ringPaths.push(
        <path
          key={`r${ri}`}
          d={arcPath(cx, cy, ringOR, ringIR, g.sa, g.ea)}
          fill={slices[mi].color}
          opacity={opacity}
          style={{
            cursor: "pointer",
            transform: `translate(${dx}px,${dy}px)`,
            transition: "transform 150ms ease-out, opacity 150ms ease",
          }}
          onMouseEnter={() => {
            cancelGrace();
            setHoveredRing(ri);
            setHoveredMain(null);
            setRingVisible(true);
          }}
          onMouseLeave={() => {
            setHoveredRing(null);
            hideRingLater();
          }}
        />,
      );
    }
  }

  // --- Layout ---

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
        >
          {mainPaths}
          {hasThin && (
            <g
              style={{
                opacity: ringVisible ? 1 : 0,
                transition: `opacity ${RING_FADE_MS}ms ease`,
                pointerEvents: ringVisible ? "auto" : "none",
              }}
            >
              {ringPaths}
            </g>
          )}
        </svg>

        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center">
            {activeSlice ? (
              <>
                <div className="text-sm font-semibold text-text-primary">
                  {activePct}%
                </div>
                <div
                  className="text-[9px] text-text-secondary leading-tight mx-auto"
                  style={{
                    maxWidth: innerR * 1.5,
                    overflow: "hidden",
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                  }}
                >
                  {capLabel(activeSlice.label)}
                </div>
                <div className="text-[9px] text-text-muted">
                  {activeSlice.value.toLocaleString()}
                </div>
              </>
            ) : (
              <>
                <div className="text-lg font-semibold text-text-primary">
                  {sliceTotal.toLocaleString()}
                </div>
                <div className="text-[9px] text-text-muted uppercase tracking-wide">
                  Total
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="w-full grid grid-cols-2 gap-x-3 gap-y-1">
        {(legendExpanded ? slices : slices.slice(0, 8)).map((slice) => {
          const pct = ((slice.value / sliceTotal) * 100).toFixed(1);
          return (
            <div key={slice.label} className="flex items-center gap-1.5 min-w-0">
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: slice.color }}
              />
              <span className="text-[10px] text-text-secondary truncate">
                {capLabel(slice.label)}
              </span>
              <span className="text-[10px] text-text-muted ml-auto shrink-0">
                {pct}%
              </span>
            </div>
          );
        })}
        {slices.length > 8 && (
          <button
            onClick={() => setLegendExpanded(e => !e)}
            className="text-[10px] text-text-muted hover:text-text-secondary
                       transition-colors col-span-2 text-left"
          >
            {legendExpanded
              ? "Show less"
              : `+${slices.length - 8} more`}
          </button>
        )}
      </div>
    </div>
  );
}

