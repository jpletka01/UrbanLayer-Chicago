// Money tab (brief "Property Profile", Money: "What would it cost or earn?"; decision Item 99). The tab shape of
// every Profile tab: takeaway sentence → one wide main visual (nearby market sales, with the "nearby" rule as
// chips; the same sales are the pins on the map above) → three smaller visuals (taxes and the Assessor's value
// over time; rent for this building's unit size; incentives as yes/no chips) → a collapsed details table.
// Blocks that read a late part follow Item 89's skeleton rule: their own outline while waiting, "Couldn't check
// in time · Retry" in the same place if the source passed its deadline. No figure here is a forecast (rule 11).
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, LoaderCircle, MapPin, RotateCw, TriangleAlert } from "lucide-react";
import type { ScorecardResponse } from "../../lib/api";
import { ConfidenceState } from "../../components/ui/ConfidenceState";
import { Toggletip } from "../../components/ui/Toggletip";
import { Block, Pill, type PillTone } from "../ui/Blocks";
import { ICON, STROKE } from "../icons";
import { numLocale, type FigureState } from "./profileModel";
import {
  agencyName, assessorBelowSale, compsModel, moneySentence, usd, incentiveChips, rentModel, taxModel, valueHistory,
  type CompsModel, type IncentiveAnswer, type LateBlockState, type RentModel, type TaxModel, type ValueYear,
} from "./moneyModel";

const usdShort = (n: number, lng: string) =>
  new Intl.NumberFormat(lng.startsWith("es") ? "es-MX" : "en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(n);
const pct = (f: number, digits = 2) => (f * 100).toFixed(digits);
const monthYear = (iso: string | null, lng: string) =>
  iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString(numLocale(lng), { month: "short", year: "numeric" }) : "—";

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
  const tax = taxModel(data);
  const comps = compsModel(data);
  const history = valueHistory(data);
  const flag = assessorBelowSale(data);
  const rent = rentModel(data);
  const chips = incentiveChips(data, late.incentives === "loading");
  const prop = data.context?.property;
  const inc = data.context?.incentives;

  return (
    <div className="flex flex-col gap-7" data-testid="money-tab">
      <p className="text-nx-answer" data-testid="money-sentence">{moneySentence(data, t, lng)}</p>

      <Block
        title={t("profile.money.sales.title")}
        icon={ICON.sale}
        labelledBy="nx-sales"
        aside={late.money === "ready" && comps && comps.sales.length > 0 ? (
          <span className="inline-flex items-center gap-1"><MapPin aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{t("profile.money.sales.onMap")}</span>
        ) : undefined}
      >
        <LateSlot state={late.money} what={t("profile.parts.part.money")} onRetry={() => onRetry("money")} skeleton={<SalesSkeleton />}>
          {comps ? <SalesBody comps={comps} /> : <p className="nx-muted">{t("profile.money.sales.none")}</p>}
        </LateSlot>
      </Block>

      <div className="grid gap-7 md:grid-cols-2 xl:grid-cols-3">
        <Block title={t("profile.money.tax.title")} icon={ICON.tax} labelledBy="nx-tax"
          aside={tax.year ? t("profile.money.tax.billYear", { year: tax.year }) : undefined}>
          <TaxBody tax={tax} history={history.years} basis={history.basis} flag={flag} />
        </Block>

        <Block title={t("profile.money.rent.title")} icon={ICON.rent} labelledBy="nx-rent"
          aside={rent?.period ? t("profile.money.rent.census", { period: rent.period }) : undefined}>
          <LateSlot state={late.neighborhood} what={t("profile.money.rent.what")} onRetry={() => onRetry("neighborhood")} skeleton={<BarsSkeleton rows={3} />}>
            <RentBody rent={rent} />
          </LateSlot>
        </Block>

        <Block title={t("profile.money.incentives.title")} icon={ICON.incentives} labelledBy="nx-incentives">
          <ul className="flex flex-wrap gap-2" data-testid="incentive-chips">
            {chips.map((c) => (
              <li key={c.key} className="flex items-center gap-1.5 rounded-xl bg-nx-page px-2.5 py-1.5" data-incentive={c.key} data-answer={c.answer}>
                <span className="text-caption">{t(`profile.money.incentives.program.${c.key}`)}</span>
                <IncentivePill answer={c.answer} />
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
            {" "}
            <Toggletip label={t("profile.money.incentives.howToRead")}>
              <p>{t("profile.money.incentives.howToReadBody")}</p>
            </Toggletip>
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
              [t("profile.money.details.rate"), tax.rate != null ? `${pct(tax.rate)}%` : "—"],
              [t("profile.money.details.typicalRate"), tax.typicalRate != null ? `${pct(tax.typicalRate, 1)}%` : "—"],
              [t("profile.money.details.exemptions"), tax.exemptions.length ? tax.exemptions.join(", ") : t("profile.money.details.noneOnBill")],
              [t("profile.money.details.taxCode"), prop?.tax_code || "—"],
              ...(prop?.tax_breakdown ?? []).slice().sort((a, b) => b.amount - a.amount).map((l) => [agencyName(l.agency), usd(l.amount, lng)] as const),
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

function SalesSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-4">
      <div className="flex gap-2">{[16, 20, 14, 12].map((w, i) => <span key={i} className={`${pulse} h-6`} style={{ width: `${w * 0.25}rem` }} />)}</div>
      <span className={`${pulse} h-7 w-32`} />
      <span className={`${pulse} h-9 w-full`} />
      {[0, 1, 2].map((i) => <span key={i} className={`${pulse} h-5 w-full`} />)}
    </div>
  );
}

function BarsSkeleton({ rows }: { rows: number }) {
  return (
    <div aria-hidden className="flex flex-col gap-3">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="grid grid-cols-[5rem_1fr] items-center gap-3">
          <span className={`${pulse} h-3`} />
          <span className={`${pulse} h-2`} style={{ width: `${70 - i * 15}%` }} />
        </div>
      ))}
    </div>
  );
}

