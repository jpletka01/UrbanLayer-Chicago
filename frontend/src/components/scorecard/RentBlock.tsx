// Current official rent for the parcel's area (WS4 PR2). Rents are the Census Bureau's ACS 5-year
// estimates, never a listing price: the community area's overall median (our sum of Census rent
// brackets, with a margin we derived), the parcel's tract median, and the Census's own medians by
// bedroom count for the tract, else its PUMA. There is no community-area figure by bedroom count.
// Below them, as a separate series (WS4 PR3), sits the County Assessor's MODELED apartment income for the
// community area: never merged with the Census rents, never called a rent, never by bedroom count.
// Last (WS4 PR5), HUD's Small Area Fair Market Rents for the parcel's ZIP: a voucher standard, not a market rent.
// The backend decides each figure's confidence state; this block only says it (guide:
// claude-context/guides/source-confidence.md).
import { useTranslation } from "react-i18next";
import type { Provenance } from "../../lib/api";
import { useFact } from "../../lib/provenanceContext";
import type { AssessorModelRent, BedroomRent, NeighborhoodSummary, RentEvidence, SaleYear, SmallAreaFmr } from "../../lib/types";
import { ConfidenceCaption, ConfidenceValue, SourceTooltip } from "../ui/Confidence";
import { ToolTray } from "../ui/ToolTray";
import { StatusLabel } from "../ui/StatusLabel";
import { DISPLAY_THRESHOLDS } from "../../lib/confidence";

const BEDROOMS = ["1_bedroom", "2_bedrooms", "3_bedrooms"] as const;

const usd = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;

function Tile({ testId, label, tip, entry, value, sub, note, suffix, omitPeriod = true }: {
  testId: string;
  label: string;
  tip: string;
  entry: Provenance | undefined;
  /** Null renders a dash: nothing to show, with `sub` saying why. */
  value: number | null;
  sub?: string;
  note?: string;
  /** What follows the amount; defaults to "/mo". */
  suffix?: string;
  /** The Census tiles' period is in their block header; a tile whose header gives none keeps it. */
  omitPeriod?: boolean;
}) {
  const { t } = useTranslation("pages");
  return (
    <div className="min-w-0" data-testid={testId}>
      <div className="text-overline uppercase tracking-wider text-text-muted">
        <SourceTooltip label={label} description={tip} entry={entry} unit="usd">{label}</SourceTooltip>
      </div>
      <div className="text-subtitle text-text-primary mt-0.5 truncate">
        {value == null ? <span className="text-text-muted">—</span> : (
          <ConfidenceValue entry={entry}>
            {usd(value)}<span className="text-caption text-text-muted font-normal">{suffix ?? t("scorecard.rent.perMonth")}</span>
          </ConfidenceValue>
        )}
      </div>
      {sub && <div className="text-caption text-text-muted mt-0.5 leading-snug">{sub}</div>}
      {note && <div className="text-caption text-text-muted mt-0.5 leading-snug">{note}</div>}
      {/* Method, margin and area stay on every tile (guide §4.4, §4.6: an area figure names its area,
          a PUMA is never passed off as a tract); the period sits once in the block header instead of
          five repeats (decision Item 54). */}
      <ConfidenceCaption entry={entry} size="micro" unit="usd" omit={omitPeriod ? ["period"] : undefined} />
    </div>
  );
}

