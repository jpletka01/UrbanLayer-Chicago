// The Deep analysis tab (decision Item 124, design v3 on the canvas "Deep Analysis Wireframe"): the most a builder can
// pay for this lot for one project, sold or rented, from numbers that are all visible, sourced and editable; the
// projects side by side with their limits as rings; and the stress test. The page's one map shows the chosen project
// in 3D on the lot (anything above the height limit red), through `onProject`.
//
// Who sees it is decided by the server (`/api/deep-analysis` answers 403 unless the lot is open to the account); this
// component only words the states: signed out, the free one not used yet (one button uses it on this lot; browsing
// never does), used on another lot (one quiet Pro offer, nothing locked elsewhere), and a lot we couldn't confirm.
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BadgeCheck, Calculator, ChartColumnBig, LayoutGrid, ChevronDown, LoaderCircle, LogIn, MapPin, Minus, Plus, Scale, X } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  DeepAnalysisError, DeepClaimError, claimDeepAnalysis, getDeepAnalysis, getDeepProject, putDeepProject,
  type DeepAnalysis, type DeepInputs,
} from "../../lib/api";
import { analysisCache, useDeepGate } from "./deepGate";
import { useAuthContext } from "../../contexts/AuthContext";
import { Pill } from "../ui/Blocks";
import { ScoreRing } from "../ui/ScoreRing";
import {
  STRESS_STEPS, compute, limitUse, money, projectMass, startingNumbers, startingProjects, step, stressGrid,
  type Mode, type NumberSource, type Numbers, type Project,
} from "./deepModel";

export interface DeepProjectOnMap { heightFt: number; capFt: number | null; label: string }

export function DeepTab({ pin, exact, onProject }: {
  /** The lot's 14-digit PIN; null when the Profile has none (an approximate match). */
  pin: string | null;
  /** The Profile matched this exact lot (not a nearest stand-in). */
  exact: boolean;
  onProject: (p: DeepProjectOnMap | null) => void;
}) {
  const { t } = useTranslation("next");
  const { signIn } = useAuthContext();
  const { gate, ent, change } = useDeepGate(pin, exact);
  const [claiming, setClaiming] = useState(false);

  useEffect(() => { if (gate !== "open") onProject(null); }, [gate, onProject]);

  const claim = async () => {
    if (!pin) return;
    setClaiming(true);
    try {
      await claimDeepAnalysis(pin);
      change("open", ent);
    } catch (e) {
      if (e instanceof DeepClaimError && e.status === 409) {
        change("elsewhere", ent ? { ...ent, deep_analysis: { ...ent.deep_analysis, free_left: 0, free_pin: e.freePin } } : ent);
      } else change("failed", ent);
    } finally {
      setClaiming(false);
    }
  };

  if (gate === "open" && pin) return <DeepAnalysisOpen pin={pin} freeHere={!ent?.deep_analysis.unlimited} onProject={onProject} />;

  return (
    <div className="flex flex-col gap-6" data-testid="deep-tab" data-gate={gate}>
      {gate === "approximate" ? (
        <>
          <p className="text-[1.125rem] font-semibold">{t("deep.gate.approximate")}</p>
          <p className="nx-muted text-center">{t("deep.gate.approximateNote")}</p>
          <div className="flex justify-center">
            <Link to="/discovery" className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 font-semibold ring-1 ring-inset ring-nx-ink/20 hover:bg-nx-ink/5 touch-target">
              <MapPin aria-hidden className="h-4 w-4" strokeWidth={2} />{t("deep.gate.pickOnMap")}
            </Link>
          </div>
        </>
      ) : (
        <>
          <p className="text-[1.125rem] font-semibold">{t("deep.gate.lead")}</p>
          <Outline />
          {gate === "checking" && <p className="nx-muted flex items-center justify-center gap-2"><LoaderCircle aria-hidden className="h-4 w-4 animate-spin" />{t("deep.gate.checking")}</p>}
          {gate === "failed" && <p className="nx-muted text-center">{t("deep.gate.failed")}</p>}
          {gate === "signed_out" && (
            <div className="flex flex-col items-center gap-2.5">
              <p>{t("deep.gate.signIn")}</p>
              <button type="button" onClick={() => signIn()} className="inline-flex items-center gap-2 rounded-full bg-nx-primary px-5 py-2.5 font-semibold text-nx-primary-fg touch-target" data-testid="deep-sign-in">
                <LogIn aria-hidden className="h-4 w-4" strokeWidth={2} />{t("deep.gate.signInButton")}
              </button>
            </div>
          )}
          {gate === "unused" && (
            <div className="flex flex-col items-center gap-2.5">
              <button type="button" onClick={claim} disabled={claiming} className="inline-flex items-center gap-2 rounded-full bg-nx-primary px-5 py-2.5 font-semibold text-nx-primary-fg disabled:opacity-60 touch-target" data-testid="deep-claim">
                {claiming && <LoaderCircle aria-hidden className="h-4 w-4 animate-spin" />}{t("deep.gate.claim")}
              </button>
              <p className="nx-muted text-caption">{t("deep.gate.claimNote")}</p>
            </div>
          )}
          {gate === "elsewhere" && <Elsewhere freePin={ent?.deep_analysis.free_pin ?? null} freeAddress={ent?.deep_analysis.free_address ?? null} />}
        </>
      )}
    </div>
  );
}

