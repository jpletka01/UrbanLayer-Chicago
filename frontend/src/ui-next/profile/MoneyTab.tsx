// Money tab (brief "Property Profile", Money: "What would it cost or earn?"; decision Item 99). The tab shape of
// every Profile tab in SnowUI's look (Item 74): the takeaway sentence → a row of stat tiles, one key figure each
// (property tax as a number, the Assessor's value, the nearby sales' median, rent for this building's unit size)
// → one wide chart block (the nearby market sales as bars, their search as chips; the same sales are the map's
// pins) → three smaller blocks (the Assessor's value by year, rent by bedroom count, incentives) → a collapsed
// details table. Ordinary bars are Sapphire, this lot is black (white in dark). Titles define themselves through
// `Term` (a definition and "Ask about this"), never on the page. Where the tax bill goes is not shown (cut by
// design 2026-07-07: builders care what they pay; the CSV and the report keep it). Blocks that read a late part
// follow Item 89's skeleton rule. No figure here is a forecast (rule 11).
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, ChevronRight, LoaderCircle, MapPin, RotateCw, TriangleAlert } from "lucide-react";
import type { ScorecardResponse } from "../../lib/api";
import { ConfidenceState } from "../../components/ui/ConfidenceState";
import { Block, Pill, StatTile, type PillTone } from "../ui/Blocks";
import { Term } from "../ui/Term";
import { ColumnChart } from "../ui/ColumnChart";
import { useAskHandoff } from "../ask/askContext";
import { ICON, STROKE } from "../icons";
import { numLocale, type FigureState } from "./profileModel";
import {
  assessorBelowSale, compsModel, niceCeil, moneySentence, usd, incentiveChips, rentModel, taxModel, valueHistory,
  type CompsModel, type IncentiveAnswer, type LateBlockState, type RentModel, type ValueYear,
} from "./moneyModel";

