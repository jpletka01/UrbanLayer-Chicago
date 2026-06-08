import { useCallback, useRef } from "react";
import i18n from "../../lib/i18n";

interface Props {
  minDate: number;
  maxDate: number;
  startDate: number;
  endDate: number;
  onChange: (start: number, end: number) => void;
}

const LOCALE_MAP: Record<string, string> = { en: "en-US", es: "es-MX" };

function formatShort(epoch: number): string {
  const locale = LOCALE_MAP[i18n.language] ?? "en-US";
  return new Date(epoch).toLocaleDateString(locale, {
    month: "short",
    day: "numeric",
  });
}

export function DateRangeSlider({ minDate, maxDate, startDate, endDate, onChange }: Props) {
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const range = maxDate - minDate;
  if (range <= 0) return null;

  const leftPercent = ((startDate - minDate) / range) * 100;
  const rightPercent = ((endDate - minDate) / range) * 100;

  const debouncedOnChange = useCallback(
    (s: number, e: number) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => onChange(s, e), 30);
    },
    [onChange],
  );

  const handleStartChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Number(e.target.value);
    debouncedOnChange(Math.min(v, endDate), endDate);
  };

  const handleEndChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Number(e.target.value);
    debouncedOnChange(startDate, Math.max(v, startDate));
  };

  return (
    <div
      className="w-full bg-dark-surface/90 backdrop-blur-sm border border-dark-border
                 rounded-lg px-3 py-2"
    >
      <div className="relative h-4 flex items-center">
        {/* Track background */}
        <div className="absolute inset-x-0 h-1 rounded-full bg-dark-border" />

        {/* Active range highlight */}
        <div
          className="absolute h-1 rounded-full bg-accent/60"
          style={{ left: `${leftPercent}%`, width: `${rightPercent - leftPercent}%` }}
        />

        {/* Start handle */}
        <input
          type="range"
          min={minDate}
          max={maxDate}
          value={startDate}
          onChange={handleStartChange}
          className="date-slider-thumb absolute inset-x-0 w-full appearance-none bg-transparent pointer-events-none"
          style={{ zIndex: startDate > maxDate - range * 0.1 ? 5 : 3 }}
        />

        {/* End handle */}
        <input
          type="range"
          min={minDate}
          max={maxDate}
          value={endDate}
          onChange={handleEndChange}
          className="date-slider-thumb absolute inset-x-0 w-full appearance-none bg-transparent pointer-events-none"
          style={{ zIndex: 4 }}
        />
      </div>

      {/* Date labels */}
      <div className="flex justify-between mt-1">
        <span className="text-[10px] text-text-muted">{formatShort(startDate)}</span>
        <span className="text-[10px] text-text-muted">{formatShort(endDate)}</span>
      </div>

      <style>{`
        .date-slider-thumb::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          height: 14px;
          width: 14px;
          border-radius: 50%;
          background: #e2e0dc;
          border: 2px solid #555;
          cursor: pointer;
          pointer-events: auto;
          position: relative;
        }
        .date-slider-thumb::-moz-range-thumb {
          height: 14px;
          width: 14px;
          border-radius: 50%;
          background: #e2e0dc;
          border: 2px solid #555;
          cursor: pointer;
          pointer-events: auto;
        }
        .date-slider-thumb::-webkit-slider-runnable-track {
          height: 4px;
          background: transparent;
        }
        .date-slider-thumb::-moz-range-track {
          height: 4px;
          background: transparent;
        }
      `}</style>
    </div>
  );
}
