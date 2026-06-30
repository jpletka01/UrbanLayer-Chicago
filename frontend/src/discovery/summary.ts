// Plain-language summary (08) — pure-ish, rendered from response.cqs (INV-4), never from
// pre-send panel state. Deterministic for a given language: equal CQS → equal text. The
// connective grammar is i18n'd (templates per predicate shape) so Spanish word order works.

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

function regionName(ref: string): string {
  return ref.startsWith(NEIGHBORHOOD_PREFIX) ? caName(ref) : humanize(ref);
}

function phrase(id: string, p: Predicate, def?: FilterDef): string {
  const label = filterLabel(id, def);
  switch (p.kind) {
    case "flag":
      return p.value ? label : td("sumNot", `not ${label}`, { label });
    case "enum":
      return td("labelValues", `${label}: {{values}}`, {
        label,
        values: p.values.map((v) => enumValue(id, v, def)).join(td("valueJoinOr", " or ")),
      });
    case "region":
      return td("labelValues", `${label}: {{values}}`, {
        label,
        values: p.regions.map(regionName).join(td("valueJoinOr", " or ")),
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

/**
 * A chat-handoff question for the current result set (#6 Discovery→chat seam).
 * Names the area (so the chat router scopes the community area from the text) and
 * the filter criteria (so the answer is specific to what the user searched),
 * anchored to "these properties". UNGROUNDED — answered by the chat's native area
 * retrieval, never a structured payload. Citywide (no region filter) is an
 * accepted generic floor; the area-filtered case is where the seam earns its keep.
 */
export function seamPrompt(cqs: CQS, registry: Registry): string {
  const defs = new Map(registry.filters.map((f) => [f.id, f]));
  const ids = Object.keys(cqs.filters).sort();
  const regions: string[] = [];
  const criteria: string[] = [];
  for (const id of ids) {
    const pred = cqs.filters[id].predicate;
    if (pred.kind === "region") regions.push(...pred.regions.map(regionName));
    else criteria.push(phrase(id, pred, defs.get(id)));
  }
  const crit = criteria.length ? criteria.join(", ") : td("seamCrit", "properties");
  const area = regions.length ? regions.join(td("valueJoinOr", " or ")) : null;
  return area
    ? td(
        "seamPromptArea",
        `I'm researching ${crit} in ${area}. What's driving development there, and what should I know before pursuing these properties?`,
        { crit, area },
      )
    : td(
        "seamPromptCity",
        `I'm researching ${crit} across Chicago. What should I know before pursuing these properties?`,
        { crit },
      );
}

/** Deterministic plain-language description of an evaluated CQS (in the active language). */
export function summarize(cqs: CQS, registry: Registry): string {
  const defs = new Map(registry.filters.map((f) => [f.id, f]));
  const ids = Object.keys(cqs.filters).sort();
  const parts = ids.map((id) => phrase(id, cqs.filters[id].predicate, defs.get(id)));

  const base = parts.length
    ? td("sumParcelsWhere", `Parcels where ${parts.join("; ")}`, { parts: parts.join("; ") })
    : td("sumAllParcels", "All parcels");
  let scope = "";
  if (cqs.scope.mode === "viewport") scope = td("sumScopeViewport", " in the current map view");
  else if (cqs.scope.mode === "region") scope = td("sumScopeRegion", " in the selected area");

  const dir = cqs.sort.dir === "asc" ? td("sumAsc", "ascending") : td("sumDesc", "descending");
  const key = td(`sort.${cqs.sort.key}`, humanize(cqs.sort.key));
  return td("sumFull", `${base}${scope}, sorted by ${key} (${dir}).`, { base, scope, key, dir });
}
