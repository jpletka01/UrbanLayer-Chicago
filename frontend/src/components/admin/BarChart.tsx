import { useState } from "react";

interface Bar {
  label: string;
  value: number;
  color: string;
}

interface Props {
  bars: Bar[];
  height?: number;
}

const BAR_HEIGHT = 28;
const GAP = 6;
const LABEL_WIDTH = 32;
const VALUE_WIDTH = 36;

export function BarChart({ bars, height }: Props) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (bars.length === 0) {
    return (
      <div className="flex items-center justify-center text-text-muted text-sm h-32">
        No data
      </div>
    );
  }

  const max = Math.max(...bars.map((b) => b.value), 1);
  const computedHeight = height ?? bars.length * (BAR_HEIGHT + GAP) + GAP;

  return (
    <svg
      viewBox={`0 0 300 ${computedHeight}`}
      className="w-full"
      style={{ maxHeight: computedHeight }}
    >
      {bars.map((bar, i) => {
        const y = GAP + i * (BAR_HEIGHT + GAP);
        const barWidth = Math.max(2, ((300 - LABEL_WIDTH - VALUE_WIDTH - 16) * bar.value) / max);
        const isHovered = hoveredIdx === i;

        return (
          <g
            key={bar.label}
            onMouseEnter={() => setHoveredIdx(i)}
            onMouseLeave={() => setHoveredIdx(null)}
            style={{ cursor: "default" }}
          >
            {/* Label */}
            <text
              x={LABEL_WIDTH - 4}
              y={y + BAR_HEIGHT / 2 + 4}
              textAnchor="end"
              fill="#eeeeee"
              fontSize={14}
              fontWeight={600}
            >
              {bar.label}
            </text>

            {/* Bar */}
            <rect
              x={LABEL_WIDTH + 4}
              y={y + 2}
              width={barWidth}
              height={BAR_HEIGHT - 4}
              rx={4}
              fill={bar.color}
              opacity={isHovered ? 1 : 0.85}
              style={{ transition: "opacity 150ms" }}
            />

            {/* Value */}
            <text
              x={LABEL_WIDTH + barWidth + 12}
              y={y + BAR_HEIGHT / 2 + 4}
              fill={isHovered ? "#eeeeee" : "#a3a098"}
              fontSize={12}
              fontWeight={500}
            >
              {bar.value}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
