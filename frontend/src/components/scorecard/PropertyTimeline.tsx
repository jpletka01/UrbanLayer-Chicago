// Interactive property timeline — the Economics module's centerpiece chart.
// Assessment history drawn as stacked columns (land + building), with sales and
// won appeals as event markers on a top lane. Built per the dataviz method:
// ≤24px columns, 4px rounded data-end (square baseline), 2px surface gaps
// between stacked segments, hairline gridlines, per-mark hover tooltip (the
// column is the hit target, keyboard-focusable), legend for the two series,
// text in text tokens. The land/building split is the honest view — a vacant
// parcel reads as land-only bars instead of hiding behind a total line.
//
// Chart-color rule (2026-07-07, Jack): series 1 = BRAND ORANGE, series 2 = a
// NEUTRAL gray step — never an off-brand hue (the first cut used a validated
// blue and read as clip-art). Identity is carried by stacking position (land
// is always the base) + the legend, so the neutral's low chroma is deliberate
// de-emphasis, not a validator miss. Building wears the accent: it's the
// series that changes when something is built or torn down.
import { useMemo, useState, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { AssessmentRecord, SaleRecord, AppealRecord } from "../../lib/types";
import { formatDate } from "../../lib/format";
import { useThemeContext } from "../../contexts/ThemeContext";

const SERIES = {
  dark: { land: "#55555e", building: "#f9a474" },
  light: { land: "#b5b1ab", building: "#c2410c" },
};

function fmtCompact(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(Math.abs(n) >= 10_000_000 ? 0 : 1)}M`;
  if (Math.abs(n) >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n)}`;
}
function fmtFull(n: number): string {
  return `$${Math.round(n).toLocaleString()}`;
}

