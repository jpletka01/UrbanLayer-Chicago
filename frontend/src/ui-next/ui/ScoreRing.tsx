// A 0–100 score as a ring filled to its share, the number inside (owner's review of the Neighborhood tab, Item 102:
// "99 out of 100 within a circle, and the circle is as filled as its percentage"). Drawn in the stat cards' ink, so it
// reads on the pale card fills in both themes. One named image for screen readers.
export function ScoreRing({ value, max = 100, label, size = 76, testId }: {
  value: number;
  max?: number;
  /** The accessible name ("Walk score: 99 of 100"). */
  label: string;
  size?: number;
  testId?: string;
}) {
  const stroke = 7;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const share = Math.max(0, Math.min(1, value / max));
  return (
    <span role="img" aria-label={label} className="relative inline-grid shrink-0 place-items-center text-nx-card-ink" style={{ width: size, height: size }} data-testid={testId} data-share={share.toFixed(2)}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden className="absolute inset-0 -rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeOpacity={0.12} strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={`${c * share} ${c}`} />
      </svg>
      <span aria-hidden className="relative flex flex-col items-center leading-none">
        <span className="text-[1.375rem] font-semibold tabular-nums">{value}</span>
        <span className="mt-0.5 text-[0.6875rem] nx-card-muted">/{max}</span>
      </span>
    </span>
  );
}
