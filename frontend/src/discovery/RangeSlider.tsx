// Dual-thumb range slider for Property Discovery's continuous filters.
//
// Built from TWO overlaid native `<input type="range">` elements rather than a custom
// div-and-pointer-events widget. That is deliberate: each thumb is then a real slider to
// the accessibility tree and to the keyboard (arrows, Home/End, PageUp/PageDown) without
// us reimplementing any of it. All we add is `aria-valuetext`, so a screen reader hears
// "$250,000" instead of "250000".
//
// All 12 non-preset range filters in the registry are `boundMode: "both"`, so both thumbs
// are always rendered; `boundMode` is still honored for the min/max-only cases so the
// component stays correct if the registry grows one.

import { useId } from "react";

import { formatRangeValue } from "./rangeFormat";
import type { BoundMode, RangeDisplay } from "./types";

interface Props {
  domain: [number, number];
  step: number;
  display?: RangeDisplay;
  unit?: string | null;
  boundMode?: BoundMode;
  /** Undefined means "unset" — the thumb rests at its end of the domain. */
  min?: number;
  max?: number;
  onChange: (min: number | undefined, max: number | undefined) => void;
  /** Filter name, for per-thumb accessible labels. */
  name: string;
  labels: { minAria: string; maxAria: string };
  disabled?: boolean;
}

export function RangeSlider({
  domain,
  step,
  display,
  unit,
  boundMode = "both",
  min,
  max,
  onChange,
  name,
  labels,
  disabled,
}: Props) {
  const [lo, hi] = domain;
  const id = useId();

  // An unset bound sits at its end of the domain, so the filled track reads as
  // "everything" before the user touches it.
  const minVal = min ?? lo;
  const maxVal = max ?? hi;

  const span = hi - lo || 1;
  const pct = (v: number) => ((v - lo) / span) * 100;

  const showMin = boundMode !== "max";
  const showMax = boundMode !== "min";

  // Clamp so the thumbs can't cross. Committing `undefined` when a thumb returns to its
  // domain end keeps "untouched" distinct from "explicitly set to the boundary" — the
  // evaluator treats a boundless side as no constraint.
  const commitMin = (raw: number) => {
    const next = Math.min(raw, maxVal);
    onChange(next <= lo ? undefined : next, max);
  };
  const commitMax = (raw: number) => {
    const next = Math.max(raw, minVal);
    onChange(min, next >= hi ? undefined : next);
  };

  const thumbCls =
    "pointer-events-none absolute inset-0 h-full w-full appearance-none bg-transparent " +
    "[&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none " +
    "[&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full " +
    "[&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-accent " +
    "[&::-webkit-slider-thumb]:bg-dark-elevated [&::-webkit-slider-thumb]:cursor-pointer " +
    "[&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4 " +
    "[&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-accent " +
    "[&::-moz-range-thumb]:bg-dark-elevated [&::-moz-range-thumb]:cursor-pointer " +
    "focus-visible:outline-none [&::-webkit-slider-thumb]:focus-visible:ring-2 " +
    "disabled:cursor-not-allowed";

  return (
    <div className="relative h-5 select-none" data-testid={`range-slider-${name}`}>
      {/* Track */}
      <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-dark-border" />
      {/* Selected span */}
      <div
        className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-accent"
        style={{ left: `${pct(minVal)}%`, right: `${100 - pct(maxVal)}%` }}
      />

      {showMin && (
        <input
          id={`${id}-min`}
          type="range"
          className={thumbCls}
          min={lo}
          max={hi}
          step={step}
          value={minVal}
          disabled={disabled}
          aria-label={labels.minAria}
          aria-valuetext={formatRangeValue(minVal, display, unit)}
          onChange={(e) => commitMin(Number(e.target.value))}
        />
      )}
      {showMax && (
        <input
          id={`${id}-max`}
          type="range"
          className={thumbCls}
          min={lo}
          max={hi}
          step={step}
          value={maxVal}
          disabled={disabled}
          aria-label={labels.maxAria}
          aria-valuetext={formatRangeValue(maxVal, display, unit)}
          onChange={(e) => commitMax(Number(e.target.value))}
        />
      )}
    </div>
  );
}
