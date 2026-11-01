// "Sources" for a Profile section, and the page's "Sources & coverage" sheet (redesign plan §4/§6a L3,
// decision Item 51). Provenance gathered in one place instead of threaded through every block: each
// figure's five fields (who published it, how old, coverage, precision, method) from the backend's own
// `provenance` map, plus, on the page sheet, the dated source list and the "what this page doesn't
// cover" notes. A dialog, not a nested disclosure: it opens over the page from a button in the section.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Provenance } from "../../lib/api";
import { confidenceStateFor, sourceBullets } from "../../lib/confidence";
import { ConfidenceState } from "../ui/ConfidenceState";
import { Modal } from "../ui/Modal";

export type SourceScope = "build" | "economics" | "market" | "record" | "area" | "all";

/** Which fact ids each section's Sources list shows (by id prefix). */
export function factsFor(scope: SourceScope, provenance: Record<string, Provenance>): string[] {
  const ids = Object.keys(provenance).sort();
  const is = (id: string, prefixes: string[]) => prefixes.some((p) => id === p || id.startsWith(`${p}.`));
  switch (scope) {
    case "build": return ids.filter((id) => is(id, ["zoning", "overlay", "code", "capacity", "upcoming", "pending", "incentive.aro"]));
    case "economics": return ids.filter((id) => is(id, ["property", "incentive"]) && !is(id, ["property.comps", "property.sales", "property.311", "property.violations", "incentive.aro"]));
    case "market": return ids.filter((id) => is(id, ["property.comps", "property.sales"]));
    case "record": return ids.filter((id) => is(id, ["property.311", "property.violations", "regulatory"]));
    case "area": return ids.filter((id) => is(id, ["area", "neighborhood", "geo"]));
    default: return ids;
  }
}

export function SourcesButton({
  scope,
  provenance,
  title,
  extra,
  label,
}: {
  scope: SourceScope;
  provenance: Record<string, Provenance> | null | undefined;
  title: string;
  /** Page sheet only: data dates and coverage notes, rendered above the per-figure list. */
  extra?: React.ReactNode;
  label?: string;
}) {
  const { t } = useTranslation("pages");
  const { t: tc } = useTranslation("common");
  const [open, setOpen] = useState(false);
  const facts = useMemo(() => (provenance ? factsFor(scope, provenance) : []), [scope, provenance]);
  if (!provenance || (facts.length === 0 && !extra)) return null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid={`sources-${scope}`}
        className="inline-flex items-center gap-1 rounded text-caption text-text-muted cursor-pointer hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <span aria-hidden>ⓘ</span> {label ?? t("scorecard.sources.button")}
      </button>
      {open && (
        <Modal onClose={() => setOpen(false)} title={title} size="lg">
          <div className="max-h-[70vh] overflow-y-auto pr-1 text-caption text-text-secondary" data-testid="sources-sheet">
            {extra && <div className="mb-4 space-y-3">{extra}</div>}
            <ul className="space-y-3">
              {facts.map((id) => {
                const entry = provenance[id];
                const state = confidenceStateFor(entry);
                return (
                  <li key={id} className="border-t border-dark-border pt-2.5 first:border-t-0 first:pt-0">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="font-medium text-text-primary">{entry.label}</span>
                      {state && <ConfidenceState kind={state.kind} low={state.low} />}
                    </div>
                    {entry.source && <p className="mt-0.5">{entry.source}</p>}
                    <ul className="mt-1 space-y-0.5 text-text-muted">
                      {sourceBullets(entry, tc).map((b, i) => <li key={i}>{b}</li>)}
                    </ul>
                    {entry.url && (
                      <a href={entry.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block text-link hover:underline">
                        {t("scorecard.sources.open")} ↗
                      </a>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        </Modal>
      )}
    </>
  );
}
