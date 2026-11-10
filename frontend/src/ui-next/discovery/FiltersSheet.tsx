// The filters sheet (brief "Discovery"; decision Item 104): only filters that have data, each with how many lots it
// knows, presets plus a custom value, an include-unknowns choice and, for a range, its spread across the city with
// the unknowns as their own hatched bar; a live "Show N lots" count from the server. Transit is one control.
// Edits stay in the sheet until "Show N lots"; nothing here evaluates (the count is a server search).
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { LoaderCircle, RotateCcw, X } from "lucide-react";
import { isPopulated } from "../../discovery/coverage";
import { HIDE_UNUSUAL } from "../../discovery/draftModel";
import { runSearch } from "../../discovery/searchClient";
import type { FilterDef, PanelState, Predicate, Registry, SpatialScope } from "../../discovery/types";
import { STROKE } from "../icons";
import { useDistribution, type Distribution } from "./discoveryData";
import { TRANSIT_WALKS } from "./discoveryModel";

/** Filters set elsewhere on the page (the search box, the ring) or switched by their own control. */
const ELSEWHERE = new Set(["neighborhood", "ward", "radius", HIDE_UNUSUAL]);

function numberFmt(lang: string) {
  return new Intl.NumberFormat(lang.startsWith("es") ? "es-MX" : "en-US", { maximumFractionDigits: 2 });
}

