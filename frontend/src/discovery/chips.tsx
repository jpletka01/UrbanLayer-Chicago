// Filter chips (08) — rendered from response.cqs (INV-4: display == evaluated), each with a
// remove button that fires a one-tap re-issue (drop that filter, re-search; 06).

import { caName, NEIGHBORHOOD_PREFIX } from "./communityAreas";
import type { CQS, FilterDef, Predicate, Registry } from "./types";

function humanize(s: string): string {
  return s.replace(/_/g, " ");
}

function regionLabel(ref: string): string {
  // "neighborhood:24" → "West Town"; "ward:1"/"radius:..." → human-ish
  if (ref.startsWith(NEIGHBORHOOD_PREFIX)) return caName(ref);
  const [kind, rest] = ref.split(":", 2);
  return rest ? `${humanize(kind)} ${rest}` : humanize(ref);
}

export function chipLabel(id: string, p: Predicate, def?: FilterDef): string {
  const label = def?.label ?? humanize(id);
  switch (p.kind) {
    case "flag":
      return p.value ? label : `no ${label}`;
    case "enum":
      return `${label}: ${p.values.map(humanize).join(" / ")}`;
    case "region":
      return `${label}: ${p.regions.map(regionLabel).join(" / ")}`;
    case "range": {
      const unit = def?.unit ? ` ${def.unit}` : "";
      if (p.min != null && p.max != null) return `${label} ${p.min}–${p.max}${unit}`;
      if (p.min != null) return `${label} ≥ ${p.min}${unit}`;
      if (p.max != null) return `${label} ≤ ${p.max}${unit}`;
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
            aria-label={`Remove ${humanize(id)} filter`}
            className="text-text-muted transition-colors hover:text-accent"
          >
            ×
          </button>
        </span>
      ))}
    </div>
  );
}