/** What the tab holds, before it is open: four equal tiles under the lead sentence. */
function Outline() {
  const { t } = useTranslation("next");
  const items = [
    { k: "bid", Icon: Scale },
    { k: "projects", Icon: LayoutGrid },
    { k: "numbers", Icon: Calculator },
    { k: "stress", Icon: ChartColumnBig },
  ] as const;
  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4" data-testid="deep-outline">
      {items.map(({ k, Icon }) => (
        <li key={k} className="flex gap-3 rounded-2xl bg-nx-block p-5">
          <Icon aria-hidden className="mt-0.5 h-[18px] w-[18px] shrink-0" strokeWidth={1.75} />
          <div>
            <div className="font-semibold">{t(`deep.outline.${k}`)}</div>
            <div className="nx-muted text-caption">{t(`deep.outline.${k}Note`)}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}

/** The free one went to another lot: say which, and offer Pro once, quietly, beside it (Item 119: no walls). */
function Elsewhere({ freePin, freeAddress }: { freePin: string | null; freeAddress: string | null }) {
  const { t } = useTranslation("next");
  const where = freeAddress ?? freePin;
  return (
    <div className="mx-auto grid w-full max-w-[880px] grid-cols-1 gap-6 sm:grid-cols-2" data-testid="deep-elsewhere">
      <div className="flex flex-col items-center gap-2.5 rounded-2xl bg-nx-block p-6 text-center">
        <BadgeCheck aria-hidden className="h-5 w-5" strokeWidth={1.75} />
        <div className="font-semibold">{t("deep.gate.yourFree")}</div>
        <div>
          {t("deep.gate.wentTo")}{" "}
          {freePin ? <Link to={`/scorecard?pin=${freePin}`} className="font-semibold underline">{where}</Link> : where}
        </div>
      </div>
      <div className="nx-pro-rim animate-nx-rim">
        <div className="flex h-full flex-col items-center gap-2.5 rounded-2xl bg-nx-page p-6 text-center">
          <div className="font-semibold">{t("deep.gate.proTitle")}</div>
          <div className="nx-muted text-caption">{t("deep.gate.proNote")}</div>
          <Link to="/pricing" className="inline-flex items-center rounded-full px-5 py-2.5 font-semibold ring-1 ring-inset ring-nx-ink/20 hover:bg-nx-ink/5 touch-target">{t("deep.gate.seePro")}</Link>
        </div>
      </div>
    </div>
  );
}

// ── The analysis ─────────────────────────────────────────────────────────────────────────────────────────

type State = { status: "loading" } | { status: "failed"; code: number | null } | { status: "ready"; data: DeepAnalysis };

function DeepAnalysisOpen({ pin, freeHere, onProject }: { pin: string; freeHere: boolean; onProject: (p: DeepProjectOnMap | null) => void }) {
  const { t, i18n } = useTranslation("next");
  const [attempt, setAttempt] = useState(0);
  const key = `${pin}|${i18n.language}|${attempt}`;
  const [answer, setAnswer] = useState<{ key: string; state: State; saved: Awaited<ReturnType<typeof getDeepProject>> | null } | null>(null);

  useEffect(() => {
    const c = new AbortController();
    // The analysis is kept for this visit (switching tabs unmounts this one); the saved project is asked each time.
    const cacheKey = `${pin}|${i18n.language}`;
    const kept = attempt === 0 ? analysisCache.get(cacheKey) : undefined;
    Promise.all([kept ? Promise.resolve(kept) : getDeepAnalysis(pin, i18n.language, c.signal), getDeepProject(pin).catch(() => null)]).then(
      ([data, proj]) => { analysisCache.set(cacheKey, data); setAnswer({ key, state: { status: "ready", data }, saved: proj }); },
      (e) => { if (!c.signal.aborted) setAnswer({ key, state: { status: "failed", code: e instanceof DeepAnalysisError ? e.status : null }, saved: null }); },
    );
    return () => c.abort();
  }, [key, pin, i18n.language, attempt]);

  const state: State = answer?.key === key ? answer.state : { status: "loading" };
  const saved = answer?.key === key ? answer.saved : null;

  if (state.status === "loading") {
    return (
      <div className="flex flex-col gap-6" data-testid="deep-tab" data-gate="loading">
        <p className="nx-muted flex items-center gap-2"><LoaderCircle aria-hidden className="h-4 w-4 animate-spin" />{t("deep.loading")}</p>
        <div className="h-48 animate-pulse rounded-2xl bg-nx-block" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">{[0, 1, 2].map((i) => <div key={i} className="h-36 animate-pulse rounded-2xl bg-nx-block" />)}</div>
      </div>
    );
  }
  if (state.status === "failed") {
    return (
      <div className="flex flex-col items-center gap-3 py-8" data-testid="deep-tab" data-gate="failed">
        <p>{t(state.code === 429 ? "deep.tooMany" : "deep.failed")}</p>
        {state.code !== 429 && (
          <button type="button" onClick={() => setAttempt((n) => n + 1)} className="rounded-full px-5 py-2.5 font-semibold ring-1 ring-inset ring-nx-ink/20 touch-target">{t("profile.parts.retry")}</button>
        )}
      </div>
    );
  }
  return <Analysis pin={pin} data={state.data} saved={saved} freeHere={freeHere} onProject={onProject} />;
}

type CardKey = string; // "largest" | "three_flat" | "townhouses" | `own:${id}`
type PresetKind = "largest" | "three_flat" | "townhouses";
type OwnProject = Project & { id: string; basedOn?: PresetKind };
interface ProjectOption { key: CardKey; project: Project; own: OwnProject | null; n: number; bid: number }
type CardPrice = Partial<Pick<Numbers, "salePriceUnit" | "rentUnitMonth">>;
type Saved = Awaited<ReturnType<typeof getDeepProject>> | null;
/** The builder's own projects on one lot (the server allows the same). */
export const MAX_OWN = 6;
/** The numbers that belong to a card (they depend on its unit size); the rest are shared. */
const CARD_NUMBERS: (keyof Numbers)[] = ["salePriceUnit", "rentUnitMonth"];
const TO_SNAKE: Record<keyof Numbers, string> = {
  landPrice: "land_price", salePriceUnit: "sale_price_unit", rentUnitMonth: "rent_unit_month", buildCostSqft: "build_cost_sqft",
  softCostPct: "soft_cost_pct", loanToCost: "loan_to_cost", loanRate: "loan_rate", buildMonths: "build_months",
  sellingPct: "selling_pct", profitOnCost: "profit_on_cost", vacancyPct: "vacancy_pct", opexPct: "opex_pct",
  capRate: "cap_rate", targetYield: "target_yield", taxRate: "tax_rate",
};
const FROM_SNAKE = Object.fromEntries(Object.entries(TO_SNAKE).map(([k, v]) => [v, k])) as Record<string, keyof Numbers>;

function newOwnId(owns: OwnProject[]): string {
  let id = "";
  do id = Math.random().toString(36).slice(2, 8); while (owns.some((o) => o.id === id));
  return id;
}

function ownsFrom(saved: Saved): OwnProject[] {
  const list: OwnProject[] = (saved?.own ?? []).map((o) => ({ kind: "own" as const, id: o.id, basedOn: o.based_on ?? undefined, units: o.units, floors: o.stories, floorAreaSqft: o.floor_area_sqft }));
  // A row saved before the list: its one "own" project becomes the first of the builder's own.
  const p = saved?.project;
  if (!list.length && p?.kind === "own") list.push({ kind: "own", id: "own1", units: p.units, floors: p.stories, floorAreaSqft: p.floor_area_sqft });
  return list.slice(0, MAX_OWN);
}

function focusFrom(saved: Saved, starts: Project[]): CardKey {
  if (saved?.focus) return saved.focus;
  const p = saved?.project;
  if (p?.kind === "own") return `own:${ownsFrom(saved)[0]?.id ?? "own1"}`;
  return p?.kind ?? starts[0]?.kind ?? "largest";
}

function pricesFrom(saved: Saved, focus: CardKey): Record<string, CardPrice> {
  const out: Record<string, CardPrice> = {};
  for (const [k, v] of Object.entries(saved?.prices ?? {})) {
    out[k] = { ...(v.sale_price_unit != null && { salePriceUnit: v.sale_price_unit }), ...(v.rent_unit_month != null && { rentUnitMonth: v.rent_unit_month }) };
  }
  // A row saved before per-card prices: its one sale price or rent was the focused card's.
  const n = saved?.numbers ?? {};
  if (!saved?.prices && (typeof n.sale_price_unit === "number" || typeof n.rent_unit_month === "number")) {
    out[focus] = { ...(typeof n.sale_price_unit === "number" && { salePriceUnit: n.sale_price_unit }), ...(typeof n.rent_unit_month === "number" && { rentUnitMonth: n.rent_unit_month }) };
  }
  return out;
}

function Analysis({ pin, data, saved, freeHere, onProject }: {
  pin: string;
  data: DeepAnalysis;
  saved: Awaited<ReturnType<typeof getDeepProject>> | null;
  freeHere: boolean;
  onProject: (p: DeepProjectOnMap | null) => void;
}) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const inputs = data.inputs;
  const starts = useMemo(() => startingProjects(inputs), [inputs]);

  // The cards: the ready-made projects, and the builder's own (changed copies, up to MAX_OWN), one of them in focus
  // (a purple outline; the numbers, the answer and the map follow it). Sale price and rent belong to each card (they
  // depend on its unit size); the other numbers are shared assumptions.
  const [owns, setOwns] = useState<OwnProject[]>(() => ownsFrom(saved));
  const [focus, setFocus] = useState<CardKey>(() => focusFrom(saved, starts));
  const [prices, setPrices] = useState<Record<string, CardPrice>>(() => pricesFrom(saved, focusFrom(saved, starts)));
  const cardOf = (k: CardKey): Project | null =>
    k.startsWith("own:") ? owns.find((o) => `own:${o.id}` === k) ?? null : starts.find((p) => p.kind === k) ?? null;
  const project = cardOf(focus) ?? starts[0] ?? null;
  const focusKey: CardKey = cardOf(focus) ? focus : (starts[0]?.kind ?? "largest");
  const [mode, setMode] = useState<Mode>(() => (saved?.numbers?.mode === "rent" ? "rent" : "sell"));
  const base = useMemo(() => (project ? startingNumbers(inputs, project) : null), [inputs, project]);
  const [edits, setEdits] = useState<Partial<Numbers>>(() => {
    const out: Partial<Numbers> = {};
    for (const [k, v] of Object.entries(saved?.numbers ?? {})) {
      const key = FROM_SNAKE[k];
      if (key && !CARD_NUMBERS.includes(key) && typeof v === "number") (out as Record<string, number>)[key] = v;
    }
    return out;
  });
  const numbers: Numbers | null = base ? { ...base.numbers, ...edits, ...prices[focusKey] } : null;

  const ownOf = (k: CardKey) => owns.find((o) => `own:${o.id}` === k) ?? null;
  // A copy of the project on screen as a new project of the builder's own, in focus; its price comes along.
  const fork = (from: Project, basedOn: PresetKind | undefined): CardKey | null => {
    if (owns.length >= MAX_OWN) return null;
    const id = newOwnId(owns);
    const key = `own:${id}`;
    setOwns((o) => [...o, { kind: "own", id, basedOn, units: from.units, floors: from.floors, floorAreaSqft: from.floorAreaSqft }]);
    if (prices[focusKey]) setPrices((pr) => ({ ...pr, [key]: { ...pr[focusKey] } }));
    setFocus(key);
    return key;
  };
  const basedOnOf = (k: CardKey): PresetKind | undefined => (k.startsWith("own:") ? ownOf(k)?.basedOn : (k as PresetKind));
  const addOwn = () => { if (project) fork(project, basedOnOf(focusKey)); };
  // − / + on a ready-made project saves the change as a project of the builder's own (the ready-made one stays in the
  // list, with "Back to …"); on one of the builder's own it changes that one.
  const stepProject = (field: "units" | "floors" | "floorAreaSqft", d: 1 | -1) => {
    if (!project) return;
    const next = step(project, field, d);
    const own = ownOf(focusKey);
    if (own) setOwns((o) => o.map((x) => (x.id === own.id ? { ...x, units: next.units, floors: next.floors, floorAreaSqft: next.floorAreaSqft } : x)));
    else fork(next, focusKey as PresetKind);
  };
  const removeOwn = (id: string) => {
    const gone = owns.find((o) => o.id === id);
    setOwns((o) => o.filter((x) => x.id !== id));
    setPrices((pr) => { const { [`own:${id}`]: _gone, ...rest } = pr; void _gone; return rest; });
    if (focus === `own:${id}`) setFocus(gone?.basedOn ?? starts[0]?.kind ?? "largest");
  };
  const options: ProjectOption[] = [
    ...starts.map((p) => ({ key: p.kind, project: p, own: null as OwnProject | null, n: 0 })),
    ...owns.map((o, i) => ({ key: `own:${o.id}`, project: o as Project, own: o, n: i + 1 })),
  ].map((o) => ({ ...o, bid: compute(o.project, { ...startingNumbers(inputs, o.project).numbers, ...edits, ...prices[o.key] }, mode).landBid }));

  // The project on the map.
  useEffect(() => {
    if (!project) { onProject(null); return; }
    const m = projectMass(project, inputs);
    const own = owns.findIndex((o) => `own:${o.id}` === focusKey);
    const name = own >= 0 ? t("deep.projects.kind.ownN", { n: own + 1, units: project.units }) : t(`deep.projects.kind.${project.kind}`, { units: project.units });
    onProject({ ...m, label: t("deep.map.label", { name, floors: project.floors }) });
  }, [project, owns, focusKey, inputs, onProject, t]);
  useEffect(() => () => onProject(null), [onProject]);

  // Saved to the account, a moment after the last change (the server keeps one row per lot).
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    if (!project) return;
    const id = window.setTimeout(() => {
      const snake: Record<string, number> = {};
      for (const [k, v] of Object.entries(edits)) if (typeof v === "number") snake[TO_SNAKE[k as keyof Numbers]] = v;
      const cardPrices: Record<string, { sale_price_unit?: number; rent_unit_month?: number }> = {};
      for (const [k, v] of Object.entries(prices)) {
        if (k.startsWith("own:") && !owns.some((o) => `own:${o.id}` === k)) continue;
        cardPrices[k] = { ...(v.salePriceUnit != null && { sale_price_unit: v.salePriceUnit }), ...(v.rentUnitMonth != null && { rent_unit_month: v.rentUnitMonth }) };
      }
      putDeepProject(pin, {
        project: { kind: project.kind, units: project.units, stories: project.floors, floor_area_sqft: project.floorAreaSqft },
        numbers: snake, mode, step: saved?.step ?? 0,
        own: owns.map((o) => ({ id: o.id, units: o.units, stories: o.floors, floor_area_sqft: o.floorAreaSqft, ...(o.basedOn && { based_on: o.basedOn }) })),
        focus: focusKey, prices: cardPrices,
      }).catch(() => { /* a failed save keeps the page as it is; the next change tries again */ });
    }, 800);
    return () => window.clearTimeout(id);
  }, [pin, project, edits, prices, owns, focusKey, mode, saved?.step]);

  if (!project || !numbers || !base) {
    return (
      <div className="flex flex-col gap-3 py-6" data-testid="deep-tab" data-gate="open">
        <p className="text-[1.125rem] font-semibold">{t("deep.noNumbers")}</p>
        <p className="nx-muted">{t("deep.noNumbersNote")}</p>
      </div>
    );
  }

  const result = compute(project, numbers, mode);
  const grid = stressGrid(project, numbers, mode);
  const sale = inputs.last_sale;
  const bid = result.landBid;
  const answer = bid <= 0
    ? t(mode === "sell" ? "deep.answer.sellNoLand" : "deep.answer.rentNoLand", { units: project.units })
    : sale
      ? t(mode === "sell" ? "deep.answer.sell" : "deep.answer.rent", { units: project.units, bid: money(bid, lng), sale: money(sale.price, lng) })
      : t(mode === "sell" ? "deep.answer.sellNoSale" : "deep.answer.rentNoSale", { units: project.units, bid: money(bid, lng) });
  const set = (k: keyof Numbers, v: number) => (CARD_NUMBERS.includes(k)
    ? setPrices((pr) => ({ ...pr, [focusKey]: { ...pr[focusKey], [k]: v } }))
    : setEdits((e) => ({ ...e, [k]: v })));
  // The land and sale sliders' ranges come from the starting figures (three times them), never from the value being
  // dragged: a range that grew with the value ran away under the thumb.
  const roundUp = (v: number, to: number) => Math.ceil(v / to) * to;
  const landMax = roundUp(Math.max(1_500_000, (base.numbers.landPrice ?? 0) * 3), 100_000);
  const saleMax = roundUp(Math.max(500_000, base.numbers.salePriceUnit * 3), 50_000);
  return (
    <div className="flex flex-col gap-7" data-testid="deep-tab" data-gate="open">
      <div className="flex flex-col gap-1.5">
        <p className="text-[1.125rem] font-semibold" data-testid="deep-answer">{answer}</p>
        {freeHere && (
          <p className="nx-muted flex items-center gap-1.5 text-caption"><BadgeCheck aria-hidden className="h-3.5 w-3.5" strokeWidth={2} />{t("deep.freeHere")}</p>
        )}
      </div>

      {/* 1 · the most you can pay */}
      <section className="nx-cq grid grid-cols-1 items-center gap-8 rounded-2xl bg-nx-block p-6 md:grid-cols-2" aria-labelledby="deep-bid-h">
        <div className="flex flex-col items-center gap-2.5 text-center">
          <div role="radiogroup" aria-label={t("deep.mode.label")} className="inline-flex rounded-full p-1 ring-1 ring-inset ring-nx-ink/20">
            {(["sell", "rent"] as const).map((m) => (
              <button key={m} type="button" role="radio" aria-checked={mode === m} onClick={() => setMode(m)}
                className={`rounded-full px-4 py-1.5 touch-target ${mode === m ? "bg-nx-ink font-semibold text-nx-page" : "hover:bg-nx-ink/5"}`} data-mode={m}>
                {t(`deep.mode.${m}`)}
              </button>
            ))}
          </div>
          <h3 id="deep-bid-h" className="nx-muted pt-1 text-caption font-normal">{t("deep.bid.label")}</h3>
          <div className="text-[3rem] font-semibold leading-none tabular-nums" data-testid="deep-bid">{bid > 0 ? money(bid, lng) : t("deep.bid.none")}</div>
          <div className="nx-muted text-caption">{t(mode === "sell" ? "deep.bid.atProfit" : "deep.bid.atYield", { pct: pct(mode === "sell" ? numbers.profitOnCost : numbers.targetYield, lng) })}</div>
        </div>
        <div className="flex flex-col gap-3">
          {sale && bid > 0 && <BidBar bid={bid} sale={sale.price} lng={lng} />}
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            <Mini label={t(mode === "sell" ? "deep.out.breakEvenSale" : "deep.out.breakEvenRent")}
              figure={result.breakEven != null ? money(result.breakEven, lng, { short: mode === "sell" }) : "—"}
              unit={t(mode === "sell" ? "deep.out.perUnit" : "deep.out.perUnitMonth")}
              note={result.breakEven == null ? t("deep.out.noSale") : undefined} />
            <Mini label={t("deep.out.taxes")} figure={money(result.taxesOnceBuilt, lng)} unit={t("deep.out.perYear")}
              note={inputs.tax.current_bill != null ? t("deep.out.taxesToday", { bill: money(inputs.tax.current_bill, lng) }) : undefined} />
            <Mini label={t("deep.out.cash")} figure={result.cashIn != null ? money(result.cashIn, lng) : "—"}
              note={sale ? t("deep.out.atPrice", { price: money(sale.price, lng) }) : t("deep.out.atBid")} />
          </div>
        </div>
      </section>

      {/* 2 · the project (one at a time, chosen from a list) and "if things move", beside your numbers: two columns of
          about the same height (owner, 2026-11-16) */}
      <section className="nx-cq grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          <ProjectPanel project={project} focusKey={focusKey} options={options} owns={owns} inputs={inputs}
            onPick={setFocus} onStep={stepProject} onSaveNew={addOwn} onRemove={removeOwn}
            backTo={ownOf(focusKey)?.basedOn ?? null} onBack={(k) => setFocus(k)} />
          <StressGrid grid={grid} sale={sale?.price ?? null} lng={lng} mode={mode} />
        </div>
        <div className="flex flex-col gap-4 rounded-2xl bg-nx-block p-6">
          <h3 className="text-center font-semibold">{t("deep.numbers.title")}</h3>
          <Slider label={t("deep.numbers.land")} value={numbers.landPrice ?? 0} min={0} max={landMax} stepBy={10_000}
            show={money(numbers.landPrice ?? 0, lng)} source={base.sources.landPrice} onChange={(v) => set("landPrice", v)} />
          {mode === "sell"
            ? <Slider label={t("deep.numbers.sale")} value={numbers.salePriceUnit} min={50_000} max={saleMax} stepBy={5_000}
                show={t("deep.numbers.perUnit", { v: money(numbers.salePriceUnit, lng) })} source={base.sources.salePriceUnit} onChange={(v) => set("salePriceUnit", v)} />
            : <Slider label={t("deep.numbers.rent")} value={numbers.rentUnitMonth} min={500} max={8_000} stepBy={25}
                show={t("deep.numbers.perUnitMonth", { v: money(numbers.rentUnitMonth, lng, { short: false }) })} source={base.sources.rentUnitMonth} onChange={(v) => set("rentUnitMonth", v)} />}
          <Slider label={t("deep.numbers.build")} value={numbers.buildCostSqft} min={100} max={500} stepBy={5}
            show={t("deep.numbers.perSqft", { v: money(numbers.buildCostSqft, lng, { short: false }) })} source={base.sources.buildCostSqft} hint={t("deep.numbers.buildHint")} onChange={(v) => set("buildCostSqft", v)} />
          <Slider label={t("deep.numbers.soft")} value={numbers.softCostPct} min={0.05} max={0.4} stepBy={0.01} show={t("deep.numbers.ofBuild", { v: pct(numbers.softCostPct, lng) })} source={base.sources.softCostPct} onChange={(v) => set("softCostPct", v)} />
          <Slider label={t("deep.numbers.loanRate")} value={numbers.loanRate} min={0.05} max={0.14} stepBy={0.0025} show={t("deep.numbers.loan", { ltc: pct(numbers.loanToCost, lng), rate: pct(numbers.loanRate, lng, 2) })} source={base.sources.loanRate} onChange={(v) => set("loanRate", v)} />
          {mode === "sell"
            ? <Slider label={t("deep.numbers.profit")} value={numbers.profitOnCost} min={0.05} max={0.4} stepBy={0.01} show={t("deep.numbers.onCost", { v: pct(numbers.profitOnCost, lng) })} source={base.sources.profitOnCost} onChange={(v) => set("profitOnCost", v)} />
            : <Slider label={t("deep.numbers.yield")} value={numbers.targetYield} min={0.04} max={0.12} stepBy={0.0025} show={pct(numbers.targetYield, lng, 2)} source={base.sources.targetYield} onChange={(v) => set("targetYield", v)} />}
          <details className="group">
            <summary className="nx-muted cursor-pointer text-caption touch-target">{t("deep.numbers.more")}</summary>
            <div className="flex flex-col gap-4 pt-3">
              <Slider label={t("deep.numbers.ltc")} value={numbers.loanToCost} min={0.4} max={0.9} stepBy={0.05} show={pct(numbers.loanToCost, lng)} source={base.sources.loanToCost} onChange={(v) => set("loanToCost", v)} />
              <Slider label={t("deep.numbers.months")} value={numbers.buildMonths} min={6} max={36} stepBy={1} show={t("deep.numbers.monthsV", { v: numbers.buildMonths })} source={base.sources.buildMonths} onChange={(v) => set("buildMonths", v)} />
              {mode === "sell"
                ? <Slider label={t("deep.numbers.selling")} value={numbers.sellingPct} min={0} max={0.12} stepBy={0.005} show={pct(numbers.sellingPct, lng, 1)} source={base.sources.sellingPct} onChange={(v) => set("sellingPct", v)} />
                : <>
                    <Slider label={t("deep.numbers.opex")} value={numbers.opexPct} min={0.15} max={0.5} stepBy={0.01} show={pct(numbers.opexPct, lng)} source={base.sources.opexPct} onChange={(v) => set("opexPct", v)} />
                    <Slider label={t("deep.numbers.vacancy")} value={numbers.vacancyPct} min={0} max={0.15} stepBy={0.01} show={pct(numbers.vacancyPct, lng)} source={base.sources.vacancyPct} onChange={(v) => set("vacancyPct", v)} />
                    <Slider label={t("deep.numbers.cap")} value={numbers.capRate} min={0.04} max={0.09} stepBy={0.0025} show={pct(numbers.capRate, lng, 2)} source={base.sources.capRate} onChange={(v) => set("capRate", v)} />
                  </>}
              <Slider label={t("deep.numbers.tax")} value={numbers.taxRate} min={0.005} max={0.05} stepBy={0.0005} show={pct(numbers.taxRate, lng, 2)} source={base.sources.taxRate} onChange={(v) => set("taxRate", v)} />
            </div>
          </details>
          {(Object.keys(edits).length > 0 || Object.keys(prices).length > 0) && (
            <button type="button" onClick={() => { setEdits({}); setPrices({}); }} className="nx-muted self-center text-caption underline touch-target">{t("deep.numbers.reset")}</button>
          )}
        </div>
      </section>
      <p className="nx-muted text-center text-caption">{t("deep.disclaimer")}</p>
    </div>
  );
}

