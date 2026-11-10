// A share as a donut with its leading figure in the middle and a key beside it (owner's reference, Census Reporter's
// profiles: "Occupied 96%", "Renter occupied 70%"). Segments in the Coastal palette; one named image for screen
// readers. The key lists every segment with its share (or a note such as a count).
export interface DonutSegment { key: string; label: string; pct: number; color: string; low?: boolean;
  /** Beside the label in the key (a count). */
  note?: string }

export function Donut({ segments, lead, center, title, showTitle = true, size = 120, testId }: {
  segments: DonutSegment[];
  /** The segment named in the middle. */
  lead?: string;
  /** Or a figure of its own in the middle (311: the total). */
  center?: { label: string; value: string };
  title: string;
  /** False inside a card that already shows the title (it still names the image). */
  showTitle?: boolean;
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
      {showTitle && <figcaption className="text-caption font-semibold">{title}</figcaption>}
      <div className="flex flex-wrap items-center gap-4">
        <span role="img" aria-label={`${title}: ${segments.map((s) => `${s.label} ${Math.round(s.pct)}%`).join(", ")}`} className="relative inline-grid shrink-0 place-items-center" style={{ width: size, height: size }}>
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden className="absolute inset-0 -rotate-90">
            {segments.map((s, i) => {
              const len = (s.pct / total) * c;
              return <circle key={s.key} cx={size / 2} cy={size / 2} r={r} fill="none" stroke={s.color} strokeWidth={stroke} strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-starts[i]} />;
            })}
          </svg>
          <span aria-hidden className="relative flex max-w-[64%] flex-col items-center text-center leading-tight">
            <span className="text-[0.6875rem]">{center ? center.label : leadSeg.label}</span>
            <span className="text-[1.25rem] font-semibold tabular-nums">{center ? center.value : `${Math.round(leadSeg.pct)}%`}</span>
          </span>
        </span>
        <ul aria-hidden className="flex min-w-0 flex-1 flex-col gap-1 text-caption">
          {segments.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: s.color }} />
              <span className="min-w-0 flex-1 nx-muted">{s.label}</span>
              <span className="shrink-0 tabular-nums">{s.note ?? `${Math.round(s.pct)}%`}</span>
            </li>
          ))}
        </ul>
      </div>
    </figure>
  );
}
