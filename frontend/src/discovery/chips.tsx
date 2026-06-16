// Filter chips (08) — rendered from response.cqs (INV-4: display == evaluated), each with a
// remove button that fires a one-tap re-issue (drop that filter, re-search; 06). Labels and
// connective grammar are i18n'd (templates per predicate shape) so Spanish word order works.

import i18n from "../lib/i18n";
import { caName, NEIGHBORHOOD_PREFIX } from "./communityAreas";
import type { CQS, FilterDef, Predicate, Registry } from "./types";

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
  cqs: CQS;
  registry: Registry;
  onRemove: (filterId: string) => void;
}

export function Chips({ cqs, registry, onRemove }: ChipsProps) {
  const defs = new Map(registry.filters.map((f) => [f.id, f]));
  const ids = Object.keys(cqs.filters).sort();
  if (ids.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {ids.map((id) => (
        <span
          key={id}
          className="inline-flex items-center gap-1.5 rounded-full border border-dark-border bg-dark-elevated px-3 py-1 text-xs text-text-primary"
        >
          {chipLabel(id, cqs.filters[id].predicate, defs.get(id))}
          <button
            type="button"
            onClick={() => onRemove(id)}
            aria-label={td("removeFilterAria", `Remove ${humanize(id)} filter`, { name: filterLabel(id, defs.get(id)) })}
            className="text-text-muted transition-colors hover:text-accent"
          >
            ×
          </button>
        </span>
      ))}
    </div>
  );
}