const usdShort = (n: number, lng: string) =>
  new Intl.NumberFormat(numLocale(lng), { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(n);
const pct = (f: number, digits = 2) => (f * 100).toFixed(digits);
const monthYear = (iso: string | null, lng: string) =>
  iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString(numLocale(lng), { month: "short", year: "numeric" }) : "—";
const stateOf = (s: FigureState) => (s ? <ConfidenceState kind={s.kind} low={s.low} /> : undefined);

export function MoneyTab({
  data,
  late,
  onRetry,
}: {
  data: ScorecardResponse;
  /** Where each late part this tab reads stands: `money` (nearby sales), `incentives` (QCT, NMTC), `neighborhood` (rent). */
  late: { money: LateBlockState; incentives: LateBlockState; neighborhood: LateBlockState };
  onRetry: (part: "money" | "incentives" | "neighborhood") => void;
}) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const ask = useAskHandoff();
  const q = (key: string) => t(`profile.money.ask.${key}`, { address: ask?.address ?? "" });
  const def = (key: string) => t(`profile.money.define.${key}`);
  const tax = taxModel(data);
  const comps = compsModel(data);
  const history = valueHistory(data);
  const flag = assessorBelowSale(data);
  const rent = rentModel(data);
  const chips = incentiveChips(data, late.incentives);
  const prop = data.context?.property;
  const inc = data.context?.incentives;
  const latestYear = history.years.length ? history.years[history.years.length - 1].year : null;
  const sizeBar = rent?.thisSize ? rent.bars.find((b) => b.key === rent.thisSize) : null;

  return (
    <div className="flex flex-col gap-7" data-testid="money-tab">
      <p className="text-nx-answer" data-testid="money-sentence">{moneySentence(data, t, lng)}</p>

      <ul className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:gap-7 xl:grid-cols-4" data-testid="money-tiles">
        <StatTile
          testId="tile-tax" tone="a"
          label={<Term label={t("profile.tiles.tax")} definition={def("tax")} question={q("tax")} />}
          figure={tax.kind === "bill" ? usd(tax.tax!, lng) : tax.kind === "exempt" ? t("profile.tiles.exempt") : "—"}
          unit={tax.kind === "bill" ? t("profile.tiles.perYear") : undefined}
          note={tax.kind === "bill"
            ? [tax.year ? t("profile.money.tax.billYear", { year: tax.year }) : null,
               tax.rate != null ? (tax.typicalRate != null ? t("profile.money.tax.rateVsTypical", { rate: pct(tax.rate), typical: pct(tax.typicalRate, 1) }) : t("profile.tiles.taxRate", { rate: pct(tax.rate) })) : null,
              ].filter(Boolean).join(" · ")
            : tax.kind === "exempt" && tax.typicalRate == null ? t("profile.money.tax.exemptNoRate")
            : t(`profile.money.tax.${tax.kind}Short`, { rate: tax.typicalRate != null ? pct(tax.typicalRate, 1) : "" })}
          state={tax.kind === "bill" ? stateOf(tax.state) : undefined}
        />
        <StatTile
          testId="tile-value" tone="b"
          label={<Term label={t("profile.money.value.label")} definition={def("value")} question={q("value")} />}
          figure={tax.marketValue != null ? usd(tax.marketValue, lng) : "—"}
          note={latestYear ? t("profile.money.value.year", { year: latestYear }) : undefined}
          warning={flag ? (
            <span className="flex items-start gap-1" data-testid="assessor-flag">
              <TriangleAlert aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={2} />
              {t("profile.money.tax.belowSale", { pct: flag.pctBelow, year: flag.saleYear })}
            </span>
          ) : undefined}
        />
        <StatTile
          testId="tile-sales" tone="a"
          label={<Term label={t("profile.money.sales.median")} definition={def("sales")} question={q("sales")} />}
          checking={late.money === "loading"}
          figure={comps && comps.median != null && !comps.medianWithheld ? usd(comps.median, lng) : "—"}
          note={late.money === "loading" ? t("profile.money.checking", { what: t("profile.parts.part.money") })
            : comps ? t("profile.money.sales.tileNote", { count: comps.rule.n, mi: comps.rule.radiusMi?.toLocaleString(numLocale(lng)) ?? "—" }) : undefined}
          state={late.money === "ready" && comps ? stateOf(comps.medianState) : undefined}
        />
        <StatTile
          testId="tile-rent" tone="b"
          label={<Term label={sizeBar ? t("profile.money.rent.tileSize", { size: t(`profile.money.rent.bed.${sizeBar.key}`).toLowerCase() }) : t("profile.money.rent.title")} definition={def("rent")} question={q("rent")} />}
          checking={late.neighborhood === "loading"}
          figure={sizeBar?.rent != null ? usd(sizeBar.rent, lng) : rent?.area ? usd(rent.area.rent, lng) : "—"}
          unit={sizeBar?.rent != null || rent?.area ? t("profile.money.rent.aMonth") : undefined}
          note={late.neighborhood === "loading" ? t("profile.money.checking", { what: t("profile.money.rent.what") })
            : sizeBar?.rent != null ? t("profile.money.rent.tileNoteSize") : rent?.area ? t("profile.money.rent.tileNoteArea") : t("profile.money.rent.notChecked")}
          state={late.neighborhood === "ready" && (sizeBar?.rent != null || rent?.area) ? <ConfidenceState kind="estimate" low={false} /> : undefined}
        />
      </ul>

      <Block
        title={<Term label={t("profile.money.sales.title")} definition={def("sales")} question={q("sales")} />}
        icon={ICON.sale}
        labelledBy="nx-sales"
        aside={late.money === "ready" && comps && comps.sales.length > 0 ? (
          <span className="inline-flex items-center gap-1"><MapPin aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{t("profile.money.sales.onMap")}</span>
        ) : undefined}
      >
        <LateSlot state={late.money} what={t("profile.parts.part.money")} onRetry={() => onRetry("money")} skeleton={<BarsSkeleton rows={4} />}>
          {comps ? <SalesBody comps={comps} /> : <p className="nx-muted">{t("profile.money.sales.none")}</p>}
        </LateSlot>
      </Block>

      <div className="grid items-start gap-7 md:grid-cols-2 xl:grid-cols-3">
        <Block title={<Term label={t("profile.money.tax.valueOverTime")} definition={def("value")} question={q("value")} />}
          icon={ICON.valueOverTime} labelledBy="nx-value">
          {history.years.length > 0 ? <ValueColumns years={history.years} /> : <p className="nx-muted">{t("profile.money.value.none")}</p>}
        </Block>

        <Block title={<Term label={t("profile.money.rent.title")} definition={def("rent")} question={q("rent")} />}
          icon={ICON.rent} labelledBy="nx-rent"
          aside={rent?.period ? t("profile.money.rent.census", { period: rent.period }) : undefined}>
          <LateSlot state={late.neighborhood} what={t("profile.money.rent.what")} onRetry={() => onRetry("neighborhood")} skeleton={<BarsSkeleton rows={3} />}>
            <RentBody rent={rent} />
          </LateSlot>
        </Block>

        <Block title={<Term label={t("profile.money.incentives.title")} definition={def("incentives")} question={q("incentives")} />}
          icon={ICON.incentives} labelledBy="nx-incentives">
          <ul className="flex flex-wrap gap-2" data-testid="incentive-chips">
            {chips.map((c) => (
              <li key={c.key} data-incentive={c.key} data-answer={c.answer}>
                {/* The whole chip opens the program's page in the right panel (owner: pills should be clickable). */}
                <button
                  type="button"
                  onClick={() => ask?.openProgram?.(c.key)}
                  disabled={!ask?.openProgram}
                  className="group flex items-center gap-1.5 rounded-xl bg-nx-page py-1.5 pl-2.5 pr-1.5 text-left hover:bg-nx-ink/5 disabled:cursor-default touch-target"
                  aria-haspopup="dialog"
                >
                  <span className="text-caption">{t(`profile.money.incentives.program.${c.key}`)}</span>
                  <IncentivePill answer={c.answer} />
                  <ChevronRight aria-hidden className="h-3.5 w-3.5 nx-muted transition-transform group-hover:translate-x-0.5" strokeWidth={STROKE} />
                </button>
              </li>
            ))}
          </ul>
          {late.incentives === "timedOut" || late.incentives === "failed" ? (
            <RetryLine state={late.incentives} what={t("profile.parts.part.incentives")} onRetry={() => onRetry("incentives")} />
          ) : null}
          <p className="text-caption nx-muted">
            {inc?.property_tax_class && inc.property_tax_class !== "standard"
              ? t("profile.money.incentives.classIncentive")
              : t("profile.money.incentives.standardClass")}
          </p>
        </Block>
      </div>

      <details className="group rounded-2xl bg-nx-block p-5 sm:p-6" data-testid="money-details">
        <summary className="flex cursor-pointer list-none items-center gap-2 font-semibold">
          <ChevronDown aria-hidden className="h-4 w-4 transition-transform group-open:rotate-180" strokeWidth={STROKE} />
          {t("profile.money.details.title")}
        </summary>
        <table className="mt-4 w-full text-caption">
          <tbody>
            {([
              [t("profile.money.details.assessed"), prop?.total_assessed_value != null ? usd(prop.total_assessed_value, lng) : "—"],
              [t("profile.money.details.level"), prop?.assessment_level != null ? `${pct(prop.assessment_level, 0)}%` : "—"],
              [t("profile.money.details.marketValue"), tax.marketValue != null ? usd(tax.marketValue, lng) : "—"],
              ...history.years.slice().reverse().map((y) => [t("profile.money.details.valueYear", { year: y.year }), t("profile.money.details.landBuilding", { total: usd(y.total, lng), land: usd(y.land, lng), building: usd(y.building, lng) })] as const),
              [t("profile.money.details.rate"), tax.rate != null ? `${pct(tax.rate)}%` : "—"],
              [t("profile.money.details.typicalRate"), tax.typicalRate != null ? `${pct(tax.typicalRate, 1)}%` : "—"],
              [t("profile.money.details.exemptions"), tax.exemptions.length ? tax.exemptions.join(", ") : t("profile.money.details.noneOnBill")],
              [t("profile.money.details.taxCode"), prop?.tax_code || "—"],
              [t("profile.money.details.classNote"), inc?.tax_incentive_description || "—"],
            ] as Array<readonly [string, string]>).map(([k, v], i) => (
              <tr key={`${k}-${i}`} className="border-b border-nx-ink/5 last:border-0">
                <th scope="row" className="py-2 pr-4 text-left font-normal nx-muted">{k}</th>
                <td className="py-2 tabular-nums">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {comps && comps.sales.length > SALES_SHOWN && (
          <>
            <h4 className="mt-6 font-semibold">{t("profile.money.details.allSales", { count: comps.sales.length })}</h4>
            <SalesList sales={comps.sales} />
          </>
        )}
      </details>
    </div>
  );
}

// ── Late slots (Item 89's skeleton rule) ───────────────────────────────────────────────────────────────

function LateSlot({ state, what, onRetry, skeleton, children }: {
  state: LateBlockState; what: string; onRetry: () => void; skeleton: ReactNode; children: ReactNode;
}) {
  const { t } = useTranslation("next");
  if (state === "loading") {
    return (
      <div aria-busy="true" className="flex flex-col gap-3">
        <p className="flex items-center gap-2 text-caption nx-muted" role="status">
          <LoaderCircle aria-hidden className="h-3.5 w-3.5 animate-spin" strokeWidth={STROKE} />
          {t("profile.money.checking", { what })}
        </p>
        {skeleton}
      </div>
    );
  }
  if (state === "timedOut" || state === "failed") return <RetryLine state={state} what={what} onRetry={onRetry} />;
  return <>{children}</>;
}

function RetryLine({ state, what, onRetry }: { state: "timedOut" | "failed"; what: string; onRetry: () => void }) {
  const { t } = useTranslation("next");
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption" role={state === "failed" ? "alert" : undefined} data-late={state}>
      <TriangleAlert aria-hidden className="h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} />
      {state === "timedOut" ? t("profile.parts.timedOut", { list: what }) : t("profile.parts.failed", { list: what })}
      <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 underline underline-offset-2 touch-target">
        <RotateCw aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
        {t("profile.parts.retry")}
      </button>
    </p>
  );
}

const pulse = "block rounded bg-nx-ink/10 motion-safe:animate-pulse";

function BarsSkeleton({ rows }: { rows: number }) {
  return (
    <div aria-hidden className="flex flex-col gap-3">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="grid grid-cols-[4.5rem_1fr] items-center gap-3">
          <span className={`${pulse} h-3`} />
          <span className={`${pulse} h-3`} style={{ width: `${80 - i * 14}%` }} />
        </div>
      ))}
    </div>
  );
}

