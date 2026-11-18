// Small pieces /admin shares, built on the site's own blocks (`ui/Blocks`): a row of stat tiles that reflows by its
// own width, an icon button whose name is its tooltip, an empty state, and the tone → pill mapping.
import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { STROKE } from "../icons";
import type { Tone } from "./adminModel";

/** Stat tiles in the Profile's container-query grid (four, two or one across by the block's own width). */
export function Tiles({ children, testId }: { children: ReactNode; testId?: string }) {
  return (
    <div className="nx-cq">
      <ul className="nx-tiles" data-testid={testId}>{children}</ul>
    </div>
  );
}

/** An icon-only button: the name is its accessible name and a tooltip on hover and keyboard focus. */
export function IconAction({ label, icon: Icon, onClick, href, tone = "plain", disabled = false, testId, pressed }: {
  label: string;
  icon: LucideIcon;
  onClick?: () => void;
  /** A link instead of a button (opens in a new tab). */
  href?: string;
  tone?: "plain" | "solid";
  disabled?: boolean;
  testId?: string;
  pressed?: boolean;
}) {
  const cls = `grid h-8 w-8 place-items-center rounded-lg touch-icon disabled:opacity-40 ${tone === "solid" ? "bg-nx-ink text-nx-on-ink hover:opacity-90" : "hover:bg-nx-ink/5"}`;
  const body = <Icon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />;
  return (
    <span className="group relative inline-flex">
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer" aria-label={`${label} (opens in a new tab)`} className={cls} data-testid={testId}>{body}</a>
      ) : (
        <button type="button" aria-label={label} onClick={onClick} disabled={disabled} className={cls} data-testid={testId} aria-pressed={pressed}>{body}</button>
      )}
      <span role="tooltip" aria-hidden
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded-md bg-nx-ink px-2 py-1 text-[11px] text-nx-on-ink group-hover:block group-focus-within:block">
        {label}
      </span>
    </span>
  );
}

/** Nothing to show yet: an icon and a few words, never a big empty chart frame. */
export function Empty({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <p className="flex items-center gap-2 py-2 text-caption nx-muted">
      <Icon aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />{children}
    </p>
  );
}

/** A square icon on a tinted ground, the lead of an attention row or a list item. */
export function IconBadge({ icon: Icon, tone = "gray" }: { icon: LucideIcon; tone?: Tone }) {
  const bg = { green: "bg-nx-pill-green-bg text-nx-pill-green", yellow: "bg-nx-pill-yellow-bg text-nx-pill-yellow", red: "bg-nx-pill-red-bg text-nx-pill-red", gray: "bg-nx-ink/5 text-nx-ink" }[tone];
  return <span aria-hidden className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${bg}`}><Icon className="h-[18px] w-[18px]" strokeWidth={STROKE} /></span>;
}