function pct(v: number, lng: string, digits = 0): string {
  return (v * 100).toLocaleString(lng.startsWith("es") ? "es-MX" : "en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits }) + "%";
}

function Mini({ label, figure, unit, note }: { label: string; figure: string; unit?: string; note?: string }) {
  return (
    <div className="rounded-xl bg-nx-page p-3 text-center">
      <div className="nx-muted text-caption">{label}</div>
      <div className="text-[1.125rem] font-semibold tabular-nums">{figure}{unit && <span className="text-caption font-normal"> {unit}</span>}</div>
      {note && <div className="nx-muted text-[0.6875rem]">{note}</div>}
    </div>
  );
}

/** The bid against what the lot last sold for, on one axis from $0. */
function BidBar({ bid, sale, lng }: { bid: number; sale: number; lng: string }) {
  const { t } = useTranslation("next");
  const max = Math.max(bid, sale) * 1.35;
  const x = (v: number) => 10 + (v / max) * 500;
  const over = bid >= sale;
  return (
    <svg role="img" aria-label={t("deep.bid.barLabel", { bid: money(bid, lng), sale: money(sale, lng) })} viewBox="0 0 520 100" className="w-full">
      <line x1="10" y1="50" x2="510" y2="50" stroke="rgb(var(--nx-ink) / 0.15)" strokeWidth="6" strokeLinecap="round" />
      <rect x="10" y="38" width={x(bid) - 10} height="24" rx="5" fill={over ? "rgb(var(--nx-pill-green) / 0.35)" : "rgb(var(--nx-pill-red) / 0.3)"} />
      <line x1={x(sale)} y1="30" x2={x(sale)} y2="70" stroke="rgb(var(--nx-ink))" strokeWidth="2" strokeDasharray="3 3" />
      <text x={x(sale)} y="22" fontSize="12" textAnchor="middle" fill="rgb(var(--nx-ink))">{t("deep.bid.lastSale", { sale: money(sale, lng) })}</text>
      <path d={`M${x(bid)} 34 l8 12 l-8 12 l-8 -12 Z`} fill="rgb(var(--nx-ink))" />
      <text x={Math.min(x(bid), 470)} y="88" fontSize="12" fontWeight="600" textAnchor="middle" fill="rgb(var(--nx-ink))">{t("deep.bid.ceiling", { bid: money(bid, lng) })}</text>
    </svg>
  );
}

/** The project on screen: chosen from a list (the ready-made ones, then the builder's own, each with its bid), its
    limits as rings and its − / +. One panel instead of a card per project (owner, 2026-11-16). */
function ProjectPanel({ project, focusKey, options, owns, inputs, onPick, onStep, onSaveNew, onRemove, backTo, onBack }: {
  project: Project; focusKey: CardKey; options: ProjectOption[]; owns: OwnProject[]; inputs: DeepInputs;
  onPick: (k: CardKey) => void; onStep: (field: "units" | "floors" | "floorAreaSqft", d: 1 | -1) => void;
  onSaveNew: () => void; onRemove: (id: string) => void; backTo: PresetKind | null; onBack: (k: CardKey) => void;
}) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const loc = lng.startsWith("es") ? "es-MX" : "en-US";
  const nameOf = (o: ProjectOption) => (o.own ? t("deep.projects.kind.ownN", { n: o.n, units: o.project.units }) : t(`deep.projects.kind.${o.project.kind}`, { units: o.project.units }));
  const current = options.find((o) => o.key === focusKey) ?? options[0];
  const uses = limitUse(project, inputs);
  const over = uses.some((u) => u.over);
  const ring = (key: "floorArea" | "height" | "units") => {
    const u = uses.find((x) => x.key === key)!;
    if (u.share == null) return null;
    const v = Math.round(u.share * 100);
    return (
      <div className="flex flex-col items-center gap-1">
        <ScoreRing value={v} max={100} size={56} label={t(`deep.projects.ring.${key}`, { v })} inkClass={u.over ? "text-nx-pill-red" : "text-nx-ink"} />
        <span className="nx-muted text-[0.6875rem]">{t(`deep.projects.ringShort.${key}`)}</span>
      </div>
    );
  };
  const full = owns.length >= MAX_OWN;
  return (
    <section className="flex flex-col gap-4 rounded-2xl bg-nx-block p-6" aria-labelledby="deep-project-h" data-testid="deep-project">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 id="deep-project-h" className="font-semibold">{t("deep.projects.title")}</h3>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger aria-label={t("deep.projects.choose", { name: nameOf(current) })} data-testid="deep-project-menu"
            className="flex items-center gap-2 rounded-full px-4 py-2 font-semibold ring-1 ring-inset ring-nx-ink/25 hover:bg-nx-ink/5 touch-target">
            {nameOf(current)}<ChevronDown aria-hidden className="h-4 w-4" />
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <div className="ui-next">
              <DropdownMenu.Content align="end" sideOffset={6} className={MENU} data-testid="deep-project-list">
                <DropdownMenu.RadioGroup value={focusKey} onValueChange={onPick}>
                  {options.map((o, i) => (
                    <div key={o.key}>
                      {i === options.findIndex((x) => x.own) && (
                        <><DropdownMenu.Separator className="my-1 h-px bg-nx-ink/10" />
                          <DropdownMenu.Label className="nx-muted px-2.5 py-1 text-caption">{t("deep.projects.yours")}</DropdownMenu.Label></>
                      )}
                      <div className="flex items-center gap-1">
                        <DropdownMenu.RadioItem value={o.key} className={`${MENU_ITEM} flex-1 justify-between ${PICKED}`} data-testid={`deep-option-${o.key}`}>
                          <span>{nameOf(o)}</span>
                          <span className="tabular-nums opacity-80">{o.bid > 0 ? money(o.bid, lng) : t("deep.bid.none")}</span>
                        </DropdownMenu.RadioItem>
                        {o.own && (
                          <DropdownMenu.Item aria-label={t("deep.projects.remove", { n: o.n })} onSelect={(e) => { e.preventDefault(); onRemove(o.own!.id); }}
                            className={`${MENU_ITEM} px-2`} data-testid="deep-own-remove">
                            <X aria-hidden className="h-4 w-4" />
                          </DropdownMenu.Item>
                        )}
                      </div>
                    </div>
                  ))}
                </DropdownMenu.RadioGroup>
                <DropdownMenu.Separator className="my-1 h-px bg-nx-ink/10" />
                <DropdownMenu.Item disabled={full} onSelect={onSaveNew} className={MENU_ITEM} data-testid="deep-project-save">
                  <Plus aria-hidden className="h-4 w-4" />{full ? t("deep.projects.ownFull", { n: MAX_OWN }) : t("deep.projects.save")}
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </div>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
      <p className="nx-muted text-caption">{t("deep.projects.size", { area: project.floorAreaSqft.toLocaleString(loc), floors: project.floors })}</p>
      <div className="flex items-start justify-around gap-3">{ring("floorArea")}{ring("units")}{ring("height")}</div>
      <div className="flex items-center justify-between gap-2 text-caption">
        <span className="nx-muted">{t("deep.projects.rings")}</span>
        {over ? <Pill tone="red">{t("deep.projects.over")}</Pill> : <Pill tone="green">{t("deep.projects.fits")}</Pill>}
      </div>
      <div className="flex flex-col gap-2 border-t border-nx-ink/10 pt-3" data-testid="deep-steppers">
        <Stepper label={t("deep.projects.units")} value={String(project.units)} onStep={(d) => onStep("units", d)} />
        <Stepper label={t("deep.projects.floors")} value={String(project.floors)} onStep={(d) => onStep("floors", d)} />
        <Stepper label={t("deep.projects.floorArea")} value={project.floorAreaSqft.toLocaleString(loc)} onStep={(d) => onStep("floorAreaSqft", d)} />
      </div>
      {backTo && (
        <button type="button" onClick={() => onBack(backTo)} className="nx-muted self-start text-caption underline touch-target" data-testid="deep-project-back">
          {t("deep.projects.back", { name: t(`deep.projects.name.${backTo}`) })}
        </button>
      )}
    </section>
  );
}

