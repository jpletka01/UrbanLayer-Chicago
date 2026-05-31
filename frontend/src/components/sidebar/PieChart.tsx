import type { PieSlice } from "../../lib/analytics";

interface Props {
  slices: PieSlice[];
  size?: number;
  innerRadiusRatio?: number;
  totalOverride?: number;
}

function polarToCartesian(cx: number, cy: number, r: number, angle: number) {
  return {
    x: cx + r * Math.cos(angle),
    y: cy + r * Math.sin(angle),
  };
}

function describeArc(
  cx: number, cy: number,
  outerR: number, innerR: number,
  startAngle: number, endAngle: number,
): string {
  const outerStart = polarToCartesian(cx, cy, outerR, startAngle);
  const outerEnd = polarToCartesian(cx, cy, outerR, endAngle);
  const innerEnd = polarToCartesian(cx, cy, innerR, endAngle);
  const innerStart = polarToCartesian(cx, cy, innerR, startAngle);
  const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;

  return [
    `M ${outerStart.x} ${outerStart.y}`,
    `A ${outerR} ${outerR} 0 ${largeArc} 1 ${outerEnd.x} ${outerEnd.y}`,
    `L ${innerEnd.x} ${innerEnd.y}`,
    `A ${innerR} ${innerR} 0 ${largeArc} 0 ${innerStart.x} ${innerStart.y}`,
    "Z",
  ].join(" ");
}

export function PieChart({ slices, size = 140, innerRadiusRatio = 0.6, totalOverride }: Props) {
  if (slices.length === 0) return null;

  const sliceTotal = slices.reduce((s, sl) => s + sl.value, 0);
  if (sliceTotal === 0) return null;

  const total = totalOverride ?? sliceTotal;

  const cx = size / 2;
  const cy = size / 2;
  const outerR = size / 2 - 2;
  const innerR = outerR * innerRadiusRatio;

  const startAngle = -Math.PI / 2;

  let paths: React.ReactNode;

  if (slices.length === 1) {
    paths = (
      <>
        <circle cx={cx} cy={cy} r={outerR} fill={slices[0].color} />
        <circle cx={cx} cy={cy} r={innerR} fill="var(--color-dark-surface, #1a1a1a)" />
      </>
    );
  } else {
    let currentAngle = startAngle;
    paths = slices.map((slice, i) => {
      const sliceAngle = (slice.value / sliceTotal) * Math.PI * 2;
      const sa = currentAngle;
      const ea = currentAngle + sliceAngle;
      currentAngle = ea;
      return (
        <path
          key={i}
          d={describeArc(cx, cy, outerR, innerR, sa, ea)}
          fill={slice.color}
          className="transition-opacity duration-150 hover:opacity-80"
        />
      );
    });
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          {paths}
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <div className="text-lg font-semibold text-text-primary">{total.toLocaleString()}</div>
            <div className="text-[9px] text-text-muted uppercase tracking-wide">Total</div>
          </div>
        </div>
      </div>

      <div className="w-full grid grid-cols-2 gap-x-3 gap-y-1">
        {slices.slice(0, 8).map((slice) => {
          const pct = ((slice.value / total) * 100).toFixed(1);
          return (
            <div key={slice.label} className="flex items-center gap-1.5 min-w-0">
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: slice.color }}
              />
              <span className="text-[10px] text-text-secondary truncate">{formatLabel(slice.label)}</span>
              <span className="text-[10px] text-text-muted ml-auto shrink-0">{pct}%</span>
            </div>
          );
        })}
        {slices.length > 8 && (
          <div className="text-[10px] text-text-muted col-span-2">
            +{slices.length - 8} more
          </div>
        )}
      </div>
    </div>
  );
}

function formatLabel(label: string): string {
  return label.charAt(0) + label.slice(1).toLowerCase().replace(/_/g, " ");
}
