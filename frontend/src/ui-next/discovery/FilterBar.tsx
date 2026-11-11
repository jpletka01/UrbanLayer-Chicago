// The filters as groups (owner's review 2026-11-10; decision Item 104): one button per group in the top bar, each
// with its icon and how many of its filters are on, opening a small panel of plain-language choices with icons.
// Technical names and coverage are small print. Edits stay in the panel until "Show N lots", whose count is a
// server search of the panel's draft; nothing here evaluates (INV-1).
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { ChevronDown, LoaderCircle, RotateCcw, X } from "lucide-react";
import { runSearch } from "../../discovery/searchClient";
import type { PanelState, Predicate, Registry, SpatialScope } from "../../discovery/types";
import { STROKE } from "../icons";
import { useDistribution, type Distribution } from "./discoveryData";
import {
  WALK_MAX, WALK_MIN, groupFilters, liveGroups, sameChoice, walkMiles, walkMinutes, type FilterSpec, type GroupSpec,
} from "./filterGroups";

const fmtFor = (lang: string) => new Intl.NumberFormat(lang.startsWith("es") ? "es-MX" : "en-US", { maximumFractionDigits: 2 });

export function FilterBar({
  registry, panel, scope, onApply, onWalkPreview, compact,
}: {
  registry: Registry;
  panel: PanelState;
  scope: SpatialScope | null;
  onApply: (panel: PanelState) => void;
  /** The transit panel's walk, in miles, while it is open (the map draws it around the L stops); null = none. */
  onWalkPreview?: (miles: number | null) => void;
  /** A phone: the panel opens as a bottom sheet. */
  compact: boolean;
}) {
  const { t, i18n } = useTranslation("next");
  const fmt = fmtFor(i18n.language);
  const groups = useMemo(() => liveGroups(registry), [registry]);
  const [open, setOpen] = useState<GroupSpec | null>(null);
  // Choices build up across groups until they are shown (owner's review): one draft for the whole bar, started
  // from the search on screen and dropped when a new search lands (its panel changes).
  const base = JSON.stringify(panel);
  const [pending, setPending] = useState<{ base: string; draft: PanelState } | null>(null);
  const draft = pending && pending.base === base ? pending.draft : panel;
  const dirty = JSON.stringify(draft) !== base;
  const setDraft = (fn: (d: PanelState) => PanelState) => setPending({ base, draft: fn(draft) });
  const count = useLiveCount(registry, draft, scope, dirty || open !== null);
  const apply = () => { onApply(draft); setPending(null); };
  const buttons = useRef<Record<string, HTMLButtonElement | null>>({});
  const close = () => {
    const id = open?.id;
    setOpen(null);
    onWalkPreview?.(null);
    if (id) buttons.current[id]?.focus({ preventScroll: true });
  };
  return (
    <div className="relative flex min-w-0 flex-wrap items-center gap-2" data-testid="filter-bar">
      <div className="flex min-w-0 flex-wrap items-center gap-2" role="group" aria-label={t("discovery.groups.label")}>
        {groups.map((g) => {
          const n = groupFilters(g).filter((f) => draft[f]).length;
          const Icon = g.icon;
          const isOpen = open?.id === g.id;
          return (
            <button key={g.id} type="button" ref={(el) => { buttons.current[g.id] = el; }}
              aria-expanded={isOpen} aria-haspopup="dialog"
              onClick={() => (isOpen ? close() : setOpen(g))}
              className={`inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full px-3 text-caption touch-target ${n || isOpen ? "bg-nx-ink text-nx-on-ink" : "bg-nx-ink/5 hover:bg-nx-ink/10"}`}
              data-group={g.id}>
              <Icon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
              {t(`discovery.groups.${g.id}`)}
              {n > 0 && <span className="tabular-nums">· {n}</span>}
              <ChevronDown aria-hidden className="h-3.5 w-3.5 opacity-70" strokeWidth={STROKE} />
            </button>
          );
        })}
        {dirty && !open && (
          <button type="button" onClick={apply} data-testid="bar-show"
            className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full bg-nx-primary px-3 text-caption font-medium text-nx-primary-fg touch-target">
            {count.loading && <LoaderCircle aria-hidden className="h-3.5 w-3.5 animate-spin" strokeWidth={STROKE} />}
            {count.n == null ? t("discovery.filters.showUnknown") : t("discovery.filters.show", { count: count.n, n: fmt.format(count.n) })}
          </button>
        )}
      </div>
      {open && (
        <GroupPanel key={open.id} group={open} draft={draft} setDraft={setDraft} count={count} compact={compact}
          onClose={close} onWalkPreview={onWalkPreview}
          onApply={() => { apply(); close(); }} />
      )}
    </div>
  );
}

