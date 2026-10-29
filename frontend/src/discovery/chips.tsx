// Filter chips (08, reworked in the Phase 0 redesign). Labels and connective grammar are
// i18n'd (templates per predicate shape) so Spanish word order works. Removing or restoring a
// chip edits the draft only; "Update results" is what searches.

import i18n from "../lib/i18n";
import type { ReactNode } from "react";
import { Chip } from "../components/ui/Chip";
import { FILTER_POPOVER_ANCHOR, HEURISTIC_FILTERS } from "./filterMenu";
import { caName, NEIGHBORHOOD_PREFIX } from "./communityAreas";
import type { ChipItem } from "./draftModel";
import type { FilterDef, Predicate, Registry } from "./types";

function td(key: string, fallback: string, opts?: Record<string, unknown>): string {
  return i18n.t(`discovery.${key}`, { ns: "pages", defaultValue: fallback, ...opts });
}

function humanize(s: string): string {
  return s.replace(/_/g, " ");
}

function filterLabel(id: string, def?: FilterDef): string {
  return td(`filter.${id}`, def?.label ?? humanize(id));
}

function unitLabel(def?: FilterDef): string {
  return def?.unit ? ` ${td(`unit.${def.unit}`, def.unit)}` : "";
}

function enumValue(id: string, v: string, def?: FilterDef): string {
  return td(`enum.${id}.${v}`, def?.enumLabels?.[v] ?? humanize(v));
}

function regionLabel(ref: string): string {
  // "neighborhood:24" → "West Town"; "ward:1"/"radius:..." → human-ish
  if (ref.startsWith(NEIGHBORHOOD_PREFIX)) return caName(ref);
  const [kind, rest] = ref.split(":", 2);
  return rest ? `${humanize(kind)} ${rest}` : humanize(ref);
}

export function chipLabel(id: string, p: Predicate, def?: FilterDef): string {
  const label = filterLabel(id, def);
  switch (p.kind) {
    case "flag":
      return p.value ? label : td("chipNo", `no ${label}`, { label });
    case "enum":
      return td("labelValues", `${label}: {{values}}`, {
        label,
        values: p.values.map((v) => enumValue(id, v, def)).join(td("valueJoinSlash", " / ")),
      });
    case "region":
      return td("labelValues", `${label}: {{values}}`, {
        label,
        values: p.regions.map(regionLabel).join(td("valueJoinSlash", " / ")),
      });
    case "range": {
      const unit = unitLabel(def);
      if (p.min != null && p.max != null)
        return td("rangeBetween", `${label} ${p.min}–${p.max}${unit}`, { label, min: p.min, max: p.max, unit });
      if (p.min != null) return td("rangeMin", `${label} ≥ ${p.min}${unit}`, { label, min: p.min, unit });
      if (p.max != null) return td("rangeMax", `${label} ≤ ${p.max}${unit}`, { label, max: p.max, unit });
      return label;
    }
  }
}

interface ChipsProps {
  /** One entry per filter in the DRAFT (plus evaluated filters the draft dropped). */
  items: ChipItem[];
  registry: Registry;
  onRemove: (filterId: string) => void;
  onRestore: (filterId: string) => void;
  /** Open the filter's editor. When given, the chip's label is a button for it. */
  onEdit?: (filterId: string) => void;
  /** Rendered after the chips, in the same wrapping row (the "+ Add filter" button). */
  children?: ReactNode;
}

// The strip is a control surface: it renders from the draft so chips stay clickable while a
// refresh runs. Evaluated facts (summary, count, rows) still come from response.cqs (INV-4);
// a chip that differs from the evaluated query says so (dashed outline) and a removed one stays
// visible, struck through, until the removal is applied.
export function Chips({ items, registry, onRemove, onRestore, onEdit, children }: ChipsProps) {
  const defs = new Map(registry.filters.map((f) => [f.id, f]));
  if (items.length === 0 && !children) return null;

  return (
    <div className="flex flex-wrap gap-2" data-testid="discovery-chips">
      {items.map(({ id, predicate, state }) => {
        const name = filterLabel(id, defs.get(id));
        const label = chipLabel(id, predicate, defs.get(id));
        if (state === "removed") {
          return (
            <Chip
              key={id}
              as="button"
              size="md"
              interactive
              onClick={() => onRestore(id)}
              className="line-through decoration-text-muted"
              title={td("restoreFilterTitle", "Removed, not applied yet. Click to restore.")}
            >
              <span className="sr-only">{td("restoreFilterAria", `Restore ${name} filter`, { name })}</span>
              <span aria-hidden>{label}</span>
            </Chip>
          );
        }
        const pending = state !== "applied";
        return (
          <Chip
            key={id}
            size="md"
            removable
            onRemove={() => onRemove(id)}
            removeLabel={td("removeFilterAria", `Remove ${humanize(id)} filter`, { name })}
            className={pending ? "border-dashed border-accent/60" : ""}
            title={
              pending
                ? td("chipPendingTitle", "Not applied yet. Press Update results.")
                : HEURISTIC_FILTERS.has(id)
                  ? td("addFilter.heuristicTip", "A rough score we calculate, not a measured value.")
                  : undefined
            }
          >
            {onEdit ? (
              <button
                type="button"
                {...{ [FILTER_POPOVER_ANCHOR]: "" }}
                aria-haspopup="dialog"
                aria-label={td("editFilterAria", `Edit ${label}`, { label })}
                onClick={() => onEdit(id)}
                className="text-left"
              >
                {label}
              </button>
            ) : (
              label
            )}
            {pending && <span className="sr-only"> ({td("chipPending", "not applied yet")})</span>}
          </Chip>
        );
      })}
      {children}
    </div>
  );
}