const MENU = "z-[70] min-w-[260px] rounded-2xl bg-nx-page p-1.5 text-body text-nx-ink shadow-[0_8px_32px_rgb(0_0_0/0.14)] ring-1 ring-nx-ink/10";
const MENU_ITEM = "flex cursor-pointer select-none items-center gap-2 rounded-xl px-2.5 py-1.5 outline-none data-[highlighted]:bg-nx-ink/5 data-[disabled]:cursor-default data-[disabled]:opacity-60";
/** The project on screen in the list: one deep violet in both themes (owner, 2026-11-16: "a darker purple"; the
    light theme's Pro/Saved lavender ink, 91 93 184), white on it (contrast 5.7:1; 7.1:1 highlighted). */
const PICKED = "data-[state=checked]:bg-[rgb(91_93_184)] data-[state=checked]:font-semibold data-[state=checked]:text-white data-[state=checked]:data-[highlighted]:bg-[rgb(76_78_165)]";

function Stepper({ label, value, onStep }: { label: string; value: string; onStep: (d: 1 | -1) => void }) {
  const { t } = useTranslation("next");
  return (
    <div className="flex items-center gap-2 text-caption">
      <span className="nx-muted flex-1">{label}</span>
      <button type="button" aria-label={t("deep.projects.less", { what: label })} onClick={() => onStep(-1)} className="grid h-9 w-9 place-items-center rounded-full ring-1 ring-inset ring-nx-ink/25 hover:bg-nx-ink/5 touch-icon"><Minus aria-hidden className="h-4 w-4" /></button>
      <b className="min-w-[3.5rem] text-center tabular-nums" aria-live="polite">{value}</b>
      <button type="button" aria-label={t("deep.projects.more", { what: label })} onClick={() => onStep(1)} className="grid h-9 w-9 place-items-center rounded-full ring-1 ring-inset ring-nx-ink/25 hover:bg-nx-ink/5 touch-icon"><Plus aria-hidden className="h-4 w-4" /></button>
    </div>
  );
}