/** The live "Show N lots" count: a server search of the draft (one row), debounced. */
function useLiveCount(registry: Registry, draft: PanelState, scope: SpatialScope | null, enabled: boolean) {
  const key = JSON.stringify(draft);
  const [answer, setAnswer] = useState<{ key: string; n: number | null } | null>(null);
  useEffect(() => {
    if (!enabled) return;  // only while a panel is open or choices wait to be shown
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      runSearch({ panelState: draft, scope, limit: 1 }, registry, controller.signal)
        .then((r) => { if (!controller.signal.aborted) setAnswer({ key, n: r?.result.total ?? null }); })
        .catch(() => { if (!controller.signal.aborted) setAnswer({ key, n: null }); });
    }, 300);
    return () => { window.clearTimeout(timer); controller.abort(); };
    // key stands for draft.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, registry, scope, enabled]);
  return { n: answer?.n ?? null, loading: answer?.key !== key };
}

function GroupPanel({ group, draft, setDraft, count, compact, onClose, onApply, onWalkPreview }: {
  group: GroupSpec; draft: PanelState; setDraft: (fn: (d: PanelState) => PanelState) => void;
  count: { n: number | null; loading: boolean }; compact: boolean;
  onClose: () => void; onApply: () => void; onWalkPreview?: (miles: number | null) => void;
}) {
  const { t, i18n } = useTranslation("next");
  const fmt = fmtFor(i18n.language);
  const set = (id: string, p: Predicate | null) => setDraft((d) => {
    const next = { ...d };
    if (p) next[id] = p as PanelState[string]; else delete next[id];
    return next;
  });
  const answer = count;
  const loading = count.loading;
  const mine = groupFilters(group);
  const chosen = mine.some((f) => draft[f]);
  const Icon = group.icon;

  const body: ReactNode = (
    <>
      <div className="flex items-center gap-2 border-b border-nx-ink/10 px-4 py-3">
        <Icon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
        <h2 className="flex-1 text-body font-semibold" id={`nx-group-${group.id}`}>{t(`discovery.groups.${group.id}Title`)}</h2>
        {chosen && (
          <button type="button" onClick={() => setDraft((d) => { const n = { ...d }; for (const f of mine) delete n[f]; return n; })}
            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-caption hover:bg-nx-ink/5 touch-target">
            <RotateCcw aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{t("discovery.filters.clear")}
          </button>
        )}
        <button type="button" onClick={onClose} aria-label={t("discovery.filters.close")} className="grid h-8 w-8 place-items-center rounded-lg hover:bg-nx-ink/5 touch-target">
          <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
        </button>
      </div>
      <div className="flex max-h-[min(30rem,60dvh)] flex-col gap-5 overflow-y-auto px-4 py-4">
        {group.filters.map((spec) => (
          <FilterBlock key={spec.filter} spec={spec} value={(draft[spec.filter] as Predicate | undefined) ?? undefined}
            onChange={(p) => set(spec.filter, p)} onWalkPreview={onWalkPreview} />
        ))}
      </div>
      <div className="border-t border-nx-ink/10 px-4 py-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))]">
        <button type="button" onClick={onApply} data-testid="filters-show"
          className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-nx-primary font-medium text-nx-primary-fg">
          {loading && <LoaderCircle aria-hidden className="h-4 w-4 animate-spin" strokeWidth={STROKE} />}
          {answer.n == null ? t("discovery.filters.showUnknown") : t("discovery.filters.show", { count: answer.n, n: fmt.format(answer.n) })}
        </button>
      </div>
    </>
  );

  if (compact) {
    return (
      <Dialog.Root open onOpenChange={(o) => { if (!o) onClose(); }}>
        <Dialog.Portal>
          <div className="ui-next">
            <Dialog.Overlay className="fixed inset-0 z-[65] bg-black/30" />
            <Dialog.Content aria-labelledby={`nx-group-${group.id}`} aria-describedby={undefined} data-testid="group-panel"
              className="fixed inset-x-0 bottom-0 z-[66] flex flex-col rounded-t-3xl bg-nx-page text-body text-nx-ink shadow-[0_-8px_32px_rgb(0_0_0/0.2)] focus:outline-none">
              <Dialog.Title className="sr-only">{t(`discovery.groups.${group.id}Title`)}</Dialog.Title>
              {body}
            </Dialog.Content>
          </div>
        </Dialog.Portal>
      </Dialog.Root>
    );
  }
  return <DesktopPanel labelledBy={`nx-group-${group.id}`} onClose={onClose}>{body}</DesktopPanel>;
}

