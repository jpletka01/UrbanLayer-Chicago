// A 0–100 score as a ring filled to its share, the number inside (owner's review of the Neighborhood tab, Item 102).
// Second review: a thick ring with flat ends, so 99 visibly stops short of full (round caps closed the gap and read as
// 100), on a darker track; just the number inside, the "of 100" said beside it. Drawn in the stat cards' ink, so it
// reads on the pale card fills in both themes. One named image for screen readers.
export function ScoreRing({ value, max = 100, label, size = 56, suffix, inkClass = "text-nx-card-ink", testId }: {
  value: number;
  max?: number;
  /** The accessible name ("Walk score: 99 of 100"). */
  label: string;
  size?: number;
  /** After the number ("%" for a school's rates). */
  suffix?: string;
  /** The ring's ink: the stat cards' dark ink by default, the page's ink on a page-colored card. */
  inkClass?: string;
  testId?: string;
}) {
  const stroke = Math.round(size * 0.17);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const share = Math.max(0, Math.min(1, value / max));
  return (
    <span role="img" aria-label={label} className={`relative inline-grid shrink-0 place-items-center ${inkClass}`} style={{ width: size, height: size }} data-testid={testId} data-share={share.toFixed(2)}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden className="absolute inset-0 -rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeOpacity={0.18} strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="butt"
          strokeDasharray={`${c * share} ${c}`} />
      </svg>
      <span aria-hidden className={`relative font-semibold leading-none tabular-nums ${size < 56 ? "text-[0.8125rem]" : "text-[1.0625rem]"}`}>{value}{suffix}</span>
    </span>
  );
}
