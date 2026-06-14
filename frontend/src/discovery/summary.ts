// Plain-English summary (08) — pure, rendered from response.cqs (INV-4), never from
// pre-send panel state. Deterministic: equal CQS → equal text.

import type { CQS, FilterDef, Predicate, Registry } from "./types";

function humanize(s: string): string {
  return s.replace(/_/g, " ");
}

function phrase(id: string, p: Predicate, def?: FilterDef): string {
  const label = humanize(id);
  switch (p.kind) {
    case "flag":
      return p.value ? label : `not ${label}`;
    case "enum":
      return `${label}: ${p.values.map(humanize).join(" or ")}`;
    case "region":
      return `${label}: ${p.regions.map(humanize).join(" or ")}`;
    case "range": {
      const unit = def?.unit ? ` ${def.unit}` : "";
      if (p.min != null && p.max != null) return `${label} ${p.min}–${p.max}${unit}`;
      if (p.min != null) return `${label} ≥ ${p.min}${unit}`;
      if (p.max != null) return `${label} ≤ ${p.max}${unit}`;
      return label;
    }
  }
}

/** Deterministic plain-English description of an evaluated CQS. */
export function summarize(cqs: CQS, registry: Registry): string {
  const defs = new Map(registry.filters.map((f) => [f.id, f]));
  const ids = Object.keys(cqs.filters).sort();
  const parts = ids.map((id) => phrase(id, cqs.filters[id].predicate, defs.get(id)));

  const base = parts.length ? `Parcels where ${parts.join("; ")}` : "All parcels";
  let scope = "";
  if (cqs.scope.mode === "viewport") scope = " in the current map view";
  else if (cqs.scope.mode === "region") scope = " in the selected area";

  const dir = cqs.sort.dir === "asc" ? "ascending" : "descending";
  return `${base}${scope}, sorted by ${humanize(cqs.sort.key)} (${dir}).`;
}