function BedroomTile({ group, cell, pumaUnchecked }: { group: (typeof BEDROOMS)[number]; cell: BedroomRent | undefined; pumaUnchecked: boolean }) {
  const { t } = useTranslation("pages");
  const entry = useFact(`area.rent.${group}`);
  const label = t(`scorecard.rent.${group}`);
  const tip = t("scorecard.tips.rentBedroom");
  const testId = `rent-tile-${group}`;
  if (!cell) {
    // The PUMA was needed and couldn't be read: say so rather than leave a hole that reads as "none".
    return pumaUnchecked
      ? <Tile testId={testId} label={label} tip={tip} entry={undefined} value={null} sub={t("scorecard.rent.pumaUnchecked")} />
      : null;
  }
  if (cell.estimate == null) {
    return <Tile testId={testId} label={label} tip={tip} entry={undefined} value={null} sub={t("scorecard.rent.notPublished")} />;
  }
  const fromPuma = cell.scope === "puma";
  return (
    <Tile
      testId={testId} label={label} tip={tip} entry={entry} value={cell.estimate}
      sub={fromPuma ? t("scorecard.rent.pumaSub") : t("scorecard.rent.tractSub")}
      note={fromPuma && cell.tract_fallback ? t(`scorecard.rent.fallback.${cell.tract_fallback}`) : undefined}
    />
  );
}

/** The Assessor's modeled income. A figure the backend withholds shows "—" and its reason (from the entry);
    an area with no modeled apartments, or one we couldn't check, says that in words, never as an empty cell. */
function AssessorModelTile({ model, unchecked }: { model: AssessorModelRent | null | undefined; unchecked: boolean }) {
  const { t } = useTranslation("pages");
  const entry = useFact("area.rent.assessor_model");
  const label = t("scorecard.rent.assessor.label");
  const tip = t("scorecard.tips.rentAssessor");
  const testId = "rent-tile-assessor-model";
  if (!model) {
    return unchecked
      ? <Tile testId={testId} label={label} tip={tip} entry={undefined} value={null} sub={t("scorecard.rent.assessor.unchecked")} />
      : null;
  }
  if (model.median_per_unit_month == null) {
    return <Tile testId={testId} label={label} tip={tip} entry={undefined} value={null}
      sub={t(model.buildings === 0 ? "scorecard.rent.assessor.none" : "scorecard.rent.assessor.noFigure")} />;
  }
  return (
    <Tile
      testId={testId} label={label} tip={tip} entry={entry} value={model.median_per_unit_month}
      suffix={t("scorecard.rent.assessor.perUnit")}
      omitPeriod={false}
      sub={entry?.confidence === "withheld" ? undefined : t("scorecard.rent.assessor.sub", { buildings: model.priced.toLocaleString("en-US") })}
    />
  );
}

const HUD_BEDROOMS = ["0", "1", "2", "3", "4"] as const;

/** HUD's ZIP-level voucher rent standard (WS4 PR5, decision Item 69). FY, ZIP and what the figure covers sit once in
 *  the header; each tile is one bedroom count. A ZIP HUD doesn't list, or a table we couldn't read, says so. */
function HudBlock({ fmr, unchecked }: { fmr: SmallAreaFmr | null | undefined; unchecked: boolean }) {
  const { t } = useTranslation("pages");
  return (
    <div className="space-y-3" data-testid="rent-hud">
      <div>
        <div className="flex items-center gap-1 text-overline uppercase tracking-wider text-text-muted">
          {t("scorecard.rent.hud.title")}
          {fmr && (
            <ToolTray
              label={t("scorecard.rent.hud.title")}
              align="start"
              explain={<span className="block normal-case tracking-normal" data-testid="hud-explain">{t("scorecard.rent.hud.scope", { zip: fmr.zip_code, fy: fmr.fy })}</span>}
            />
          )}
        </div>
        <p className="text-caption text-text-muted leading-snug mt-0.5">
          {!fmr ? t("scorecard.rent.hud.unchecked")
            : fmr.listed ? t("scorecard.rent.hud.line", { zip: fmr.zip_code, fy: fmr.fy })
              : t("scorecard.rent.hud.notListed", { zip: fmr.zip_code })}
        </p>
      </div>
      {fmr?.listed && !unchecked && (
        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-x-6 gap-y-4">
          {HUD_BEDROOMS.filter((b) => fmr.by_bedroom[b] != null).map((b) => (
            <HudTile key={b} bedrooms={b} amount={fmr.by_bedroom[b]} />
          ))}
        </div>
      )}
    </div>
  );
}