// ── Nearby sales ───────────────────────────────────────────────────────────────────────────────────────

const SALES_SHOWN = 5;

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

  return (
    <div className="flex flex-col gap-5">
      <ul className="flex flex-wrap gap-2" aria-label={t("profile.money.sales.ruleLabel")} data-testid="sales-rule">
        {ruleChips.map((c) => <li key={c}><Pill tone="gray">{c}</Pill></li>)}
        {r.widened && <li><Pill tone="yellow">{t("profile.money.sales.rule.widened")}</Pill></li>}
      </ul>

      {comps.sales.length === 0 ? (
        <p className="nx-muted">{t("profile.money.sales.noneFound")}</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-x-10 gap-y-3">
            <Figure label={t("profile.money.sales.median")} value={comps.median != null && !comps.medianWithheld ? usd(comps.median, lng) : "—"} state={comps.medianState} testId="sales-median" />
            {(comps.perBuildable != null || comps.perBuildableWithheld) && (
              <Figure label={t("profile.money.sales.perBuildable")} value={comps.perBuildable != null && !comps.perBuildableWithheld ? t("profile.money.perSqft", { value: usd(comps.perBuildable, lng) }) : "—"} state={comps.perBuildableState} />
            )}
          </div>
          {comps.sales.length >= 3 && <PriceStrip sales={comps.sales} median={comps.medianWithheld ? null : comps.median} />}
          <SalesList sales={comps.sales.slice(0, SALES_SHOWN)} />
        </>
      )}
    </div>
  );
}

function Figure({ label, value, state, testId }: { label: string; value: string; state: FigureState; testId?: string }) {
  return (
    <div className="flex flex-col gap-0.5" data-testid={testId}>
      <span className="text-caption nx-muted">{label}</span>
      <span className="flex flex-wrap items-center gap-2">
        <span className="text-nx-figure tabular-nums">{value}</span>
        {state && <ConfidenceState kind={state.kind} low={state.low} />}
      </span>
    </div>
  );
}

/** Sale prices on one axis (a dot each, the median a hairline). This lot's Assessor value is not drawn: an
    assessment is not a price, and one axis would read as a comparison it isn't. */
