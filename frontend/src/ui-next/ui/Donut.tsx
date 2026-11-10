// A share as a donut with its leading figure in the middle and a key beside it (owner's reference, Census Reporter's
// profiles: "Occupied 96%", "Renter occupied 70%"). Segments in the Coastal palette; one named image for screen
// readers. A `low` segment (margin of error at least 10% of the value) carries a dagger, explained once per section.
export interface DonutSegment { key: string; label: string; pct: number; color: string; low?: boolean }

export function Donut({ segments, lead, title, size = 132, testId }: {
  segments: DonutSegment[];
  /** The segment named in the middle. */
  lead: string;
  title: string;
  size?: number;
  testId?: string;
}) {
  const stroke = Math.round(size * 0.16);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const total = segments.reduce((s, x) => s + x.pct, 0) || 1;
  const leadSeg = segments.find((s) => s.key === lead) ?? segments[0];
  // Each segment starts where the ones before it end.
  const starts = segments.map((_, i) => segments.slice(0, i).reduce((a, x) => a + (x.pct / total) * c, 0));
  return (
    <figure className="flex flex-col gap-2" data-testid={testId}>
      <figcaption className="text-caption font-semibold">{title}</figcaption>
      <div className="flex flex-wrap items-center gap-4">
        <span role="img" aria-label={`${title}: ${segments.map((s) => `${s.label} ${Math.round(s.pct)}%`).join(", ")}`} className="relative inline-grid shrink-0 place-items-center" style={{ width: size, height: size }}>
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden className="absolute inset-0 -rotate-90">
            {segments.map((s, i) => {
              const len = (s.pct / total) * c;
              return <circle key={s.key} cx={size / 2} cy={size / 2} r={r} fill="none" stroke={s.color} strokeWidth={stroke} strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-starts[i]} />;
            })}
          </svg>
          <span aria-hidden className="relative flex max-w-[70%] flex-col items-center text-center leading-tight">
            <span className="text-[0.6875rem]">{leadSeg.label}</span>
            <span className="text-[1.375rem] font-semibold tabular-nums">{Math.round(leadSeg.pct)}%{leadSeg.low ? <sup>†</sup> : null}</span>
          </span>
        </span>
        <ul aria-hidden className="flex flex-col gap-1 text-caption nx-muted">
          {segments.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: s.color }} />{s.label}</li>
          ))}
        </ul>
      </div>
    </figure>
  );
}