export function FiltersSheet({
  open, onOpenChange, registry, panel, scope, onApply,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  registry: Registry;
  panel: PanelState;
  scope: SpatialScope | null;
  onApply: (panel: PanelState) => void;
}) {
  const { t, i18n } = useTranslation("next");
  const { t: tp } = useTranslation("pages");
  // The sheet starts from the page's panel each time it opens (the page remounts it: `key`).
  const [draft, setDraft] = useState<PanelState>(panel);
  const defs = useMemo(
    () => registry.filters.filter((f) => !ELSEWHERE.has(f.id) && f.kind !== "region" && isPopulated(registry, f.id)),
    [registry],
  );
  const groups = useMemo(() => {
    const order = ["location", "property_use", "financial", "incentives", "zoning", "risk", "other"];
    const by = new Map<string, FilterDef[]>();
    for (const f of defs) by.set(f.category, [...(by.get(f.category) ?? []), f]);
    return [...by.entries()].sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]));
  }, [defs]);
  const set = (id: string, p: Predicate | null) => setDraft((d) => {
    const next = { ...d };
    if (p) next[id] = p as PanelState[string]; else delete next[id];
    return next;
  });

  // The live count: a server search of the sheet's draft (one row), debounced.
  const key = JSON.stringify(draft);
  const [answer, setAnswer] = useState<{ key: string; n: number | null } | null>(null);
  const count = { n: answer?.n ?? null, loading: answer?.key !== key };
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      runSearch({ panelState: draft, scope, limit: 1 }, registry, controller.signal)
        .then((r) => { if (!controller.signal.aborted) setAnswer({ key, n: r?.result.total ?? null }); })
        .catch(() => { if (!controller.signal.aborted) setAnswer({ key, n: null }); });
    }, 300);
    return () => { window.clearTimeout(timer); controller.abort(); };
    // key stands for draft.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, open, registry, scope]);

  const fmt = numberFmt(i18n.language);
  const chosen = defs.filter((f) => draft[f.id]).length;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <div className="ui-next">
          <Dialog.Overlay className="fixed inset-0 z-[65] bg-black/30" />
          <Dialog.Content
            className="fixed inset-x-0 bottom-0 z-[66] flex max-h-[88dvh] flex-col rounded-t-3xl bg-nx-page text-body text-nx-ink shadow-[0_8px_32px_rgb(0_0_0/0.2)] focus:outline-none md:inset-x-auto md:inset-y-0 md:right-0 md:max-h-none md:w-[28rem] md:rounded-none"
            data-testid="filters-sheet"
          >
            <div className="flex items-center gap-2 border-b border-nx-ink/10 px-5 py-4">
              <Dialog.Title className="flex-1 text-body font-semibold">{t("discovery.filters.title")}</Dialog.Title>
              <Dialog.Description className="sr-only">{t("discovery.filters.hint")}</Dialog.Description>
              {chosen > 0 && (
                <button type="button" onClick={() => setDraft({})} className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-caption hover:bg-nx-ink/5 touch-target">
                  <RotateCcw aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{t("discovery.filters.clear")}
                </button>
              )}
              <Dialog.Close className="grid h-8 w-8 place-items-center rounded-lg hover:bg-nx-ink/5 touch-target" aria-label={t("discovery.filters.close")}>
                <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
              </Dialog.Close>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {groups.map(([cat, list]) => (
                <section key={cat} className="mb-6">
                  <h3 className="mb-3 text-caption font-semibold nx-muted">{t(`discovery.filters.group.${cat}`, { defaultValue: cat })}</h3>
                  <div className="flex flex-col gap-5">
                    {list.map((def) => (
                      <FilterRow key={def.id} def={def} value={(draft[def.id] as Predicate | undefined) ?? null} onChange={(p) => set(def.id, p)}
                        label={tp(`discovery.filter.${def.id}`, { defaultValue: def.label ?? def.id })} />
                    ))}
                  </div>
                </section>
              ))}
              <p className="text-caption nx-muted">{t("discovery.filters.soon")}</p>
            </div>
            <div className="border-t border-nx-ink/10 px-5 py-4 pb-[calc(1rem+env(safe-area-inset-bottom))]">
              <button
                type="button"
                onClick={() => { onApply(draft); onOpenChange(false); }}
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-nx-primary font-medium text-nx-primary-fg"
                data-testid="filters-show"
              >
                {count.loading && <LoaderCircle aria-hidden className="h-4 w-4 animate-spin" strokeWidth={STROKE} />}
                {count.n == null ? t("discovery.filters.showUnknown") : t("discovery.filters.show", { count: count.n, n: fmt.format(count.n) })}
              </button>
            </div>
          </Dialog.Content>
        </div>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function FilterRow({ def, value, onChange, label }: { def: FilterDef; value: Predicate | null; onChange: (p: Predicate | null) => void; label: string }) {
  const { t, i18n } = useTranslation("next");
  const { t: tp } = useTranslation("pages");
  const dist = useDistribution(def.id);
  const fmt = numberFmt(i18n.language);
  const known = dist ? dist.total - dist.unknown : null;
  const share = dist && dist.total ? Math.round((100 * (dist.total - dist.unknown)) / dist.total) : null;
  const includeUnknown = value && "includeUnknown" in value ? !!(value as { includeUnknown?: boolean }).includeUnknown : false;
  const withUnknown = (p: Predicate, inc: boolean): Predicate => (inc && p.kind !== "region" ? { ...p, includeUnknown: true } : stripUnknown(p));
  const pill = (on: boolean) => `rounded-full px-3 py-1.5 text-caption touch-target ${on ? "bg-nx-ink text-nx-on-ink" : "bg-nx-ink/5 hover:bg-nx-ink/10"}`;

  return (
    <div className="flex flex-col gap-2" data-filter={def.id}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-medium">{label}</span>
        <span className="shrink-0 text-caption nx-muted">
          {share == null ? "" : t("discovery.filters.coverage", { share, known: fmt.format(known ?? 0) })}
        </span>
      </div>

      {def.id === "transit_proximity" ? (
        <div className="flex flex-wrap gap-2" role="group" aria-label={label}>
          {TRANSIT_WALKS.map((w) => {
            const on = value?.kind === "range" && value.max === w.mi;
            return (
              <button key={w.minutes} type="button" aria-pressed={on} className={pill(on)}
                onClick={() => onChange(on ? null : { kind: "range", max: w.mi })}>
                {t("discovery.filters.walk", { minutes: w.minutes })}
              </button>
            );
          })}
          <span className="basis-full text-caption nx-muted">{t("discovery.filters.transitNote")}</span>
        </div>
      ) : def.kind === "flag" ? (
        <div className="flex flex-wrap gap-2" role="group" aria-label={label}>
          {([["any", null], ["yes", true], ["no", false]] as const).map(([k, v]) => {
            const on = v === null ? !value : value?.kind === "flag" && value.value === v;
            return (
              <button key={k} type="button" aria-pressed={on} className={pill(on)}
                onClick={() => onChange(v === null ? null : { kind: "flag", value: v })}>
                {t(`discovery.filters.${k}`)}
              </button>
            );
          })}
        </div>
      ) : def.kind === "enum" ? (
        <div className="flex flex-wrap gap-2" role="group" aria-label={label}>
          {(def.enumValues ?? []).map((v) => {
            const values = value?.kind === "enum" ? value.values : [];
            const on = values.includes(v);
            return (
              <button key={v} type="button" aria-pressed={on} className={pill(on)}
                onClick={() => {
                  const next = on ? values.filter((x) => x !== v) : [...values, v];
                  onChange(next.length ? { kind: "enum", values: next } : null);
                }}>
                {tp(`discovery.enum.${def.id}.${v}`, { defaultValue: def.enumLabels?.[v] ?? v.replace(/_/g, " ") })}
                {dist?.values?.[v] != null && <span className="ml-1 opacity-70">{fmt.format(dist.values[v])}</span>}
              </button>
            );
          })}
        </div>
      ) : def.kind === "range" && def.range ? (
        <RangeRow def={def} value={value?.kind === "range" ? value : null} dist={dist ?? null} label={label}
          onChange={(p) => onChange(p ? withUnknown(p, includeUnknown) : null)} />
      ) : null}

      {value && def.kind !== "region" && dist && dist.unknown > 0 && (
        <label className="flex items-center gap-2 text-caption">
          <input type="checkbox" checked={includeUnknown} onChange={(e) => onChange(withUnknown(value, e.target.checked))} className="h-4 w-4 accent-current" />
          {t("discovery.filters.includeUnknown", { n: fmt.format(dist.unknown) })}
        </label>
      )}
    </div>
  );
}

