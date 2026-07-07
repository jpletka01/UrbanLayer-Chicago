// De-carded dashboard bands for the Property Profile page (2026-07-07 redesign).
// The page is ONE canvas: modules are full-width sections separated by hairline
// rules, not boxed cards — "card = data source" is retired. Borders and radius
// are reserved for genuinely interactive elements (buttons, inputs, chips).
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

/** Top-level dashboard band: title + subtitle + optional right-side action. */
export function ProfileModule({ id, title, subtitle, action, children }: {
  id?: string;
  title: string;
  subtitle?: string;
  /** Right-aligned quiet action (the module's single "Ask" affordance). */
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-28 border-t border-dark-border pt-8 mt-10 first:border-t-0 first:mt-0 first:pt-0">
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h3 className="text-subtitle text-text-primary">{title}</h3>
          {subtitle && <p className="text-caption text-text-muted mt-0.5">{subtitle}</p>}
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