// ── Nearby sales ───────────────────────────────────────────────────────────────────────────────────────

const SALES_SHOWN = 6;

/** The nearby sales as one bar each (price on a shared scale, newest first), the median a dashed line across them;
    Sapphire bars, since none of them is this lot. The search that chose them sits above as chips. */
function SalesBody({ comps }: { comps: CompsModel }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const r = comps.rule;
  const ruleChips = [
    r.classGroup ? t("profile.money.sales.rule.class", { group: r.classGroup }) : null,
    r.radiusMi != null ? t("profile.money.sales.rule.radius", { mi: r.radiusMi.toLocaleString(numLocale(lng)) }) : null,
    r.years != null ? t("profile.money.sales.rule.years", { count: r.years }) : null,
    t("profile.money.sales.rule.count", { count: r.n }),
  ].filter((c): c is string => !!c);
  const shown = comps.sales.slice(0, SALES_SHOWN);
  const max = Math.max(1, ...shown.map((s) => s.sale_price));
  const median = !comps.medianWithheld && comps.median != null && shown.length >= 3 ? comps.median : null;

  return (
    <div className="flex flex-col gap-5">
      <ul className="flex flex-wrap gap-2" aria-label={t("profile.money.sales.ruleLabel")} data-testid="sales-rule">
        {ruleChips.map((c) => <li key={c}><Pill tone="gray">{c}</Pill></li>)}
        {r.widened && <li><Pill tone="yellow">{t("profile.money.sales.rule.widened")}</Pill></li>}
      </ul>
      {comps.sales.length === 0 ? (
        <p className="nx-muted">{t("profile.money.sales.noneFound")}</p>
      ) : (
        <figure className="flex flex-col gap-2">
          <ul className="flex flex-col gap-2.5" data-testid="sales-bars">
            {shown.map((s) => (
              <li key={`${s.pin}-${s.sale_date}`} className="grid grid-cols-[4.75rem_minmax(0,1fr)_auto] items-center gap-x-3 text-caption sm:grid-cols-[5.5rem_minmax(0,1fr)_auto_5.5rem]">
                <span className="nx-muted whitespace-nowrap">{monthYear(s.sale_date, lng)}</span>
                <span className="relative h-5 rounded bg-nx-ink/5" role="img"
                  aria-label={t("profile.money.sales.barLabel", { date: monthYear(s.sale_date, lng), price: usd(s.sale_price, lng), distance: s.distance_mi != null ? s.distance_mi.toFixed(2) : "—" })}>
                  <span className="absolute inset-y-0 left-0 rounded bg-nx-chart-1" style={{ width: `${(s.sale_price / max) * 100}%` }} />
                  {median != null && <span aria-hidden className="absolute inset-y-[-3px] border-l-2 border-dashed border-nx-ink" style={{ left: `${(median / max) * 100}%` }} />}
                </span>
                <span className="font-semibold tabular-nums">{usdShort(s.sale_price, lng)}</span>
                <span className="hidden text-right tabular-nums nx-muted sm:block">
                  {s.distance_mi != null ? t("profile.money.miles", { mi: s.distance_mi.toFixed(2) }) : "—"}
                </span>
              </li>
            ))}
          </ul>
          <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-caption nx-muted">
            {median != null && <span className="inline-flex items-center gap-1.5"><span aria-hidden className="h-3 border-l-2 border-dashed border-nx-ink" />{t("profile.money.sales.medianIs", { median: usd(median, lng) })}</span>}
            {comps.perBuildable != null && !comps.perBuildableWithheld && (
              <span>{t("profile.money.sales.perBuildableIs", { value: usd(comps.perBuildable, lng) })}</span>
            )}
            {comps.sales.length > SALES_SHOWN && <span>{t("profile.money.sales.moreInDetails", { count: comps.sales.length - SALES_SHOWN })}</span>}
          </figcaption>
        </figure>
      )}
    </div>
  );
}