/** One number: a slider with its range drawn under it (when the source gives one) and where it came from. */
function Slider({ label, value, min, max, stepBy, show, source, hint, onChange }: {
  label: string; value: number; min: number; max: number; stepBy: number; show: string; source: NumberSource; hint?: string; onChange: (v: number) => void;
}) {
  const id = useId();
  const band = source.kind === "assumption" ? [source.low, source.high]
    : source.kind === "census_rent" && source.moe ? [value - source.moe, value + source.moe]
    : source.kind === "new_construction" ? [source.low * source.unitSqft, source.high * source.unitSqft] : null;
  const at = (v: number) => `${Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100))}%`;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id}>{label}</label>
        <b className="tabular-nums">{show}</b>
      </div>
      <div className="relative">
        {band && (
          <span aria-hidden className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded bg-nx-pill-blue/35" style={{ left: at(band[0]), width: `calc(${at(band[1])} - ${at(band[0])})` }} />
        )}
        <input id={id} type="range" min={min} max={max} step={stepBy} value={value} onChange={(e) => onChange(Number(e.target.value))}
          className="relative w-full accent-[rgb(var(--nx-ink))]" aria-valuetext={show} />
      </div>
      <SourceLine source={source} hint={hint} />
    </div>
  );
}

function SourceLine({ source, hint }: { source: NumberSource; hint?: string }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  let text: string;
  switch (source.kind) {
    case "lot_sale": text = t("deep.src.lotSale", { date: source.date.slice(0, 4) }); break;
    case "new_construction": {
      const loc = lng.startsWith("es") ? "es-MX" : "en-US";
      text = t("deep.src.newConstruction", { perSqft: money(source.perSqft, lng, { short: false }), unitSqft: source.unitSqft.toLocaleString(loc),
        years: source.years.join("–"), n: source.n.toLocaleString(loc), premium: source.premium.toLocaleString(loc, { maximumFractionDigits: 2 }) });
      if (source.pooled) text += t("deep.src.newConstructionPooled");
      if (!source.newSales) text += t("deep.src.newConstructionCarried");
      break;
    }
    case "area_sales": text = t(`deep.src.areaSales.${source.group}`, { year: source.year, n: source.n.toLocaleString(lng.startsWith("es") ? "es-MX" : "en-US") }); break;
    case "census_rent": text = t("deep.src.census", { beds: t(`deep.beds.${source.bedrooms}`), scope: t(`deep.scope.${source.scope}`), period: source.period ?? "", moe: source.moe ? money(source.moe, lng, { short: false }) : "—" }); break;
    case "hud_rent": text = t("deep.src.hud", { beds: t(`deep.beds.${source.bedrooms}`), fy: source.fy }); break;
    case "tax_rate": text = t("deep.src.taxRate", { year: source.year ?? "" }); break;
    case "chicago_tax_rate": text = t("deep.src.chicagoTax"); break;
    case "assumption": text = t(`deep.src.assumption.${source.source}`, { asOf: source.asOf }); break;
    default: text = t("deep.src.none");
  }
  return <span className="nx-muted text-[0.6875rem]">{text}{hint ? ` · ${hint}` : ""}</span>;
}