function HudTile({ bedrooms, amount }: { bedrooms: (typeof HUD_BEDROOMS)[number]; amount: number }) {
  const { t } = useTranslation("pages");
  const entry = useFact(`area.rent.hud_safmr.${bedrooms}`);
  const label = t(`scorecard.rent.hud.br${bedrooms}`);
  return (
    <div className="min-w-0" data-testid={`rent-tile-hud-${bedrooms}`}>
      <div className="text-overline uppercase tracking-wider text-text-muted">
        <SourceTooltip label={label} description={t("scorecard.tips.rentHud")} entry={entry} unit="usd">{label}</SourceTooltip>
      </div>
      <div className="text-subtitle text-text-primary mt-0.5 truncate">
        <ConfidenceValue entry={entry}>
          {usd(amount)}<span className="text-caption text-text-muted font-normal">{t("scorecard.rent.perMonth")}</span>
        </ConfidenceValue>
      </div>
    </div>
  );
}

const SALE_GROUPS = ["two_to_six", "single_family", "condo"] as const;

/** Which way rent and sale prices moved in the community area (WS4 PR4, decision Item 62). The rent change between
 *  two non-overlapping ACS periods, labeled when it is within the margins; and per property group the median sale
 *  price of the first and last year with enough sales. The method and the year-by-year series sit behind Explain. */