/** A panel under the bar: Escape and a click outside close it; focus moves in and returns to the group's button. */
function DesktopPanel({ labelledBy, onClose, children }: { labelledBy: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef(onClose);
  useEffect(() => { closeRef.current = onClose; });
  useEffect(() => {
    ref.current?.querySelector<HTMLElement>("button, input")?.focus({ preventScroll: true });
    const down = (e: PointerEvent) => {
      const target = e.target as Element | null;
      if (ref.current && target && !ref.current.contains(target) && !target.closest("[data-group]")) closeRef.current();
    };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") closeRef.current(); };
    document.addEventListener("pointerdown", down);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("pointerdown", down); document.removeEventListener("keydown", key); };
  }, []);
  return (
    <div ref={ref} role="dialog" aria-labelledby={labelledBy} data-testid="group-panel"
      className="absolute left-0 top-12 z-40 w-[26rem] max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl bg-nx-page shadow-[0_12px_40px_rgb(0_0_0/0.22)]">
      {children}
    </div>
  );
}

function FilterBlock({ spec, value, onChange, onWalkPreview }: {
  spec: FilterSpec; value: Predicate | undefined; onChange: (p: Predicate | null) => void;
  onWalkPreview?: (miles: number | null) => void;
}) {
  const { t, i18n } = useTranslation("next");
  const fmt = fmtFor(i18n.language);
  const dist = useDistribution(spec.filter);
  const Icon = spec.icon;
  const share = dist && dist.total ? Math.round((100 * (dist.total - dist.unknown)) / dist.total) : null;
  const includeUnknown = !!(value && "includeUnknown" in value && value.includeUnknown);
  const withUnknown = (p: Predicate, inc: boolean): Predicate => {
    const { includeUnknown: _drop, ...rest } = p as Predicate & { includeUnknown?: boolean };
    void _drop;
    return (inc && p.kind !== "region" ? { ...rest, includeUnknown: true } : rest) as Predicate;
  };
  const card = (on: boolean) => `flex min-w-0 items-start gap-2 rounded-xl px-3 py-2.5 text-left touch-target ${on ? "bg-nx-ink text-nx-on-ink" : "bg-nx-ink/5 hover:bg-nx-ink/10"}`;
  const f = `discovery.f.${spec.filter}`;

  return (
    <section className="flex flex-col gap-2" data-filter={spec.filter} aria-labelledby={`nx-f-${spec.filter}`}>
      <div className="flex items-start gap-2">
        <Icon aria-hidden className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={STROKE} />
        <div className="min-w-0 flex-1">
          <h3 id={`nx-f-${spec.filter}`} className="font-medium">{t(`${f}.name`)}</h3>
          <p className="text-caption nx-muted">{t(`${f}.hint`)}</p>
        </div>
      </div>

      {spec.kind === "toggle" && (
        <button type="button" role="switch" aria-checked={!!value} aria-labelledby={`nx-f-${spec.filter}`}
          onClick={() => onChange(value ? null : { kind: "flag", value: true })}
          className={`${card(!!value)} items-center`}>
          <span className={`relative h-5 w-9 shrink-0 rounded-full ${value ? "bg-nx-on-ink/40" : "bg-nx-ink/20"}`}>
            <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-current transition-[left] ${value ? "left-[1.125rem]" : "left-0.5"}`} />
          </span>
          <span>{t(`${f}.on`)}</span>
        </button>
      )}

      {(spec.kind === "cards" || spec.kind === "multi") && spec.choices && (
        <div className="grid grid-cols-2 gap-2" role="group" aria-labelledby={`nx-f-${spec.filter}`}>
          {spec.choices.map((c) => {
            const CIcon = c.icon;
            const on = spec.kind === "multi"
              ? value?.kind === "enum" && c.predicate.kind === "enum" && c.predicate.values.every((v) => value.values.includes(v))
              : sameChoice(value, c.predicate);
            const n = spec.kind === "multi" && c.predicate.kind === "enum" ? dist?.values?.[c.predicate.values[0]] : undefined;
            return (
              <button key={c.id} type="button" aria-pressed={on} className={card(on)}
                onClick={() => {
                  if (spec.kind === "multi" && c.predicate.kind === "enum") {
                    const cur = value?.kind === "enum" ? value.values : [];
                    const v = c.predicate.values[0];
                    const next = on ? cur.filter((x) => x !== v) : [...cur, v];
                    onChange(next.length ? withUnknown({ kind: "enum", values: next }, includeUnknown) : null);
                  } else {
                    onChange(on ? null : withUnknown(c.predicate, includeUnknown));
                  }
                }}>
                <CIcon aria-hidden className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={STROKE} />
                <span className="min-w-0">
                  <span className="block text-caption font-medium">
                    {t(`discovery.choice.${spec.filter}.${c.id}.name`, c.predicate.kind === "range" ? { from: c.predicate.min, to: c.predicate.max } : undefined)}
                  </span>
                  <span className={`block text-[11px] leading-snug ${on ? "opacity-80" : "nx-muted"}`}>
                    {t(`discovery.choice.${spec.filter}.${c.id}.hint`)}{n != null ? ` · ${fmt.format(n)}` : ""}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      )}

      {spec.kind === "walk" && <WalkSlider value={value} onChange={onChange} onPreview={onWalkPreview} />}

      {dist?.bins && spec.kind === "cards" && <Histogram dist={dist} value={value?.kind === "range" ? value : null} label={t(`${f}.name`)} />}

      <p className="text-[11px] nx-muted">
        {[share != null ? t("discovery.filters.coverage", { share, known: "" }) : null, t(`${f}.tech`, { defaultValue: "" }) || null].filter(Boolean).join(" · ")}
      </p>
      {value && dist && dist.unknown > 0 && (
        <label className="flex items-center gap-2 text-caption">
          <input type="checkbox" checked={includeUnknown} onChange={(e) => onChange(withUnknown(value, e.target.checked))} className="h-4 w-4" />
          {t("discovery.filters.includeUnknown", { n: fmt.format(dist.unknown) })}
        </label>
      )}
    </section>
  );
}

function WalkSlider({ value, onChange, onPreview }: { value: Predicate | undefined; onChange: (p: Predicate | null) => void; onPreview?: (mi: number | null) => void }) {
  const { t, i18n } = useTranslation("next");
  const fmt = fmtFor(i18n.language);
  const minutes = value?.kind === "range" && value.max != null ? walkMinutes(value.max) : null;
  const shown = minutes ?? 10;
  useEffect(() => { onPreview?.(minutes != null ? walkMiles(minutes) : null); }, [minutes, onPreview]);
  return (
    <div className="flex flex-col gap-2">
      <label className="flex items-center gap-2 text-caption">
        <input type="checkbox" checked={minutes != null} className="h-4 w-4"
          onChange={(e) => onChange(e.target.checked ? { kind: "range", max: walkMiles(10) } : null)} />
        {t("discovery.f.transit_proximity.on")}
      </label>
      <input type="range" min={WALK_MIN} max={WALK_MAX} step={1} value={shown} disabled={minutes == null}
        aria-label={t("discovery.f.transit_proximity.name")}
        aria-valuetext={t("discovery.walk.value", { minutes: shown, mi: fmt.format(walkMiles(shown)) })}
        onChange={(e) => onChange({ kind: "range", max: walkMiles(Number(e.target.value)) })}
        className="w-full accent-current disabled:opacity-40" />
      <p className="text-body font-medium tabular-nums">{t("discovery.walk.value", { minutes: shown, mi: fmt.format(walkMiles(shown)) })}</p>
      <p className="text-[11px] nx-muted">{t("discovery.walk.note")}</p>
    </div>
  );
}

/** A filter's spread across the city's lots: 16 bars over its domain, the chosen range dark, the unknowns hatched. */
export function Histogram({ dist, value, label }: { dist: Distribution; value: { min?: number; max?: number } | null; label: string }) {
  const { t, i18n } = useTranslation("next");
  const bins = dist.bins ?? [];
  const max = Math.max(1, dist.unknown, ...bins.map((b) => b.n));
  const fmt = fmtFor(i18n.language);
  const inRange = (b: { min: number; max: number }) => !value || ((value.min == null || b.max > value.min) && (value.max == null || b.min < value.max));
  const W = 260, H = 36, gap = 2, bw = (W - 24 - gap * bins.length) / bins.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-9 w-full" role="img"
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
