// Dashboard bands for the Property Profile page. "Card = data source" stays
// retired — a card here is a MODULE (one question, fixed composition), so the
// page reads as a handful of contained widgets on the canvas instead of an
// unbounded texture of rules. Interiors stay de-carded (quiet SubSections).
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

/** Top-level dashboard band: title + optional takeaway + right-side action.
    The takeaway is parcel-specific computed insight ("the so-what"), NOT
    definitional copy — definitions live in tooltips (2026-07-07 rule). */
export function ProfileModule({ id, title, takeaway, action, children, open, onToggle, sources }: {
  id?: string;
  title: string;
  takeaway?: string | null;
  /** Right-aligned quiet action (the module's single "Ask" affordance). */
  action?: ReactNode;
  children: ReactNode;
  /** Collapsible (redesign, decision Item 51): closed, the module is ONE line, its title and the takeaway
      as a summary; open, the full detail. Without onToggle the module is always open (old behavior). */
  open?: boolean;
  onToggle?: () => void;
  /** The section's Sources button, shown in the open module's header row. */
  sources?: ReactNode;
}) {
  if (onToggle) {
    return (
      <section id={id} data-module-open={open ? "true" : "false"} className="scroll-mt-28 rounded-bento border border-dark-border bg-dark-surface shadow-card mt-4 first:mt-0">
        <button
          type="button"
          aria-expanded={!!open}
          aria-controls={id ? `${id}-body` : undefined}
          onClick={onToggle}
          className="flex w-full items-center gap-4 rounded-bento px-5 py-4 text-left cursor-pointer transition-colors hover:bg-dark-hover/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent md:px-7"
        >
          <span className="min-w-0 flex-1">
            <h3 className="text-subtitle text-text-primary">{title}</h3>
            {takeaway && <p className={`mt-0.5 text-caption text-text-secondary ${open ? "" : "truncate"}`}>{takeaway}</p>}
          </span>
          <span aria-hidden className={`shrink-0 text-text-muted transition-transform ${open ? "rotate-180" : ""}`}>▾</span>
        </button>
        {open && (
          <div id={id ? `${id}-body` : undefined} className="px-5 pb-6 md:px-7 md:pb-7">
            {(action || sources) && (
              <div className="mb-5 flex flex-wrap items-center justify-end gap-3">
                {sources}
                {action}
              </div>
            )}
            {children}
          </div>
        )}
      </section>
    );
  }
  return (
    <section id={id} className="scroll-mt-28 rounded-bento border border-dark-border bg-dark-surface shadow-card p-5 md:p-7 mt-6 first:mt-0">
      <div className="flex items-start justify-between gap-4 mb-5">
        <div className="min-w-0">
          <h3 className="text-subtitle text-text-primary">{title}</h3>
          {takeaway && <p className="text-body text-text-secondary mt-1.5 max-w-3xl leading-relaxed">{takeaway}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      {children}
    </section>
  );
}

/** Sub-block inside a module: quiet header (icon + title + meta), no box. */
export function SubSection({ id, icon, title, meta, children, className = "" }: {
  id?: string;
  icon?: ReactNode;
  title: string;
  meta?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={`scroll-mt-28 min-w-0 ${className}`}>
      <div className="flex items-center gap-2 mb-3">
        {icon && <span className="shrink-0 text-text-muted">{icon}</span>}
        <h4 className="text-title text-text-primary">{title}</h4>
        {meta != null && <span className="ml-auto text-caption text-text-muted text-right">{meta}</span>}
      </div>
      {children}
    </section>
  );
}

/** THE one disclosure idiom on the page: top-N always visible, one button
    appends the tail in place. Replaces the old per-card chevron accordions —
    nothing on the page hides behind a closed-by-default toggle anymore. */
export function ShowMore<T>({ items, limit, render, labelKey }: {
  items: T[];
  limit: number;
  render: (visible: T[]) => ReactNode;
  /** i18n key (pages ns) taking {{count}}; defaults to the shared "and N more". */
  labelKey?: string;
}) {
  const { t } = useTranslation("pages");
  const [all, setAll] = useState(false);
  const visible = all ? items : items.slice(0, limit);
  return (
    <>
      {render(visible)}
      {items.length > limit && !all && (
        <button
          type="button"
          onClick={() => setAll(true)}
          className="mt-2 text-caption text-text-muted hover:text-text-secondary transition-colors"
        >
          {t(labelKey ?? "scorecard.showMore", { count: items.length - limit })}
        </button>
      )}
    </>
  );
}