function TrendBlock({ rent }: { rent: RentEvidence }) {
  const { t, i18n } = useTranslation("pages");
  const nf = new Intl.NumberFormat(i18n.language === "es" ? "es-MX" : "en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  const pct = (x: number) => { const r = Math.round(x); return `${r > 0 ? "+" : ""}${r === 0 ? 0 : r}%`; };
  const tr = rent.trend;
  const st = rent.sales_trend;
  const min = DISPLAY_THRESHOLDS.hideNBelow;
  const enough = (c: SaleYear) => c.median != null && c.n >= min;
  return (
    <div className="space-y-3" data-testid="rent-trend">
      <div className="flex items-center gap-1 text-overline uppercase tracking-wider text-text-muted">
        {t("scorecard.trend.title")}
        <ToolTray
          label={t("scorecard.trend.title")}
          align="start"
          explain={
            <span className="block space-y-1.5 normal-case tracking-normal" data-testid="trend-explain">
              {tr && <span className="block">{t("scorecard.trend.rentMethod", { a: tr.earlier.period, b: tr.later.period })}</span>}
              {st && <span className="block">{t("scorecard.trend.salesMethod", { min })}</span>}
              {st && SALE_GROUPS.filter((g) => st.groups[g]).map((g) => (
                <span key={g} className="block font-mono text-micro">
                  {t(`scorecard.trend.group.${g}`)}: {st.groups[g]!.map((c) => `${c.year} ${enough(c) ? nf.format(c.median!) : "—"} (n ${c.n})`).join(" · ")}
                </span>
              ))}
            </span>
          }
        />
      </div>
      <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        {tr && (
          <div data-testid="trend-rent">
            <dt className="text-caption text-text-muted">{t("scorecard.trend.rent", { period: tr.earlier.period })}</dt>
            <dd className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="text-subtitle tabular-nums text-text-primary">{pct(tr.change_pct)}</span>
              <span className="text-caption text-text-secondary">{t("scorecard.trend.realChange", { pct: pct(tr.real_change_pct) })}</span>
              {tr.significant === false && <StatusLabel tone="neutral" glyph={null}>{t("scorecard.trend.notClear")}</StatusLabel>}
            </dd>
          </div>
        )}
        {st && SALE_GROUPS.filter((g) => st.groups[g]).map((g) => {
          const cells = st.groups[g]!;
          const first = cells.find(enough);
          const last = [...cells].reverse().find(enough);
          const latest = cells[cells.length - 1];
          return (
            <div key={g} data-testid={`trend-sales-${g}`}>
              <dt className="text-caption text-text-muted">{t(`scorecard.trend.group.${g}`)}</dt>
              <dd className="mt-0.5">
                {last ? (
                  <>
                    <span className="text-subtitle tabular-nums text-text-primary">{nf.format(last.median!)}</span>
                    <span className="ml-2 text-caption text-text-secondary">
                      {first && first.year !== last.year
                        ? t("scorecard.trend.salesSince", { year: last.year, from: nf.format(first.median!), first: first.year })
                        : t("scorecard.trend.salesIn", { year: last.year })}
                    </span>
                  </>
                ) : (
                  <span className="text-caption text-text-muted" data-withheld-reason>
                    {t("scorecard.trend.tooFew", { n: latest?.n ?? 0, min })}
                  </span>
                )}
              </dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

export function RentBlock({ data }: { data: NeighborhoodSummary }) {
  const { t } = useTranslation("pages");
  const rent = data.rent;
  const areaEntry = useFact("area.rent.community_area");
  const tractEntry = useFact("area.tract.median_gross_rent");
  if (!rent) return null;
  const ca = rent.community_area;
  const tractRent = data.census_tract?.median_gross_rent ?? null;
  const cells = new Map(rent.bedrooms.map((b) => [b.bedrooms, b]));
  const pumaUnchecked = rent.unchecked.includes("puma_rent");
  const areaUnchecked = rent.unchecked.includes("community_area_rent");
  const model = rent.assessor_model;
  const modelUnchecked = rent.unchecked.includes("assessor_model");
  const hasAcs = !!ca || tractRent != null || cells.size > 0 || pumaUnchecked || areaUnchecked;
  const hudUnchecked = rent.unchecked.includes("hud_safmr");
  if (!hasAcs && !model && !modelUnchecked && !rent.safmr && !hudUnchecked) return null;
  return (
    <div className="space-y-4" data-testid="rent-block">
      {hasAcs && (
      <div className="space-y-3" data-testid="rent-acs">
        <div>
          <div className="text-overline uppercase tracking-wider text-text-muted">{t("scorecard.rent.title")}</div>
          <p className="text-caption text-text-muted leading-snug mt-0.5">
            {rent.acs_period ? t("scorecard.rent.scope", { period: rent.acs_period }) : t("scorecard.rent.scopeNoPeriod")}
          </p>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-x-6 gap-y-4">
          {(ca || areaUnchecked) && (
            <Tile
              testId="rent-tile-community-area" label={t("scorecard.rent.communityArea")} tip={t("scorecard.tips.rentArea")}
              entry={areaEntry} value={ca?.median ?? null}
              sub={ca ? undefined : t("scorecard.rent.areaUnchecked")}
            />
          )}
          {tractRent != null && (
            <Tile testId="rent-tile-tract" label={t("scorecard.rent.tract")} tip={t("scorecard.tips.rentTract")} entry={tractEntry} value={tractRent} />
          )}
          {BEDROOMS.map((g) => (
            <BedroomTile key={g} group={g} cell={cells.get(g)} pumaUnchecked={pumaUnchecked} />
          ))}
        </div>
      </div>
      )}
      {(rent.trend || rent.sales_trend) && <TrendBlock rent={rent} />}
      {(model || modelUnchecked) && (
        <div className="space-y-3" data-testid="rent-assessor">
          <div>
            <div className="flex items-center gap-1 text-overline uppercase tracking-wider text-text-muted">
              {t("scorecard.rent.assessor.title")}
              {model && (
                <ToolTray
                  label={t("scorecard.rent.assessor.title")}
                  align="start"
                  explain={<span className="block normal-case tracking-normal" data-testid="assessor-explain">{t("scorecard.rent.assessor.scope", { year: model.year, cycle: model.cycle })}</span>}
                />
              )}
            </div>
            {!model && (
              <p className="text-caption text-text-muted leading-snug mt-0.5">{t("scorecard.rent.assessor.unchecked")}</p>
            )}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-x-6 gap-y-4">
            <AssessorModelTile model={model} unchecked={modelUnchecked} />
          </div>
        </div>
      )}
      {(rent.safmr || hudUnchecked) && <HudBlock fmr={rent.safmr} unchecked={hudUnchecked} />}
    </div>
  );
}
