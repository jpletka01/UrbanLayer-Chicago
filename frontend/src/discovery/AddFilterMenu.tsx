// The "+ Add filter" menu and the in-place filter editor (redesign Phase 3a).
//
// One popover with two views:
//   menu   a search box and the filters in three groups: essentials, more, and (collapsed)
//          "coming soon" for filters the index has no data for
//   edit   one filter's control, reused unchanged from the filter panel, with Reset and Done
//
// Opened by "+ Add filter" (menu) or by clicking a chip (edit that filter). It only edits the
// DRAFT, like every other control: nothing is requested until Update results (Phase 0). A
// popover on desktop, a bottom sheet below `md`. Escape or a click outside closes it and
// focus goes back to where it was.

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Chip } from "../components/ui/Chip";
import { Control } from "./FilterControl";
import { FILTER_POPOVER_ANCHOR, HEURISTIC_FILTERS, menuGroups } from "./filterMenu";
import type { FilterDef, FilterId, Predicate, Registry } from "./types";

export type FilterPopoverView = { kind: "menu" } | { kind: "edit"; id: FilterId } | null;

interface Props {
  registry: Registry;
  view: Exclude<FilterPopoverView, null>;
  /** The filters the draft would send (panel plus carried text filters), for values and marks. */
  values: Record<FilterId, Predicate>;
  onChange: (id: FilterId, predicate: Predicate | null) => void;
  onView: (view: FilterPopoverView) => void;
  onClose: () => void;
}

