import { useState, useMemo, useRef, useCallback } from "react";

interface DataPoint {
  bucket: string;
  value: number;
}

interface Series {
  label: string;
  values: DataPoint[];
  color: string;
}

interface Props {
  series: Series[];
  height?: number;
  yLabel?: string;
  formatValue?: (v: number) => string;
  formatBucket?: (b: string) => string;
}

const MARGIN = { top: 16, right: 16, bottom: 32, left: 56 };

function niceMax(max: number): number {
  if (max <= 0) return 10;
  const magnitude = Math.pow(10, Math.floor(Math.log10(max)));
  const normalized = max / magnitude;
  if (normalized <= 1) return magnitude;
  if (normalized <= 2) return 2 * magnitude;
  if (normalized <= 5) return 5 * magnitude;
  return 10 * magnitude;
}

function defaultFormatBucket(b: string): string {
  if (b.includes("T")) {
    const d = new Date(b);
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:00`;
  }
  const d = new Date(b + "T00:00:00");
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export function TimeSeriesChart({
  series,
  height = 240,
  yLabel,
  formatValue = (v) => v.toLocaleString(),
  formatBucket = defaultFormatBucket,
}: Props) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const allBuckets = useMemo(() => {
    const set = new Set<string>();
    for (const s of series) for (const p of s.values) set.add(p.bucket);
    return Array.from(set).sort();
  }, [series]);

  const yMax = useMemo(() => {
    let max = 0;
    for (const s of series) for (const p of s.values) max = Math.max(max, p.value);
    return niceMax(max);
  }, [series]);

  const chartWidth = 600;
  const w = chartWidth - MARGIN.left - MARGIN.right;
  const h = height - MARGIN.top - MARGIN.bottom;

  const xScale = useCallback(
    (i: number) => MARGIN.left + (allBuckets.length > 1 ? (i / (allBuckets.length - 1)) * w : w / 2),
    [allBuckets.length, w],
  );
  const yScale = useCallback(
    (v: number) => MARGIN.top + h - (v / yMax) * h,
    [h, yMax],
  );

  const gridLines = useMemo(() => {
    const lines: number[] = [];
    const step = yMax / 4;
    for (let i = 0; i <= 4; i++) lines.push(step * i);
    return lines;
  }, [yMax]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!svgRef.current || allBuckets.length === 0) return;
      const rect = svgRef.current.getBoundingClientRect();
      const svgX = ((e.clientX - rect.left) / rect.width) * chartWidth;
      const relX = svgX - MARGIN.left;
      if (relX < 0 || relX > w) { setHoverIndex(null); return; }
      const idx = allBuckets.length > 1
        ? Math.round((relX / w) * (allBuckets.length - 1))
        : 0;
      setHoverIndex(Math.max(0, Math.min(idx, allBuckets.length - 1)));
    },
    [allBuckets.length, w],
  );

  if (allBuckets.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-text-muted text-body"
        style={{ height }}
      >
        No data yet
      </div>
    );
  }

  const labelInterval = Math.max(1, Math.floor(allBuckets.length / 6));

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${chartWidth} ${height}`}
        className="w-full"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverIndex(null)}
      >
        <defs>
          {series.map((s, i) => (
            <linearGradient
              key={i}
              id={`area-grad-${i}`}
              x1="0" y1="0" x2="0" y2="1"
            >
              <stop offset="0%" stopColor={s.color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={s.color} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>

        {/* Grid lines */}
        {gridLines.map((v, i) => (
          <g key={i}>
            <line
              x1={MARGIN.left} y1={yScale(v)}
              x2={MARGIN.left + w} y2={yScale(v)}
              stroke="#2a2a2a" strokeWidth={1}
            />
            <text
              x={MARGIN.left - 8} y={yScale(v) + 4}
              textAnchor="end" fill="#6b6962" fontSize={10}
            >
              {formatValue(v)}
            </text>
          </g>
        ))}

        {/* Y label */}
        {yLabel && (
          <text
            x={12} y={MARGIN.top + h / 2}
            textAnchor="middle" fill="#6b6962" fontSize={10}
            transform={`rotate(-90, 12, ${MARGIN.top + h / 2})`}
          >
            {yLabel}
          </text>
        )}

        {/* X labels */}
        {allBuckets.map((b, i) =>
          i % labelInterval === 0 ? (
            <text
              key={i}
              x={xScale(i)} y={height - 8}
              textAnchor="middle" fill="#6b6962" fontSize={10}
            >
              {formatBucket(b)}
            </text>
          ) : null,
        )}

        {/* Area fills */}
        {series.map((s, si) => {
          const bucketMap = new Map(s.values.map((p) => [p.bucket, p.value]));
          const points = allBuckets.map((b, i) => ({
            x: xScale(i),
            y: yScale(bucketMap.get(b) ?? 0),
          }));
          const areaPath =
            `M${points[0].x},${yScale(0)} ` +
            points.map((p) => `L${p.x},${p.y}`).join(" ") +
            ` L${points[points.length - 1].x},${yScale(0)} Z`;
          return (
            <path
              key={`area-${si}`}
              d={areaPath}
              fill={`url(#area-grad-${si})`}
            />
          );
        })}

        {/* Lines */}
        {series.map((s, si) => {
          const bucketMap = new Map(s.values.map((p) => [p.bucket, p.value]));
          const points = allBuckets.map((b, i) => ({
            x: xScale(i),
            y: yScale(bucketMap.get(b) ?? 0),
          }));
          const linePath = points
            .map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`)
            .join(" ");
          return (
            <path
              key={`line-${si}`}
              d={linePath}
              fill="none"
              stroke={s.color}
              strokeWidth={2}
              strokeLinejoin="round"
            />
          );
        })}

        {/* Hover crosshair */}
        {hoverIndex !== null && (
          <>
            <line
              x1={xScale(hoverIndex)} y1={MARGIN.top}
              x2={xScale(hoverIndex)} y2={MARGIN.top + h}
              stroke="#a3a098" strokeWidth={1} strokeDasharray="3,3"
            />
            {series.map((s, si) => {
              const bucketMap = new Map(s.values.map((p) => [p.bucket, p.value]));
              const val = bucketMap.get(allBuckets[hoverIndex]) ?? 0;
              return (
                <circle
                  key={si}
                  cx={xScale(hoverIndex)}
                  cy={yScale(val)}
                  r={4}
                  fill={s.color}
                  stroke="#0d0d0d"
                  strokeWidth={2}
                />
              );
            })}
          </>
        )}
      </svg>

      {/* Tooltip */}
      {hoverIndex !== null && (
        <div
          className="absolute bg-dark-border-strong border border-dark-border rounded-lg px-3 py-2 text-caption pointer-events-none shadow-lg"
          style={{
            left: `${(xScale(hoverIndex) / chartWidth) * 100}%`,
            top: 0,
            transform: "translateX(-50%)",
          }}
        >
          <div className="text-text-secondary mb-1">
            {formatBucket(allBuckets[hoverIndex])}
          </div>
          {series.map((s, i) => {
            const bucketMap = new Map(s.values.map((p) => [p.bucket, p.value]));
            return (
              <div key={i} className="flex items-center gap-2">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: s.color }}
                />
                <span className="text-text-muted">{s.label}:</span>
                <span className="text-text-primary font-medium">
                  {formatValue(bucketMap.get(allBuckets[hoverIndex]) ?? 0)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
