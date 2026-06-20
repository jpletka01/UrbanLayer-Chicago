// Registry-driven filter panel (08). Renders one control per FilterDef, grouped by
// category. Emits a Predicate (or null to clear) per filter id; the page holds the
// PanelState. Region filters: only `neighborhood` is wired to data today (community-area
// multiselect); `ward`/`radius` are shown disabled until the index populates them.

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Chip } from "../components/ui/Chip";
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
  const { t } = useTranslation("pages");
  const byCategory = useMemo(() => {
    const map = new Map<FilterCategory, FilterDef[]>();
    for (const f of registry.filters) {
      (map.get(f.category) ?? map.set(f.category, []).get(f.category)!).push(f);
    }
    return map;
  }, [registry]);

  // PR8 IA: categories collapse by default (refinement drawer, not the front door). A
  // category auto-expands when it holds an active filter — so a recipe's set fields are
  // visible — and the user can toggle any category open/closed.
  const [openCats, setOpenCats] = useState<Set<FilterCategory>>(new Set());
  const toggle = (cat: FilterCategory) =>
    setOpenCats((prev) => {
      const next = new Set(prev);
      next.has(cat) ? next.delete(cat) : next.add(cat);
      return next;
    });

  return (
    <div className="space-y-3">
      {CATEGORY_ORDER.map((cat) => {
        const defs = byCategory.get(cat);
        if (!defs?.length) return null;
        const activeCount = defs.filter((d) => state[d.id]).length;
        const expanded = activeCount > 0 || openCats.has(cat);
        return (
          <div key={cat}>
            <button
              type="button"
              onClick={() => toggle(cat)}
              aria-expanded={expanded}
              className="flex w-full items-center justify-between text-overline uppercase text-text-muted transition-colors hover:text-text-secondary"
            >
              <span>
                {t(`discovery.category.${cat}`, CATEGORY_LABELS[cat])}
                {activeCount > 0 && <span className="ml-1 text-accent">({activeCount})</span>}
              </span>
              <span aria-hidden>{expanded ? "−" : "+"}</span>
            </button>
            {expanded && (
              <div className="mt-2 space-y-3">
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
            )}
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
  const { t } = useTranslation("pages");
  const name = t(`discovery.filter.${def.id}`, def.label ?? humanize(def.id));
  const unit = def.unit ? t(`discovery.unit.${def.unit}`, def.unit) : null;
  // Visible group label (a <span>, not a <label> — pill/preset groups have no single
  // form control to associate; their accessible name comes from role+aria-label).
  const labelNode = (
    <span className="mb-1 block text-caption text-text-secondary">
      {name}
      {unit ? <span className="text-text-muted"> ({unit})</span> : null}
    </span>
  );

  // PR4: a filter whose index field isn't populated yet reads "coming" — never a live
  // control that would silently return 0. (Pre-index, populatedFields is empty → all of
  // these, so the whole panel is honestly dormant.)
  if (!populated) {
    return (
      <div className="opacity-50">
        {labelNode}
        <p className="text-micro text-text-muted">{t("discovery.comingSoon")}</p>
      </div>
    );
  }

  if (def.kind === "flag") {
    const v = value?.kind === "flag" ? value.value : null;
    const opts: Array<[string, boolean | null]> = [
      [t("discovery.flagAny"), null],
      [t("discovery.flagYes"), true],
      [t("discovery.flagNo"), false],
    ];
    return (
      <div>
        {labelNode}
        <div role="group" aria-label={name} className="flex gap-1.5">
          {opts.map(([txt, val]) => (
            <Chip
              key={txt}
              as="button"
              size="md"
              selected={v === val}
              interactive
              aria-pressed={v === val}
              onClick={() => onChange(def.id, val === null ? null : { kind: "flag", value: val })}
            >
              {txt}
            </Chip>
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
    const enumLabel = (v: string) => t(`discovery.enum.${def.id}.${v}`, def.enumLabels?.[v] ?? humanize(v));
    return (
      <div>
        {labelNode}
        <div role="group" aria-label={name} className="flex flex-wrap gap-1.5">
          {(def.enumValues ?? []).map((v) => (
            <Chip
              key={v}
              as="button"
              size="md"
              selected={selected.includes(v)}
              interactive
              aria-pressed={selected.includes(v)}
              onClick={() => toggle(v)}
            >
              {enumLabel(v)}
            </Chip>
          ))}
        </div>
      </div>
    );
  }

  if (def.kind === "range") {
    const r = value?.kind === "range" ? value : undefined;

    // Preset-backed ranges (transit/recency/percentile/upside) → a radiogroup of chips
    // (PR2 metadata). A continuous slider control for the remaining ranges is not built —
    // those keep labeled min/max inputs (see below); slider a11y is deferred with it.
    if (def.range?.presets?.length) {
      const anyChecked = !r || (r.min == null && r.max == null);
      const isChecked = (p: { min?: number | null; max?: number | null }) =>
        !!r && r.min === (p.min ?? undefined) && r.max === (p.max ?? undefined);
      return (
        <div>
          {labelNode}
          <div role="radiogroup" aria-label={name} className="flex flex-wrap gap-1.5">
            <Chip
              as="button"
              size="md"
              role="radio"
              selected={anyChecked}
              interactive
              aria-checked={anyChecked}
              onClick={() => onChange(def.id, null)}
            >
              {t("discovery.flagAny")}
            </Chip>
            {def.range.presets.map((p) => (
              <Chip
                key={p.label}
                as="button"
                size="md"
                role="radio"
                selected={isChecked(p)}
                interactive
                aria-checked={isChecked(p)}
                onClick={() =>
                  onChange(def.id, { kind: "range", min: p.min ?? undefined, max: p.max ?? undefined })
                }
              >
                {t(`discovery.preset.${p.label}`, p.label)}
              </Chip>
            ))}
          </div>
        </div>
      );
    }

    const set = (min: number | undefined, max: number | undefined) =>
      onChange(def.id, min == null && max == null ? null : { kind: "range", min, max });
    const parse = (s: string) => (s === "" ? undefined : Number(s));
    const dom = def.range?.domain;
    const inputCls =
      "w-full rounded-lg border border-dark-border bg-dark-elevated px-2 py-1 text-caption text-text-primary focus:border-accent focus:outline-none";
    return (
      <div>
        {labelNode}
        <div className="flex items-center gap-2">
          <input
            type="number"
            aria-label={t("discovery.minAria", { name })}
            placeholder={t("discovery.minPlaceholder")}
            min={dom?.[0]}
            max={dom?.[1]}
            step={def.range?.step}
            value={r?.min ?? ""}
            onChange={(e) => set(parse(e.target.value), r?.max)}
            className={inputCls}
          />
          <span aria-hidden className="text-text-muted">–</span>
          <input
            type="number"
            aria-label={t("discovery.maxAria", { name })}
            placeholder={t("discovery.maxPlaceholder")}
            min={dom?.[0]}
            max={dom?.[1]}
            step={def.range?.step}
            value={r?.max ?? ""}
            onChange={(e) => set(r?.min, parse(e.target.value))}
            className={inputCls}
          />
        </div>
      </div>
    );
  }

  // region — only `neighborhood` has a built control (a real labeled multi-select).
  if (def.id !== "neighborhood") {
    return (
      <div className="opacity-50">
        {labelNode}
        <p className="text-micro text-text-muted">{t("discovery.notAvailable")}</p>
      </div>
    );
  }
  const selected = value?.kind === "region" ? value.regions : [];
  const onSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const refs = Array.from(e.target.selectedOptions, (o) => NEIGHBORHOOD_PREFIX + o.value);
    onChange(def.id, refs.length ? { kind: "region", regions: refs } : null);
  };
  const selectId = `disc-${def.id}`;
  return (
    <div>
      <label htmlFor={selectId} className="mb-1 block text-caption text-text-secondary">
        {name}
      </label>
      <select
        id={selectId}
        multiple
        value={selected.map((r) => r.replace(NEIGHBORHOOD_PREFIX, ""))}
        onChange={onSelect}
        className="h-28 w-full rounded-lg border border-dark-border bg-dark-elevated px-2 py-1 text-caption text-text-primary focus:border-accent focus:outline-none"
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
