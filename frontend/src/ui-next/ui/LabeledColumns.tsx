// Shares as columns with the value printed on top and the label underneath (owner's reference, Census Reporter's
// profiles). For a breakdown read at a glance, where hover-to-read (ColumnChart) would hide the point. Sapphire
// columns; a `low` value (margin of error at least 10% of it) carries a dagger, explained once per section.
export interface LabeledColumn { key: string; label: string; pct: number; low?: boolean }

export function LabeledColumns({ columns, title, heightClass = "h-24", testId }: {
  columns: LabeledColumn[];
  title: string;
  heightClass?: string;
  testId?: string;
}) {
  const max = Math.max(1, ...columns.map((c) => c.pct));
  return (
    <figure className="flex min-w-0 flex-col gap-2" data-testid={testId}>
      <figcaption className="text-caption font-semibold">{title}</figcaption>
      <ul className="flex items-end gap-1.5" role="list" aria-label={title}>
        {columns.map((c) => (
          <li key={c.key} className="flex min-w-0 flex-1 flex-col items-center gap-1" aria-label={`${c.label}: ${Math.round(c.pct)}%`}>
            <span aria-hidden className={`flex w-full flex-col justify-end ${heightClass}`}>
              <span className="text-center text-[0.6875rem] tabular-nums">{Math.round(c.pct)}%{c.low ? <sup>†</sup> : null}</span>
              <span className="mt-0.5 block w-full rounded-t-sm bg-nx-chart-1" style={{ height: `${Math.max(1, (c.pct / max) * 78)}%` }} />
            </span>
            <span aria-hidden className="w-full text-center text-[0.6875rem] leading-tight nx-muted [overflow-wrap:anywhere]">{c.label}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
