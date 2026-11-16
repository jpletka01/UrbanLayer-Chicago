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
import { BadgeCheck, Calculator, ChartColumnBig, LayoutGrid, LoaderCircle, LogIn, MapPin, Minus, Plus, Scale } from "lucide-react";
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

  const [project, setProject] = useState<Project | null>(() => {
    const s = saved?.project;
    if (s) return { kind: s.kind, units: s.units, floors: s.stories, floorAreaSqft: s.floor_area_sqft };
    return starts[0] ?? null;
  });
  const [mode, setMode] = useState<Mode>(() => (saved?.numbers?.mode === "rent" ? "rent" : "sell"));
  const base = useMemo(() => (project ? startingNumbers(inputs, project) : null), [inputs, project]);
  const [edits, setEdits] = useState<Partial<Numbers>>(() => {
    const n = saved?.numbers ?? {};
    const out: Partial<Numbers> = {};
    const map: Record<string, keyof Numbers> = {
      land_price: "landPrice", sale_price_unit: "salePriceUnit", rent_unit_month: "rentUnitMonth", build_cost_sqft: "buildCostSqft",
      soft_cost_pct: "softCostPct", loan_to_cost: "loanToCost", loan_rate: "loanRate", build_months: "buildMonths",
      selling_pct: "sellingPct", profit_on_cost: "profitOnCost", vacancy_pct: "vacancyPct", opex_pct: "opexPct",
      cap_rate: "capRate", target_yield: "targetYield", tax_rate: "taxRate",
    };
    for (const [k, v] of Object.entries(n)) if (map[k] && typeof v === "number") (out as Record<string, number>)[map[k]] = v;
    return out;
  });
  const numbers: Numbers | null = base ? { ...base.numbers, ...edits } : null;

  // The project on the map.
  useEffect(() => {
    if (!project) { onProject(null); return; }
    const m = projectMass(project, inputs);
    onProject({ ...m, label: t("deep.map.label", { units: project.units, floors: project.floors }) });
  }, [project, inputs, onProject, t]);
  useEffect(() => () => onProject(null), [onProject]);

  // Saved to the account, a moment after the last change (the server keeps one row per lot).
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    if (!project) return;
    const id = window.setTimeout(() => {
      const snake: Record<string, number> = {};
      const back: Record<keyof Numbers, string> = {
        landPrice: "land_price", salePriceUnit: "sale_price_unit", rentUnitMonth: "rent_unit_month", buildCostSqft: "build_cost_sqft",
        softCostPct: "soft_cost_pct", loanToCost: "loan_to_cost", loanRate: "loan_rate", buildMonths: "build_months",
        sellingPct: "selling_pct", profitOnCost: "profit_on_cost", vacancyPct: "vacancy_pct", opexPct: "opex_pct",
        capRate: "cap_rate", targetYield: "target_yield", taxRate: "tax_rate",
      };
      for (const [k, v] of Object.entries(edits)) if (typeof v === "number") snake[back[k as keyof Numbers]] = v;
      putDeepProject(pin, {
        project: { kind: project.kind, units: project.units, stories: project.floors, floor_area_sqft: project.floorAreaSqft },
        numbers: snake, mode, step: saved?.step ?? 0,
      }).catch(() => { /* a failed save keeps the page as it is; the next change tries again */ });
    }, 800);
    return () => window.clearTimeout(id);
  }, [pin, project, edits, mode, saved?.step]);

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
  const set = (k: keyof Numbers, v: number) => setEdits((e) => ({ ...e, [k]: v }));

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

      {/* 2 · the projects, with their limits as rings */}
      <section className="flex flex-col gap-3" aria-label={t("deep.projects.label")}>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {starts.map((p) => (
            <ProjectCard key={p.kind} p={p} inputs={inputs} numbers={startingNumbers(inputs, p).numbers} edits={edits} mode={mode}
              selected={project.kind === p.kind} onPick={() => setProject(p)} />
          ))}
          <ProjectCard p={project.kind === "own" ? project : null} inputs={inputs} numbers={numbers} edits={edits} mode={mode}
            selected={project.kind === "own"} onPick={() => setProject((cur) => ({ ...(cur ?? starts[0]), kind: "own" }))} own />
        </div>
        <div className="flex flex-wrap justify-center gap-x-7 gap-y-3" data-testid="deep-steppers">
          <Stepper label={t("deep.projects.units")} value={String(project.units)} onStep={(d) => setProject(step(project, "units", d))} />
          <Stepper label={t("deep.projects.floors")} value={String(project.floors)} onStep={(d) => setProject(step(project, "floors", d))} />
          <Stepper label={t("deep.projects.floorArea")} value={project.floorAreaSqft.toLocaleString(lng.startsWith("es") ? "es-MX" : "en-US")} onStep={(d) => setProject(step(project, "floorAreaSqft", d))} />
        </div>
      </section>

      {/* 3 · your numbers, sourced; and if things move */}
      <section className="nx-cq grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-4 rounded-2xl bg-nx-block p-6">
          <h3 className="text-center font-semibold">{t("deep.numbers.title")}</h3>
          <Slider label={t("deep.numbers.land")} value={numbers.landPrice ?? 0} min={0} max={Math.max(3_000_000, (numbers.landPrice ?? 0) * 2)} stepBy={10_000}
            show={money(numbers.landPrice ?? 0, lng)} source={base.sources.landPrice} onChange={(v) => set("landPrice", v)} />
          {mode === "sell"
            ? <Slider label={t("deep.numbers.sale")} value={numbers.salePriceUnit} min={100_000} max={Math.max(1_500_000, numbers.salePriceUnit * 2)} stepBy={5_000}
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
          {Object.keys(edits).length > 0 && (
            <button type="button" onClick={() => setEdits({})} className="nx-muted self-center text-caption underline touch-target">{t("deep.numbers.reset")}</button>
          )}
        </div>
        <StressGrid grid={grid} sale={sale?.price ?? null} lng={lng} mode={mode} />
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

function ProjectCard({ p, inputs, numbers, edits, mode, selected, onPick, own = false }: {
  p: Project | null; inputs: DeepInputs; numbers: Numbers; edits: Partial<Numbers>; mode: Mode; selected: boolean; onPick: () => void; own?: boolean;
}) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  if (own && !p) {
    return (
      <button type="button" aria-pressed={selected} onClick={onPick}
        className="flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-nx-card-ink/30 bg-nx-stat-a p-5 text-nx-card-ink touch-target" data-testid="deep-project-own">
        <Plus aria-hidden className="h-6 w-6" strokeWidth={1.75} />
        <b className="font-semibold">{t("deep.projects.own")}</b>
        <span className="text-caption opacity-70">{t("deep.projects.ownNote")}</span>
      </button>
    );
  }
  const proj = p!;
  const n = { ...numbers, ...edits };
  const r = compute(proj, n, mode);
  const uses = limitUse(proj, inputs);
  const over = uses.some((u) => u.over);
  const ring = (key: "floorArea" | "height") => {
    const u = uses.find((x) => x.key === key)!;
    if (u.share == null) return null;
    const v = Math.round(u.share * 100);
    return <ScoreRing value={v} max={100} size={48} label={t(`deep.projects.ring.${key}`, { v })} inkClass={u.over ? "text-nx-pill-red" : "text-nx-card-ink"} />;
  };
  return (
    <button type="button" aria-pressed={selected} onClick={onPick}
      className={`nx-on-card flex flex-col gap-3 rounded-2xl p-5 text-left text-nx-card-ink touch-target ${proj.kind === "three_flat" ? "bg-nx-stat-b" : "bg-nx-stat-a"} ${selected ? "ring-2 ring-nx-card-ink" : ""}`}
      data-testid={`deep-project-${proj.kind}`} data-selected={selected || undefined}>
      <div className="flex items-baseline justify-between gap-2">
        <b className="font-semibold">{t(`deep.projects.kind.${proj.kind}`, { units: proj.units })}</b>
        <span className="text-caption opacity-70">{t("deep.projects.size", { area: proj.floorAreaSqft.toLocaleString(lng.startsWith("es") ? "es-MX" : "en-US"), floors: proj.floors })}</span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-caption opacity-70">{t("deep.bid.label")}</div>
          <div className="text-[1.5rem] font-semibold tabular-nums">{r.landBid > 0 ? money(r.landBid, lng) : t("deep.bid.none")}</div>
          <div className="text-[0.6875rem] opacity-70">{mode === "sell"
            ? t("deep.projects.atSale", { price: money(n.salePriceUnit, lng) })
            : t("deep.projects.atRent", { price: money(n.rentUnitMonth, lng, { short: false }) })}</div>
        </div>
        <div className="flex items-center gap-2">{ring("floorArea")}{ring("height")}</div>
      </div>
      <div className="flex items-center justify-between gap-2 text-caption">
        <span className="opacity-75">{t("deep.projects.rings")}</span>
        {over ? <Pill tone="red">{t("deep.projects.over")}</Pill> : <Pill tone="green">{t("deep.projects.fits")}</Pill>}
      </div>
    </button>
  );
}

function Stepper({ label, value, onStep }: { label: string; value: string; onStep: (d: 1 | -1) => void }) {
  const { t } = useTranslation("next");
  return (
    <div className="flex items-center gap-2">
      <span className="nx-muted">{label}</span>
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