/** Clean 3–4-tick axis: 1/2/2.5/5×10^k step covering [0, max]. */
function niceTicks(max: number): number[] {
  if (!(max > 0)) return [];
  const rough = max / 4;
  const pow = Math.pow(10, Math.floor(Math.log10(rough)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * pow).find((s) => s >= rough) ?? pow * 10;
  const ticks: number[] = [];
  for (let v = step; v <= max * 1.001; v += step) ticks.push(v);
  return ticks;
}

interface YearPoint {
  year: number;
  land: number;
  building: number;
  total: number;
  yoyPct: number | null;
  sales: SaleRecord[];
  appeal: AppealRecord | null;
}

const W = 760;
const H = 216;
const M = { top: 30, right: 10, bottom: 22, left: 48 };
const LANE_Y = 14; // event-marker lane, above the plot

export function PropertyTimeline({ history, sales, appeals }: {
  history: AssessmentRecord[];
  sales: SaleRecord[];
  appeals?: AppealRecord[] | null;
}) {
  const { t } = useTranslation("data");
  const { resolvedTheme } = useThemeContext();
  const colors = SERIES[resolvedTheme === "light" ? "light" : "dark"];
  const [hover, setHover] = useState<number | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  const points = useMemo<YearPoint[]>(() => {
    const pts = history
      .filter((a): a is AssessmentRecord & { year: number; total: number } =>
        a.year != null && a.total != null && a.total > 0)
      .sort((a, b) => a.year - b.year)
      .map((a) => ({
        year: a.year,
        land: Math.max(a.land ?? 0, 0),
        building: Math.max(a.building ?? 0, 0),
        total: a.total,
        yoyPct: null as number | null,
        sales: [] as SaleRecord[],
        appeal: null as AppealRecord | null,
      }));
    for (let i = 1; i < pts.length; i++) {
      const prev = pts[i - 1].total;
      if (prev > 0) pts[i].yoyPct = Math.round(((pts[i].total - prev) / prev) * 100);
    }
    const byYear = new Map(pts.map((p) => [p.year, p]));
    for (const s of sales) {
      if (!s.date || s.price == null || s.price <= 0) continue;
      const y = byYear.get(new Date(s.date).getFullYear());
      if (y) y.sales.push(s);
    }
    for (const a of appeals ?? []) {
      if (a.year == null || a.reduction_pct == null) continue;
      const y = byYear.get(a.year);
      if (y && !y.appeal) y.appeal = a;
    }
    return pts;
  }, [history, sales, appeals]);

  if (points.length < 2) return null;

  const maxTotal = Math.max(...points.map((p) => p.total));
  const ticks = niceTicks(maxTotal);
  const yMax = Math.max(maxTotal, ticks[ticks.length - 1] ?? maxTotal);
  const plotW = W - M.left - M.right;
  const plotH = H - M.top - M.bottom;
  const slot = plotW / points.length;
  const barW = Math.min(24, slot * 0.55);
  const xCenter = (i: number) => M.left + slot * i + slot / 2;
  const y = (v: number) => M.top + plotH - (v / yMax) * plotH;
  const baseline = M.top + plotH;
  const SEG_GAP = 2; // surface gap between stacked segments

  const hasSales = points.some((p) => p.sales.length > 0);
  const hasAppeals = points.some((p) => p.appeal != null);
  const labelEvery = points.length > 9 ? 2 : 1;

  const hovered = hover != null ? points[hover] : null;

  // Tooltip anchoring: percentage of the wrapper width, edge-clamped so the
  // readout never leaves the chart.
  const tipLeftPct = hover != null ? (xCenter(hover) / W) * 100 : 0;
  const tipTranslate = tipLeftPct < 18 ? "0%" : tipLeftPct > 82 ? "-100%" : "-50%";

  return (
    <div ref={wrapRef} className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={t("property.timeline.ariaLabel", {
          from: points[0].year, to: points[points.length - 1].year,
        })}
        onPointerLeave={() => setHover(null)}
      >
        {/* gridlines + y ticks — recessive hairlines, clean numbers */}
        {ticks.map((v) => (
          <g key={v}>
            <line x1={M.left} y1={y(v)} x2={W - M.right} y2={y(v)}
              stroke="rgb(var(--border))" strokeWidth="1" />
            <text x={M.left - 6} y={y(v) + 3} textAnchor="end"
              className="fill-[rgb(var(--text-muted))]" fontSize="10">
              {fmtCompact(v)}
            </text>
          </g>
        ))}
        <line x1={M.left} y1={baseline} x2={W - M.right} y2={baseline}
          stroke="rgb(var(--border-strong))" strokeWidth="1" />

        {points.map((p, i) => {
          const cx = xCenter(i);
          const x0 = cx - barW / 2;
          const landH = (p.land / yMax) * plotH;
          const bldgH = (p.building / yMax) * plotH;
          const landTop = baseline - landH;
          // building sits above land with a 2px surface gap (gap eats into the
          // building segment so the stack's outer height stays honest)
          const bldgBottom = landH > 0 && bldgH > 0 ? landTop - SEG_GAP : baseline;
          const bldgTop = bldgBottom - Math.max(bldgH - (landH > 0 ? SEG_GAP : 0), 0);
          const isHover = hover === i;
          const lift = isHover ? { filter: "brightness(1.18)" } : undefined;
          const topOfStack = Math.min(landTop, bldgTop);
          return (
            <g key={p.year}>
              {/* land — bottom segment, square baseline; rounded only when it
                  IS the top of the stack (vacant years) */}
              {landH > 0.5 && (
                <path
                  d={roundedTopRect(x0, landTop, barW, landH, p.building > 0 ? 0 : 4)}
                  fill={colors.land} style={lift}
                />
              )}
              {bldgTop < bldgBottom && (
                <path
                  d={roundedTopRect(x0, bldgTop, barW, bldgBottom - bldgTop, 4)}
                  fill={colors.building} style={lift}
                />
              )}
              {/* event markers — top lane, ink shapes (identity by shape + legend) */}
              {p.sales.length > 0 && (
                <path
                  d={diamond(cx, LANE_Y, 5)}
                  fill="rgb(var(--text-secondary))"
                  stroke="rgb(var(--bg))" strokeWidth="2"
                />
              )}
              {p.appeal && (
                <path
                  d={triangleDown(cx + (p.sales.length > 0 ? 12 : 0), LANE_Y, 5)}
                  fill="rgb(var(--text-muted))"
                  stroke="rgb(var(--bg))" strokeWidth="2"
                />
              )}
              {/* year label */}
              {(i % labelEvery === 0 || i === points.length - 1) && (
                <text x={cx} y={H - 6} textAnchor="middle"
                  className="fill-[rgb(var(--text-muted))]" fontSize="10">
                  {p.year}
                </text>
              )}
              {/* full-slot hit target — bigger than the mark, keyboard-reachable */}
              <rect
                x={M.left + slot * i} y={0} width={slot} height={H}
                fill="transparent"
                tabIndex={0}
                aria-label={`${p.year}: ${fmtFull(p.total)}`}
                onPointerEnter={() => setHover(i)}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
                style={{ outline: "none" }}
              />
              {isHover && (
                <rect x={M.left + slot * i} y={M.top - 4} width={slot} height={plotH + 4}
                  fill="rgb(var(--text-primary) / 0.04)" pointerEvents="none" />
              )}
              <title>{`${p.year} · ${fmtFull(p.total)}`}</title>
              {/* stack-top value label on hover only (selective labeling) */}
              {isHover && (
                <text x={cx} y={topOfStack - 5} textAnchor="middle"
                  className="fill-[rgb(var(--text-secondary))]" fontSize="10" pointerEvents="none">
                  {fmtCompact(p.total)}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Tooltip — value leads, series keyed by a short color stroke */}
      {hovered && (
        <div
          className="pointer-events-none absolute top-8 z-10 rounded-lg border border-dark-border bg-dark-elevated shadow-card px-3 py-2 text-caption whitespace-nowrap"
          style={{ left: `${tipLeftPct}%`, transform: `translateX(${tipTranslate})` }}
          role="status"
        >
          <div className="text-text-primary font-medium">
            {hovered.year}
            {hovered.yoyPct != null && hovered.yoyPct !== 0 && (
              <span className="text-text-muted font-normal">
                {" "}· {hovered.yoyPct > 0 ? "+" : ""}{hovered.yoyPct}% {t("property.timeline.vsPrior")}
              </span>
            )}
          </div>
          <TipRow color={colors.building} label={t("property.timeline.building")}
            value={hovered.building > 0 ? fmtFull(hovered.building) : "—"} />
          <TipRow color={colors.land} label={t("property.timeline.land")} value={fmtFull(hovered.land)} />
          <div className="mt-0.5 text-text-secondary">
            <span className="text-text-primary font-medium">{fmtFull(hovered.total)}</span>{" "}
            {t("property.timeline.totalAssessed")}
          </div>
          {hovered.sales.map((s, i) => (
            <div key={i} className="mt-0.5 text-text-secondary">
              ◆ <span className="text-text-primary font-medium">{s.price != null ? fmtFull(s.price) : "—"}</span>{" "}
              {t("property.timeline.sold")}{s.date ? ` · ${formatDate(s.date)}` : ""}
            </div>
          ))}
          {hovered.appeal && (
            <div className="mt-0.5 text-text-secondary">
              ▾ {t("property.timeline.appealWon", { pct: hovered.appeal.reduction_pct })}
            </div>
          )}
        </div>
      )}

      {/* Legend — always present (2 series); event keys only when present */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1.5 text-caption text-text-secondary">
        <LegendKey swatch={<rect width="10" height="10" rx="2" fill={colors.land} />}>
          {t("property.timeline.land")}
        </LegendKey>
        <LegendKey swatch={<rect width="10" height="10" rx="2" fill={colors.building} />}>
          {t("property.timeline.building")}
        </LegendKey>
        {hasSales && (
          <LegendKey swatch={<path d={diamond(5, 5, 4.5)} fill="rgb(var(--text-secondary))" />}>
            {t("property.timeline.sale")}
          </LegendKey>
        )}
        {hasAppeals && (
          <LegendKey swatch={<path d={triangleDown(5, 5, 4.5)} fill="rgb(var(--text-muted))" />}>
            {t("property.timeline.appeal")}
          </LegendKey>
        )}
      </div>
    </div>
  );
}

function TipRow({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span aria-hidden className="inline-block w-2.5 h-[3px] rounded-full" style={{ background: color }} />
      <span className="text-text-primary font-medium">{value}</span>
      <span className="text-text-muted">{label}</span>
    </div>
  );
}

function LegendKey({ swatch, children }: { swatch: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden>{swatch}</svg>
      {children}
    </span>
  );
}

/** Rect path with rounded TOP corners only (data-end), square baseline. */
function roundedTopRect(x: number, top: number, w: number, h: number, r: number): string {
  const rr = Math.min(r, w / 2, h);
  return [
    `M ${x} ${top + h}`,
    `L ${x} ${top + rr}`,
    `Q ${x} ${top} ${x + rr} ${top}`,
    `L ${x + w - rr} ${top}`,
    `Q ${x + w} ${top} ${x + w} ${top + rr}`,
    `L ${x + w} ${top + h}`,
    "Z",
  ].join(" ");
}

function diamond(cx: number, cy: number, r: number): string {
  return `M ${cx} ${cy - r} L ${cx + r} ${cy} L ${cx} ${cy + r} L ${cx - r} ${cy} Z`;
}

function triangleDown(cx: number, cy: number, r: number): string {
  return `M ${cx - r} ${cy - r * 0.8} L ${cx + r} ${cy - r * 0.8} L ${cx} ${cy + r} Z`;
}
