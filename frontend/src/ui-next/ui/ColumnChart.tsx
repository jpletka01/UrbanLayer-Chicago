// SnowUI's column chart with a value you can read on demand (decision Item 99, owner's review: the browser's own
// tooltip on a bar "didn't feel like part of the graphic"). Hovering a column shows its label and value in a callout
// drawn above it; a click pins that callout until the same column is clicked again (Escape also unpins). With nothing
// active, the highlighted column (this lot's latest) keeps its value shown, so the chart always says one figure.
// Each column is a real button (keyboard focus shows its value, Enter or Space pins), named for screen readers.
// A dollar scale with faint gridlines sits on the left. Ordinary columns Sapphire, the highlighted one this lot's black.
import { useState } from "react";

export interface Column {
  key: string;
  /** Under the column ("’24"). */
  tick: string;
  /** In the callout and the accessible name ("2024"). */
  label: string;
  value: number;
  valueText: string;
  highlight?: boolean;
}

export function ColumnChart({ columns, top, scale, heightClass = "h-36", testId, ariaLabel }: {
  columns: Column[];
  /** The scale's top (a round number at or above the largest value). */
  top: number;
  /** The scale's labels, top to bottom (top, half, zero). */
  scale: [string, string, string];
  heightClass?: string;
  testId?: string;
  /** Names the chart as a group ("Assessor's value by year"). */
  ariaLabel: string;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);
  const fallback = columns.find((c) => c.highlight)?.key ?? null;
  const active = pinned ?? hover ?? fallback;
  const ticks = [top, top / 2, 0];

  return (
    <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-2">
      <div aria-hidden className={`flex ${heightClass} flex-col justify-between text-right text-caption nx-muted tabular-nums`}>
        {scale.map((s, i) => <span key={i} className="-my-2 leading-4">{s}</span>)}
      </div>
      <div
        className={`relative ${heightClass}`}
        role="group"
        aria-label={ariaLabel}
        data-testid={testId}
        onPointerLeave={() => setHover(null)}
        onKeyDown={(e) => { if (e.key === "Escape" && pinned) { e.stopPropagation(); setPinned(null); } }}
      >
        {ticks.map((v) => <span key={v} aria-hidden className="absolute inset-x-0 border-t border-nx-ink/10" style={{ bottom: `${(v / top) * 100}%` }} />)}
        <div className="absolute inset-0 flex items-end gap-2">
          {columns.map((c, i) => {
            const h = Math.max(2, (c.value / top) * 100);
            const isActive = active === c.key;
            const edge = i === 0 ? "left-0" : i === columns.length - 1 ? "right-0" : "left-1/2 -translate-x-1/2";
            return (
              <div key={c.key} className="relative flex h-full min-w-0 flex-1 flex-col items-center justify-end">
                {isActive && (
                  <span
                    aria-hidden
                    className={`pointer-events-none absolute z-10 whitespace-nowrap rounded-lg px-2 py-1 text-caption font-semibold tabular-nums shadow-[0_2px_8px_rgb(0_0_0/0.15)] ${edge} ${c.highlight ? "bg-nx-lot text-nx-page" : "bg-nx-ink text-nx-page"}`}
                    style={{ bottom: `calc(${h}% + 6px)` }}
                    data-testid="column-callout"
                  >
                    <span className="font-normal opacity-80">{c.label}</span> {c.valueText}
                  </span>
                )}
                <button
                  type="button"
                  aria-label={`${c.label}: ${c.valueText}`}
                  aria-pressed={pinned === c.key}
                  onPointerEnter={(e) => { if (e.pointerType !== "touch") setHover(c.key); }}
                  onFocus={() => setHover(c.key)}
                  onBlur={() => setHover(null)}
                  onClick={() => setPinned((p) => (p === c.key ? null : c.key))}
                  className={`block w-full max-w-10 cursor-pointer rounded-t-md transition-[filter,box-shadow] ${c.highlight ? "bg-nx-lot" : "bg-nx-chart-1"} ${isActive && !c.highlight ? "brightness-90" : ""} ${pinned === c.key ? "shadow-[0_0_0_2px_rgb(var(--nx-page)),0_0_0_4px_rgb(var(--nx-ink)/0.5)]" : ""}`}
                  style={{ height: `${h}%` }}
                />
              </div>
            );
          })}
        </div>
      </div>
      <span aria-hidden />
      <div aria-hidden className="mt-2 flex gap-2 text-caption nx-muted tabular-nums">
        {columns.map((c) => (
          <span key={c.key} className={`min-w-0 flex-1 text-center ${active === c.key ? "font-semibold text-nx-ink" : ""}`}>{c.tick}</span>
        ))}
      </div>
    </div>
  );
}