/** If things move: the land bid with price and build cost each 10% lower, as set, higher. Red = below the last sale. */
function StressGrid({ grid, sale, lng, mode }: { grid: number[][]; sale: number | null; lng: string; mode: Mode }) {
  const { t } = useTranslation("next");
  const head = (d: number) => (d === 0 ? t("deep.stress.asSet") : `${d > 0 ? "+" : "−"}${Math.abs(d * 100)}%`);
  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-nx-block p-6" data-testid="deep-stress">
      <h3 className="text-center font-semibold">{t("deep.stress.title")}</h3>
      <table className="w-full border-separate border-spacing-1.5 text-center tabular-nums">
        <caption className="sr-only">{t("deep.stress.caption")}</caption>
        <thead>
          <tr>
            <th scope="col" className="nx-muted text-left text-caption font-normal">{t(mode === "sell" ? "deep.stress.axesSell" : "deep.stress.axesRent")}</th>
            {STRESS_STEPS.map((d) => <th key={d} scope="col" className="text-caption font-medium">{head(d)}</th>)}
          </tr>
        </thead>
        <tbody>
          {grid.map((row, i) => (
            <tr key={i}>
              <th scope="row" className="text-left text-caption font-medium">{head(STRESS_STEPS[i])}</th>
              {row.map((v, j) => {
                const center = i === 1 && j === 1;
                const low = v <= 0 || (sale != null && v < sale);
                return (
                  <td key={j} className={`rounded-xl px-2 py-2.5 ${center ? "bg-nx-ink font-semibold text-nx-page" : low ? "bg-nx-pill-red-bg text-nx-pill-red" : "bg-nx-stat-a text-nx-card-ink"}`}>
                    {v > 0 ? money(v, lng) : t("deep.bid.none")}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="nx-muted text-center text-caption">{t(sale != null ? "deep.stress.legend" : "deep.stress.legendNoSale", { sale: sale != null ? money(sale, lng) : "" })}</p>
    </div>
  );
}