function PriceStrip({ sales, median }: { sales: Array<{ sale_price: number }>; median: number | null }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const prices = sales.map((s) => s.sale_price);
  const min = Math.min(...prices), max = Math.max(...prices);
  const W = 560, H = 36, PX = 10;
  const x = (p: number) => (max === min ? W / 2 : PX + ((p - min) / (max - min)) * (W - 2 * PX));
  return (
    <figure className="flex flex-col gap-1">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-9 w-full" role="img" data-testid="price-strip"
        aria-label={t("profile.money.sales.stripLabel", { count: sales.length, min: usd(min, lng), max: usd(max, lng) })}>
        <line x1={PX} x2={W - PX} y1={H / 2} y2={H / 2} className="stroke-nx-ink/10" strokeWidth={2} />
        {median != null && max > min && <line x1={x(median)} x2={x(median)} y1={4} y2={H - 4} className="stroke-nx-ink" strokeWidth={1.5} />}
        {prices.map((p, i) => <circle key={i} cx={x(p)} cy={H / 2} r={6} className="fill-nx-chart-1 stroke-nx-block" strokeWidth={2} />)}
      </svg>
      <figcaption aria-hidden className="flex justify-between text-caption nx-muted tabular-nums">
        <span>{usdShort(min, lng)}</span>
        {median != null && max > min && <span>{t("profile.money.sales.medianMark")}</span>}
        <span>{usdShort(max, lng)}</span>
      </figcaption>
    </figure>
  );
}

