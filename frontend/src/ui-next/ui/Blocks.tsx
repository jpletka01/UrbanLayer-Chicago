// The new UI's building blocks (decision Items 73–74, 76), drawn from SnowUI's look: blocks separated by fill
// (16px radius, 24px padding), stat tiles with one key figure, and SnowUI's status pills (pale fill, one
// colored word). Used only inside `.ui-next`.
import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { STROKE } from "../icons";

export function Block({
  title,
  icon: Icon,
  aside,
  children,
  className = "",
  labelledBy,
}: {
  title?: ReactNode;
  icon?: LucideIcon;
  /** Right of the title: a legend, a date, a tool. */
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
  labelledBy?: string;
}) {
  return (
    <section className={`flex min-w-0 flex-col gap-4 rounded-2xl bg-nx-block p-5 sm:p-6 ${className}`} aria-labelledby={labelledBy}>
      {(title || aside) && (
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          {title && (
            <h3 id={labelledBy} className="flex items-center gap-2 text-body font-semibold">
              {Icon && <Icon aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />}
              {title}
            </h3>
          )}
          {aside && <div className="text-caption nx-muted">{aside}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export type PillTone = "purple" | "green" | "blue" | "yellow" | "red" | "gray";

const PILL: Record<PillTone, string> = {
  purple: "bg-nx-pill-purple-bg text-nx-pill-purple",
  green: "bg-nx-pill-green-bg text-nx-pill-green",
  blue: "bg-nx-pill-blue-bg text-nx-pill-blue",
  yellow: "bg-nx-pill-yellow-bg text-nx-pill-yellow",
  red: "bg-nx-pill-red-bg text-nx-pill-red",
  gray: "bg-nx-ink/5 nx-muted",
};

/** A status, always a word (never color alone), inert: not a button. */
export function Pill({ tone = "gray", children, icon: Icon }: { tone?: PillTone; children: ReactNode; icon?: LucideIcon }) {
  return (
    <span data-pill={tone} className={`inline-flex max-w-full items-center gap-1 whitespace-nowrap rounded-lg px-2 py-px text-caption ${PILL[tone]}`}>
      {Icon && <Icon aria-hidden className="h-3 w-3 shrink-0" strokeWidth={2} />}
      <span className="truncate">{children}</span>
    </span>
  );
}

/** A horizontal share bar: the track is the allowed figure, the fill what is built. */
export function ShareBar({ share, emphasis = false, hatched = false, label }: {
  share: number | null;
  /** The deciding limit is black (white in dark); others are Sapphire. */
  emphasis?: boolean;
  /** Unknown built figure: drawn hatched (brief rule 5). */
  hatched?: boolean;
  label: string;
}) {
  const pct = share == null ? 0 : Math.max(0, Math.min(share, 1)) * 100;
  return (
    <div
      role="img"
      aria-label={label}
      className={`relative h-2 overflow-hidden rounded bg-nx-ink/5 ${hatched ? "bg-hatch" : ""}`}
    >
      {share != null && (
        <span
          className={`absolute inset-y-0 left-0 rounded ${emphasis ? "bg-nx-lot" : "bg-nx-chart-1"}`}
          style={{ width: `${pct}%` }}
        />
      )}
    </div>
  );
}

/** SnowUI's stat card (Item 74): one key figure on a pale fill (alternate `a` / `b`), its label above, a short
    note and at most one warning below. The tile row reflows from four to two to one. */
export function StatTile({ label, figure, unit, note, warning, state, tone = "a", checking = false, testId, visual, icon }: {
  label: ReactNode;
  /** An icon in a square at the card's start, like the Neighborhood tab's "Around the lot" cards (owner, Item 102). */
  icon?: ReactNode;
  figure?: ReactNode;
  /** A small graphic on the card's right (a score ring); with it, the figure line is left out when `figure` is unset. */
  visual?: ReactNode;
  unit?: string;
  note?: ReactNode;
  warning?: ReactNode;
  /** The confidence state, below the note (Estimate, Withheld, …). */
  state?: ReactNode;
  tone?: "a" | "b";
  /** The figure waits on a late part: a placeholder the figure's own height. */
  checking?: boolean;
  testId?: string;
}) {
  const iconBox = icon ? <span aria-hidden className={`grid shrink-0 place-items-center rounded-xl bg-white/60 text-nx-card-ink ${visual ? "h-8 w-8" : "h-10 w-10"}`}>{icon}</span> : null;
  if (visual) {
    return (
      // Icon and label on top, the words below, the visual on the right with the card's own padding around it.
      <li className={`flex min-w-0 items-center gap-3 rounded-2xl p-4 text-nx-card-ink ${tone === "a" ? "bg-nx-stat-a" : "bg-nx-stat-b"}`} data-testid={testId}>
        <span className="flex min-w-0 flex-1 flex-col gap-2">
          {iconBox ? <span className="flex items-center gap-2">{iconBox}<span className="min-w-0 text-caption font-semibold">{label}</span></span> : null}
          {!iconBox && <span className="text-caption font-semibold">{label}</span>}
          {figure != null && <span className="text-nx-figure tabular-nums">{figure}</span>}
          {note && <span className="text-caption nx-card-muted">{note}</span>}
          {state && <span className="nx-on-card inline-flex">{state}</span>}
        </span>
        {visual}
      </li>
    );
  }
  return (
    <li className={`flex min-w-0 flex-col gap-2 rounded-2xl p-4 text-nx-card-ink ${icon ? "" : "sm:p-6"} ${tone === "a" ? "bg-nx-stat-a" : "bg-nx-stat-b"}`} data-testid={testId}>
      {icon ? <span className="flex items-center gap-3">{iconBox}<span className="text-caption font-semibold">{label}</span></span> : <span className="text-caption font-semibold">{label}</span>}
      {checking ? (
        <span aria-hidden className="flex items-center text-nx-figure"><span className="block h-[0.8em] w-24 animate-pulse rounded bg-nx-card-ink/10" />&#8203;</span>
      ) : (
        <span className="flex flex-wrap items-baseline gap-x-1.5">
          <span className="text-nx-figure tabular-nums [overflow-wrap:anywhere]">{figure}</span>
          {unit && <span className="text-caption nx-card-muted">{unit}</span>}
        </span>
      )}
      {note && <span className="text-caption nx-card-muted">{note}</span>}
      {warning && <span className="text-caption font-medium">{warning}</span>}
      {state && <span className="nx-on-card mt-auto inline-flex">{state}</span>}
    </li>
  );
}