function SalesList({ sales }: { sales: CompsModel["sales"] }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  return (
    <table className="mt-2 w-full text-caption" data-testid="sales-list">
      <thead>
        <tr className="text-left nx-muted">
          <th scope="col" className="pb-2 font-normal">{t("profile.money.sales.col.date")}</th>
          <th scope="col" className="pb-2 font-normal">{t("profile.money.sales.col.price")}</th>
          <th scope="col" className="hidden pb-2 font-normal sm:table-cell">{t("profile.money.sales.col.buildable")}</th>
          <th scope="col" className="hidden pb-2 font-normal sm:table-cell">{t("profile.money.sales.col.district")}</th>
          <th scope="col" className="pb-2 text-right font-normal">{t("profile.money.sales.col.distance")}</th>
        </tr>
      </thead>
      <tbody>
        {sales.map((s) => (
          <tr key={`${s.pin}-${s.sale_date}`} className="border-t border-nx-ink/5">
            <td className="py-2 pr-3 whitespace-nowrap">{monthYear(s.sale_date, lng)}</td>
            <td className="py-2 pr-3 font-semibold tabular-nums">{usd(s.sale_price, lng)}</td>
            <td className="hidden py-2 pr-3 tabular-nums sm:table-cell">{s.price_per_buildable_sqft != null ? t("profile.money.perSqft", { value: usd(s.price_per_buildable_sqft, lng) }) : "—"}</td>
            <td className="hidden py-2 pr-3 sm:table-cell">{s.zone_class ?? "—"}</td>
            <td className="py-2 text-right tabular-nums whitespace-nowrap">{s.distance_mi != null ? t("profile.money.miles", { mi: s.distance_mi.toFixed(2) }) : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ── The Assessor's value by year ───────────────────────────────────────────────────────────────────────

/** The Assessor's value by year as SnowUI's column chart: hover a column for its value, click to keep it shown. */
function ValueColumns({ years }: { years: ValueYear[] }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const top = niceCeil(Math.max(...years.map((y) => y.total)));
  const last = years[years.length - 1];
  return (
    <figure className="flex flex-col gap-2">
      <ColumnChart
        testId="value-bars"
        ariaLabel={t("profile.money.tax.valueOverTime")}
        top={top}
        scale={[usdShort(top, lng), usdShort(top / 2, lng), usdShort(0, lng)]}
        columns={years.map((y) => ({
          key: String(y.year), tick: `’${String(y.year).slice(2)}`, label: String(y.year),
          value: y.total, valueText: usdShort(y.total, lng), highlight: y === last,
        }))}
      />
      <figcaption className="text-caption nx-muted">{t("profile.money.value.hint")}</figcaption>
    </figure>
  );
}

// ── Rent ───────────────────────────────────────────────────────────────────────────────────────────────

function RentBody({ rent }: { rent: RentModel | null }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  if (!rent) return <p className="nx-muted">{t("profile.money.rent.notChecked")}</p>;
  if (rent.unchecked) return <p className="nx-muted">{t("profile.money.rent.notChecked")}</p>;
  const max = Math.max(1, ...rent.bars.map((b) => b.rent ?? 0), rent.area?.rent ?? 0);
  const anyPuma = rent.bars.some((b) => b.scope === "puma" && b.rent != null);
  return (
    <div className="flex flex-col gap-4">
      <ul className="flex flex-col gap-3" data-testid="rent-bars">
        {rent.bars.map((b) => {
          const mine = b.key === rent.thisSize;
          const label = t(`profile.money.rent.bed.${b.key}`);
          return (
            <li key={b.key} className="flex flex-col gap-1" data-this-size={mine || undefined}>
              <span className="flex items-baseline justify-between gap-2 text-caption">
                <span className={mine ? "font-semibold" : ""}>{label}</span>
                <span className={`flex items-center gap-1.5 tabular-nums ${mine ? "font-semibold" : ""}`}>
                  {b.rent != null ? t("profile.money.perMonth", { value: usd(b.rent, lng) }) : "—"}
                  {(b.withheld || b.state?.low) && b.state && <ConfidenceState kind={b.state.kind} low={b.state.low} />}
                </span>
              </span>
              <span className="relative block h-3 overflow-hidden rounded bg-nx-ink/5" role="img"
                aria-label={b.rent != null ? t("profile.money.rent.barLabel", { size: label, rent: usd(b.rent, lng) }) : t("profile.money.rent.barNone", { size: label })}>
                {b.rent != null && <span className={`absolute inset-y-0 left-0 rounded ${mine ? "bg-nx-lot" : "bg-nx-chart-1"}`} style={{ width: `${(b.rent / max) * 100}%` }} />}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="text-caption nx-muted">
        {rent.thisSize
          ? t("profile.money.rent.thisSize", { size: t(`profile.money.rent.bed.${rent.thisSize}`).toLowerCase() })
          : t("profile.money.rent.noSize")}
        {rent.area ? ` · ${t("profile.money.rent.area", { rent: usd(rent.area.rent, lng) })}` : ""}
        {anyPuma ? ` · ${t("profile.money.rent.puma")}` : ""}
      </p>
    </div>
  );
}

// ── Incentives ─────────────────────────────────────────────────────────────────────────────────────────

function IncentivePill({ answer }: { answer: IncentiveAnswer }) {
  const { t } = useTranslation("next");
  if (answer === "checking") {
    return <span className="inline-flex items-center gap-1 rounded-lg bg-nx-ink/5 px-2 py-px text-caption nx-muted"><LoaderCircle aria-hidden className="h-3 w-3 animate-spin" strokeWidth={2} />{t("profile.money.incentives.checking")}</span>;
  }
  const tone: PillTone = answer === "yes" ? "green" : "gray";
  return <Pill tone={tone}>{t(`profile.build.answer.${answer}`)}</Pill>;
}