function SalesList({ sales }: { sales: CompsModel["sales"] }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  return (
    <table className="w-full text-caption" data-testid="sales-list">
      <thead className="sr-only sm:not-sr-only">
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

// ── Taxes and the Assessor's value ─────────────────────────────────────────────────────────────────────

function TaxBody({ tax, history, basis, flag }: {
  tax: TaxModel; history: ValueYear[]; basis: "market" | "assessed"; flag: ReturnType<typeof assessorBelowSale>;
}) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  if (tax.kind !== "bill") {
    return (
      <div className="flex flex-col gap-3">
        <span className="text-nx-figure">{tax.kind === "exempt" ? t("profile.tiles.exempt") : "—"}</span>
        <p className="text-caption nx-muted">
          {t(`profile.money.tax.${tax.kind}`, { rate: tax.typicalRate != null ? pct(tax.typicalRate, 1) : "" })}
        </p>
        {history.length > 0 && <ValueBars years={history} basis={basis} />}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-0.5" data-testid="tax-figure">
        <span className="flex flex-wrap items-baseline gap-x-1.5">
          <span className="text-nx-figure tabular-nums">{usd(tax.tax!, lng)}</span>
          <span className="text-caption nx-muted">{t("profile.tiles.perYear")}</span>
          {tax.state && <ConfidenceState kind={tax.state.kind} low={tax.state.low} />}
        </span>
        {tax.rate != null && (
          <span className="text-caption nx-muted">
            {tax.typicalRate != null
              ? t("profile.money.tax.rateVsTypical", { rate: pct(tax.rate), typical: pct(tax.typicalRate, 1) })
              : t("profile.tiles.taxRate", { rate: pct(tax.rate) })}
          </span>
        )}
      </div>
      {tax.agencies.length > 0 && <AgencyBar agencies={tax.agencies} />}
      {history.length > 0 && <ValueBars years={history} basis={basis} />}
      {flag && (
        <p className="flex items-start gap-1.5 text-caption font-medium" data-testid="assessor-flag">
          <TriangleAlert aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={2} />
          {t("profile.money.tax.belowSale", { pct: flag.pctBelow, year: flag.saleYear })}
        </p>
      )}
    </div>
  );
}

const AGENCY_FILL = ["bg-nx-chart-1", "bg-nx-chart-2", "bg-nx-chart-3", "bg-nx-chart-4", "bg-nx-ink/20"];

/** Where the bill goes: one stacked bar, the largest taxing bodies named in a small key. */
function AgencyBar({ agencies }: { agencies: TaxModel["agencies"] }) {
  const { t } = useTranslation("next");
  const name = (a: TaxModel["agencies"][number]) => (a.others ? t("profile.money.tax.others") : agencyName(a.name));
  return (
    <figure className="flex flex-col gap-2">
      <figcaption className="text-caption nx-muted">{t("profile.money.tax.whereItGoes")}</figcaption>
      <div className="flex h-2.5 overflow-hidden rounded" role="img" data-testid="agency-bar"
        aria-label={agencies.map((a) => `${name(a)} ${Math.round(a.share * 100)}%`).join(", ")}>
        {agencies.map((a, i) => <span key={i} className={AGENCY_FILL[a.others ? 4 : i]} style={{ width: `${a.share * 100}%` }} />)}
      </div>
      <ul aria-hidden className="flex flex-col gap-1 text-caption">
        {agencies.map((a, i) => (
          <li key={i} className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 shrink-0 rounded-sm ${AGENCY_FILL[a.others ? 4 : i]}`} />
            <span className="min-w-0 flex-1 truncate">{name(a)}</span>
            <span className="tabular-nums nx-muted">{Math.round(a.share * 100)}%</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}

/** The Assessor's value by year (land and building stacked), this lot in black for its latest year. */
function ValueBars({ years, basis }: { years: ValueYear[]; basis: "market" | "assessed" }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const max = Math.max(...years.map((y) => y.total));
  const last = years[years.length - 1];
  return (
    <figure className="flex flex-col gap-2">
      <figcaption className="flex items-center gap-2 text-caption nx-muted">
        <ICON.valueOverTime aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
        {basis === "market" ? t("profile.money.tax.valueOverTime") : t("profile.money.tax.assessedOverTime")}
      </figcaption>
      <div className="flex h-20 items-end gap-1.5" role="img" data-testid="value-bars"
        aria-label={years.map((y) => `${y.year}: ${usd(y.total, lng)}`).join(", ")}>
        {years.map((y) => {
          const isLast = y === last;
          return (
            <div key={y.year} className="flex h-full min-w-0 flex-1 flex-col justify-end" title={`${y.year}: ${usd(y.total, lng)}`}>
              <span className={`block rounded-t ${isLast ? "bg-nx-lot" : "bg-nx-chart-3"}`} style={{ height: `${(y.building / max) * 100}%` }} />
              <span className={`block ${isLast ? "bg-nx-lot/50" : "bg-nx-chart-1"}`} style={{ height: `${(y.land / max) * 100}%` }} />
            </div>
          );
        })}
      </div>
      <div aria-hidden className="flex justify-between text-caption nx-muted tabular-nums">
        <span>{years[0].year}</span>
        <span className="font-semibold text-nx-ink">{last.year}: {usdShort(last.total, lng)}</span>
      </div>
      <p aria-hidden className="flex gap-3 text-caption nx-muted">
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-nx-chart-3" />{t("profile.money.tax.building")}</span>
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-nx-chart-1" />{t("profile.money.tax.land")}</span>
      </p>
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
              <span className="relative block h-2 overflow-hidden rounded bg-nx-ink/5" role="img"
                aria-label={b.rent != null ? t("profile.money.rent.barLabel", { size: label, rent: usd(b.rent, lng) }) : t("profile.money.rent.barNone", { size: label })}>
                {b.rent != null && <span className={`absolute inset-y-0 left-0 rounded ${mine ? "bg-nx-lot" : "bg-nx-chart-1"}`} style={{ width: `${(b.rent / max) * 100}%` }} />}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="text-caption nx-muted">
        <span className="mr-1.5 inline-flex align-middle"><ConfidenceState kind="estimate" low={false} /></span>
        {rent.thisSize
          ? t("profile.money.rent.thisSize", { size: t(`profile.money.rent.bed.${rent.thisSize}`).toLowerCase() })
          : t("profile.money.rent.noSize")}
        {rent.area ? ` · ${t("profile.money.rent.area", { rent: usd(rent.area.rent, lng) })}` : ""}
        {anyPuma ? ` · ${t("profile.money.rent.puma")}` : ""}
        {" "}
        <Toggletip label={t("profile.money.rent.howToRead")}>
          <p>{t("profile.money.rent.howToReadBody")}</p>
        </Toggletip>
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

