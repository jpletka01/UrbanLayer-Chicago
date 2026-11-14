import { useState } from "react";
import type { DistributionBucket } from "../../lib/types";

interface Props {
  bars: DistributionBucket[];
  accentColor?: string;
}

const DEFAULT_COLOR = "#fe9179";

export function BarChart({ bars, accentColor = DEFAULT_COLOR }: Props) {
  const [hovered, setHovered] = useState<number | null>(null);
  const max = Math.max(...bars.map((b) => b.value), 1);

  return (
    <div className="space-y-1">
      {bars.map((bar, i) => (
        <div
          key={bar.label}
          className="group flex items-center gap-2"
          onMouseEnter={() => setHovered(i)}
          onMouseLeave={() => setHovered(null)}
        >
          <span className="text-micro nx-muted w-[72px] shrink-0 text-right truncate">
            {bar.label}
          </span>
          <div className="flex-1 h-3.5 bg-nx-block rounded-sm overflow-hidden relative">
            <div
              className="h-full rounded-sm transition-all duration-200"
              style={{
                width: `${(bar.value / max) * 100}%`,
                backgroundColor: accentColor,
                opacity: hovered === null || hovered === i ? 0.85 : 0.4,
              }}
            />
          </div>
          <span
            className="text-micro font-mono w-[36px] shrink-0 text-right transition-colors"
            style={{ color: hovered === i ? "#c6c7f8" : "#8a8a8a" }}
          >
            {bar.value.toFixed(0)}%
          </span>
        </div>
      ))}
    </div>
  );
}
