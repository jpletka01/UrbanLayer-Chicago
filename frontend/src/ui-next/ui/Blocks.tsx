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