function stripUnknown(p: Predicate): Predicate {
  const { includeUnknown: _drop, ...rest } = p as Predicate & { includeUnknown?: boolean };
  void _drop;
  return rest as Predicate;
}

function RangeRow({ def, value, dist, label, onChange }: {
  def: FilterDef; value: { kind: "range"; min?: number; max?: number } | null; dist: Distribution | null; label: string;
  onChange: (p: Predicate | null) => void;
}) {
  const { t, i18n } = useTranslation("next");
  const { t: tp } = useTranslation("pages");
  const fmt = numberFmt(i18n.language);
  const range = def.range!;
  const presets = range.presets ?? [];
  const pill = (on: boolean) => `rounded-full px-3 py-1.5 text-caption touch-target ${on ? "bg-nx-ink text-nx-on-ink" : "bg-nx-ink/5 hover:bg-nx-ink/10"}`;
  const num = (s: string) => (s.trim() === "" ? undefined : Number(s));
  return (
    <div className="flex flex-col gap-2">
      {dist?.bins && <Histogram dist={dist} value={value} label={label} />}
      {presets.length > 0 && (
        <div className="flex flex-wrap gap-2" role="group" aria-label={t("discovery.filters.presets", { label })}>
          {presets.map((p) => {
            const on = !!value && (value.min ?? null) === (p.min ?? null) && (value.max ?? null) === (p.max ?? null);
            return (
              <button key={p.label} type="button" aria-pressed={on} className={pill(on)}
                onClick={() => onChange(on ? null : { kind: "range", ...(p.min != null ? { min: p.min } : {}), ...(p.max != null ? { max: p.max } : {}) })}>
                {tp(`discovery.preset.${p.label}`, { defaultValue: p.label })}
              </button>
            );
          })}
        </div>
      )}
      <div className="flex items-center gap-2 text-caption">
        {range.boundMode !== "max" && (
          <label className="flex items-center gap-1.5">
            <span className="nx-muted">{t("discovery.filters.min")}</span>
            <input type="number" inputMode="decimal" step={range.step} value={value?.min ?? ""} placeholder={fmt.format(range.domain[0])}
              onChange={(e) => { const min = num(e.target.value); const max = value?.max; onChange(min == null && max == null ? null : { kind: "range", ...(min != null ? { min } : {}), ...(max != null ? { max } : {}) }); }}
              className="h-9 w-24 rounded-lg bg-nx-ink/5 px-2 tabular-nums" aria-label={t("discovery.filters.minOf", { label })} />
          </label>
        )}
        {range.boundMode !== "min" && (
          <label className="flex items-center gap-1.5">
            <span className="nx-muted">{t("discovery.filters.max")}</span>
            <input type="number" inputMode="decimal" step={range.step} value={value?.max ?? ""} placeholder={fmt.format(range.domain[1])}
              onChange={(e) => { const max = num(e.target.value); const min = value?.min; onChange(min == null && max == null ? null : { kind: "range", ...(min != null ? { min } : {}), ...(max != null ? { max } : {}) }); }}
              className="h-9 w-24 rounded-lg bg-nx-ink/5 px-2 tabular-nums" aria-label={t("discovery.filters.maxOf", { label })} />
          </label>
        )}
        {def.unit && <span className="nx-muted">{t(`discovery.filters.unit.${def.unit}`, { defaultValue: def.unit })}</span>}
      </div>
    </div>
  );
}

/** The filter's spread across the city's lots: 16 bars over its domain, the chosen range dark, the unknowns hatched. */
export function Histogram({ dist, value, label }: { dist: Distribution; value: { min?: number; max?: number } | null; label: string }) {
  const { t, i18n } = useTranslation("next");
  const bins = dist.bins ?? [];
  const max = Math.max(1, dist.unknown, ...bins.map((b) => b.n));
  const fmt = numberFmt(i18n.language);
  const inRange = (b: { min: number; max: number }) => !value || ((value.min == null || b.max > value.min) && (value.max == null || b.min < value.max));
  const W = 260, H = 44, gap = 2, bw = (W - 24 - gap * bins.length) / bins.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-11 w-full max-w-[17rem]" role="img"
      aria-label={t("discovery.filters.histogram", { label, unknown: fmt.format(dist.unknown) })}>
      <defs>
        <pattern id="nx-hatch-unknown" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="4" height="4" fill="currentColor" opacity="0.08" />
          <line x1="0" y1="0" x2="0" y2="4" stroke="currentColor" strokeWidth="1.4" opacity="0.45" />
        </pattern>
      </defs>
      {bins.map((b, i) => {
        const h = Math.max(b.n ? 1.5 : 0, (b.n / max) * (H - 2));
        return <rect key={i} x={i * (bw + gap)} y={H - h} width={bw} height={h} rx={1} fill="currentColor" opacity={inRange(b) ? 0.85 : 0.22} />;
      })}
      <rect x={W - 20} y={H - Math.max(1.5, (dist.unknown / max) * (H - 2))} width={20} height={Math.max(1.5, (dist.unknown / max) * (H - 2))} rx={1} fill="url(#nx-hatch-unknown)" />
    </svg>
  );
}
