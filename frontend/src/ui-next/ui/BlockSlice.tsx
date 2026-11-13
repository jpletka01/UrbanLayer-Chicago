// The block around a lot (Discovery's list card, Item 104; shared with Saved and the home, Item 119): neighbors in
// their room-to-build color, this lot in its own with an ink outline, the zoning as a colored tag. A lot with no PIN
// (the Profile found only an address) draws its own outline from the County record instead; nothing is invented.
import { useEffect, useState } from "react";
import { ZONING_COLORS } from "../map/mapStyle";
import { contextPaths, fetchLotContext } from "../discovery/discoveryData";
import { measureSteps } from "../discovery/discoveryModel";
import { outlinePath } from "../home/lotMemory";

const ROOM_COLOR: Record<string, string> = Object.fromEntries(measureSteps("room").map((s) => [s.value, s.color]));
const W = 320;
const H = 96;

export function BlockSlice({ pin10, zoneTag, family, outline = null, className = "h-24 rounded-t-2xl" }: {
  pin10: string | null;
  zoneTag: string | null;
  family: keyof typeof ZONING_COLORS | null;
  /** The lot's own ring (lon/lat), drawn when there is no PIN to ask the block for. */
  outline?: Array<[number, number]> | null;
  /** Height and rounding: the slice sits at the top of its card. */
  className?: string;
}) {
  const [paths, setPaths] = useState<ReturnType<typeof contextPaths> | null>(null);
  useEffect(() => {
    if (!pin10) return;
    let live = true;
    fetchLotContext(pin10).then((fc) => { if (live) setPaths(fc ? contextPaths(fc, W, H) : []); });
    return () => { live = false; };
  }, [pin10]);
  const tag = family ? ZONING_COLORS[family] : null;
  const own = !pin10 && outline && outline.length >= 3 ? outlinePath(outline, W, H, 14) : null;
  return (
    <div className={`relative overflow-hidden bg-nx-ink/[0.04] ${className}`} data-testid="block-slice">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className="h-full w-full" aria-hidden>
        {(paths ?? []).map((p, i) => (
          <path key={i} d={p.d}
            fill={p.r && ROOM_COLOR[p.r] ? ROOM_COLOR[p.r] : "rgb(var(--nx-ink) / 0.06)"}
            fillOpacity={p.me ? 1 : 0.55}
            stroke={p.me ? "rgb(var(--nx-lot))" : "rgb(var(--nx-page))"} strokeWidth={p.me ? 2.5 : 1} strokeLinejoin="round" />
        ))}
        {own && <path d={own} fill="rgb(var(--nx-ink) / 0.08)" stroke="rgb(var(--nx-lot))" strokeWidth={2.5} strokeLinejoin="round" />}
      </svg>
      {zoneTag && (
        <span className="absolute left-2 top-2 rounded-md px-1.5 py-0.5 text-[11px] font-semibold text-[#1c1c1c]"
          style={{ background: tag ? tag[1] : "#C9CED6" }}>
          {zoneTag}
        </span>
      )}
    </div>
  );
}
