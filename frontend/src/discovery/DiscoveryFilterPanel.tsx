// Registry-driven filter panel (08). Renders one control per FilterDef, grouped by
// category. Emits a Predicate (or null to clear) per filter id; the page holds the
// PanelState. Region filters: only `neighborhood` is wired to data today (community-area
// multiselect); `ward`/`radius` are shown disabled until the index populates them.

import { useMemo } from "react";
import {
  COMMUNITY_AREAS,
  NEIGHBORHOOD_PREFIX,
  SORTED_CAS,
} from "./communityAreas";
import { isPopulated } from "./coverage";
import type { FilterCategory, FilterDef, PanelState, Predicate, Registry } from "./types";

const CATEGORY_ORDER: FilterCategory[] = [
  "location", "property_use", "zoning_dev", "incentives", "financial", "condition_risk",
];

const CATEGORY_LABELS: Record<FilterCategory, string> = {
  location: "Location",
  property_use: "Property & use",
  zoning_dev: "Zoning & development",
  incentives: "Incentives",
  financial: "Financial",
  condition_risk: "Condition & risk",
};

function humanize(s: string): string {
  return s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

interface PanelProps {
  registry: Registry;
  state: PanelState;
  onChange: (filterId: string, predicate: Predicate | null) => void;
}

export function DiscoveryFilterPanel({ registry, state, onChange }: PanelProps) {
  const byCategory = useMemo(() => {
    const map = new Map<FilterCategory, FilterDef[]>();
    for (const f of registry.filters) {
      (map.get(f.category) ?? map.set(f.category, []).get(f.category)!).push(f);
    }
    return map;
  }, [registry]);

  return (
    <div className="space-y-5">
      {CATEGORY_ORDER.map((cat) => {
        const defs = byCategory.get(cat);
        if (!defs?.length) return null;
        return (
          <div key={cat}>
            <h3 className="mb-2 text-[10px] uppercase tracking-wider text-text-muted">
              {CATEGORY_LABELS[cat]}
            </h3>
            <div className="space-y-3">
              {defs.map((def) => (
                <Control
                  key={def.id}
                  def={def}
                  value={state[def.id]}
                  populated={isPopulated(registry, def.id)}
                  onChange={onChange}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Control({
  def,
  value,
  populated,
  onChange,
}: {
  def: FilterDef;
  value: Predicate | undefined;
  populated: boolean;
  onChange: (id: string, p: Predicate | null) => void;
}) {
  const label = (
    <label className="mb-1 block text-xs text-text-secondary">
      {def.label ?? humanize(def.id)}
      {def.unit ? <span className="text-text-muted"> ({def.unit})</span> : null}
    </label>
  );

  // PR4: a filter whose index field isn't populated yet reads "coming" — never a live
  // control that would silently return 0. (Pre-index, populatedFields is empty → all of
  // these, so the whole panel is honestly dormant.)
  if (!populated) {
    return (
      <div className="opacity-50">
        {label}
        <p className="text-[11px] text-text-muted">Coming with the next data update</p>
      </div>
    );
  }

  if (def.kind === "flag") {
    const v = value?.kind === "flag" ? value.value : null;
    const opts: Array<[string, boolean | null]> = [["Any", null], ["Yes", true], ["No", false]];
    return (
      <div>
        {label}
        <div className="flex gap-1.5">
          {opts.map(([txt, val]) => (
            <button
              key={txt}
              type="button"
              onClick={() => onChange(def.id, val === null ? null : { kind: "flag", value: val })}
              className={`rounded-md border px-2.5 py-1 text-[11px] transition-colors ${
                v === val
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-dark-border text-text-secondary hover:border-text-muted"
              }`}
            >
              {txt}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (def.kind === "enum") {
    const selected = value?.kind === "enum" ? value.values : [];
    const toggle = (v: string) => {
      const next = selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v];
      onChange(def.id, next.length ? { kind: "enum", values: next } : null);
    };
    return (
      <div>
        {label}
        <div className="flex flex-wrap gap-1.5">
          {(def.enumValues ?? []).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => toggle(v)}
              className={`rounded-md border px-2 py-0.5 text-[11px] transition-colors ${
                selected.includes(v)
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-dark-border text-text-secondary hover:border-text-muted"
              }`}
            >
              {humanize(v)}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (def.kind === "range") {
    const cur = value?.kind === "range" ? value : { min: undefined, max: undefined };
    const set = (min: number | undefined, max: number | undefined) =>
      onChange(def.id, min == null && max == null ? null : { kind: "range", min, max });
    const parse = (s: string) => (s === "" ? undefined : Number(s));
    return (
      <div>
        {label}
        <div className="flex items-center gap-2">
          <input
            type="number"
            placeholder="min"
            value={cur.min ?? ""}
            onChange={(e) => set(parse(e.target.value), cur.max)}
            className="w-full rounded-md border border-dark-border bg-dark-elevated px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
          />
          <span className="text-text-muted">–</span>
          <input
            type="number"
            placeholder="max"
            value={cur.max ?? ""}
            onChange={(e) => set(cur.min, parse(e.target.value))}
            className="w-full rounded-md border border-dark-border bg-dark-elevated px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
          />
        </div>
      </div>
    );
  }

  // region
  if (def.id !== "neighborhood") {
    return (
      <div className="opacity-50">
        {label}
        <p className="text-[11px] text-text-muted">Not available yet</p>
      </div>
    );
  }
  const selected = value?.kind === "region" ? value.regions : [];
  const onSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const refs = Array.from(e.target.selectedOptions, (o) => NEIGHBORHOOD_PREFIX + o.value);
    onChange(def.id, refs.length ? { kind: "region", regions: refs } : null);
  };
  return (
    <div>
      {label}
      <select
        multiple
        value={selected.map((r) => r.replace(NEIGHBORHOOD_PREFIX, ""))}
        onChange={onSelect}
        className="h-28 w-full rounded-md border border-dark-border bg-dark-elevated px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
      >
        {SORTED_CAS.map((ca) => (
          <option key={ca.id} value={ca.id}>
            {COMMUNITY_AREAS[ca.id]}
          </option>
        ))}
      </select>
    </div>
  );
}