function humanize(s: string): string {
  return s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function AddFilterMenu({ registry, view, values, onChange, onView, onClose }: Props) {
  const { t } = useTranslation("pages");
  const dialogRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [soonOpen, setSoonOpen] = useState(false);

  const nameOf = (def: FilterDef) => t(`discovery.filter.${def.id}`, def.label ?? humanize(def.id));

  // Focus goes in on open and back to where it came from on close.
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    return () => {
      if (before && document.contains(before)) before.focus();
    };
  }, []);
  const editingId = view.kind === "edit" ? view.id : "";
  useEffect(() => {
    dialogRef.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
  }, [view.kind, editingId]);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const target = e.target as Element | null;
      if (!target || dialogRef.current?.contains(target) || target.closest(`[${FILTER_POPOVER_ANCHOR}]`)) return;
      onClose();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [onClose]);

  const groups = useMemo(() => menuGroups(registry, query, nameOf), [registry, query, t]); // eslint-disable-line react-hooks/exhaustive-deps
  const editing = view.kind === "edit" ? registry.filters.find((f) => f.id === view.id) : undefined;

  const choose = (def: FilterDef) => {
    // A flag has nothing to pick but a side: adding it means "Yes", and the editor lets it flip.
    if (def.kind === "flag" && !values[def.id]) onChange(def.id, { kind: "flag", value: true });
    onView({ kind: "edit", id: def.id });
  };

  const row = (def: FilterDef) => (
    <li key={def.id}>
      <button
        type="button"
        onClick={() => choose(def)}
        className="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-body text-text-secondary transition-colors hover:bg-dark-elevated hover:text-text-primary"
      >
        <span className="flex items-center gap-2">
          {nameOf(def)}
          {HEURISTIC_FILTERS.has(def.id) && (
            <Chip size="sm" title={t("discovery.addFilter.heuristicTip")}>{t("discovery.addFilter.heuristic")}</Chip>
          )}
        </span>
        {values[def.id] && (
          <span className="text-micro text-accent">
            <span aria-hidden>✓</span>
            <span className="sr-only">{t("discovery.addFilter.inSearch")}</span>
          </span>
        )}
      </button>
    </li>
  );

  const group = (label: string, defs: FilterDef[]) =>
    defs.length > 0 && (
      <section className="mt-3 first:mt-0">
        <h3 className="px-3 pb-1 text-overline uppercase text-text-muted">{label}</h3>
        <ul>{defs.map(row)}</ul>
      </section>
    );

  return (
    <>
      <div className="fixed inset-0 z-30 bg-black/50 md:hidden" aria-hidden onClick={onClose} />
      <div
        ref={dialogRef}
        role="dialog"
        aria-label={t(view.kind === "menu" ? "discovery.addFilter.menuAria" : "discovery.addFilter.editAria")}
        data-testid="discovery-filter-popover"
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.stopPropagation();
            onClose();
          }
        }}
        className="fixed inset-x-0 bottom-0 z-40 max-h-[80vh] overflow-y-auto rounded-t-xl border-t border-dark-border bg-dark-surface p-3 shadow-modal md:absolute md:inset-x-auto md:bottom-auto md:left-4 md:top-full md:mt-1 md:max-h-[70vh] md:w-[24rem] md:max-w-[calc(100%-2rem)] md:rounded-xl md:border"
      >
        {view.kind === "menu" ? (
          <>
            <input
              type="search"
              data-autofocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("discovery.addFilter.search")}
              aria-label={t("discovery.addFilter.search")}
              className="mb-3 w-full rounded-lg border border-dark-border bg-dark-elevated px-3 py-2 text-body text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
            />
            {group(t("discovery.addFilter.essentials"), groups.essentials)}
            {group(t("discovery.addFilter.more"), groups.more)}
            {groups.soon.length > 0 && (
              <section className="mt-3">
                <button
                  type="button"
                  aria-expanded={soonOpen}
                  onClick={() => setSoonOpen((o) => !o)}
                  className="flex w-full items-center justify-between rounded-lg px-3 py-1.5 text-overline uppercase text-text-muted transition-colors hover:bg-dark-elevated"
                >
                  {t("discovery.addFilter.soon", { count: groups.soon.length })}
                  <span aria-hidden>{soonOpen ? "−" : "+"}</span>
                </button>
                {soonOpen && (
                  <>
                    <p className="px-3 pb-1 text-micro text-text-muted">{t("discovery.addFilter.soonNote")}</p>
                    <ul>
                      {groups.soon.map((def) => (
                        <li key={def.id} className="px-3 py-1 text-caption text-text-muted">{nameOf(def)}</li>
                      ))}
                    </ul>
                  </>
                )}
              </section>
            )}
            {groups.essentials.length + groups.more.length + groups.soon.length === 0 && (
              <p className="px-3 py-2 text-caption text-text-muted">{t("discovery.addFilter.noMatch")}</p>
            )}
          </>
        ) : editing ? (
          <>
            <div className="mb-3 flex items-center justify-between gap-2">
              <button
                type="button"
                data-autofocus
                onClick={() => onView({ kind: "menu" })}
                className="text-caption text-text-secondary transition-colors hover:text-accent"
              >
                <span aria-hidden>← </span>{t("discovery.addFilter.back")}
              </button>
              {HEURISTIC_FILTERS.has(editing.id) && (
                <Chip size="sm" title={t("discovery.addFilter.heuristicTip")}>{t("discovery.addFilter.heuristic")}</Chip>
              )}
            </div>
            {HEURISTIC_FILTERS.has(editing.id) && (
              <p className="mb-3 text-micro text-text-muted">{t("discovery.addFilter.heuristicTip")}</p>
            )}
            <Control def={editing} value={values[editing.id]} populated onChange={onChange} />
            <div className="mt-4 flex items-center justify-between gap-2">
              <button
                type="button"
                disabled={!values[editing.id]}
                onClick={() => onChange(editing.id, null)}
                className="text-caption text-text-muted transition-colors hover:text-accent disabled:opacity-40 disabled:hover:text-text-muted"
              >
                {t("discovery.addFilter.reset")}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg bg-action px-3 py-1.5 text-caption font-medium text-text-on-accent transition-colors hover:bg-action-hover"
              >
                {t("discovery.addFilter.done")}
              </button>
            </div>
          </>
        ) : null}
      </div>
    </>
  );
}
