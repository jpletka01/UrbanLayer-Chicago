// Economics module content (de-carded 2026-07-07). The old boxed Property card
// is now a set of open bands: the interactive assessment/sales timeline leads,
// tax detail and building facts sit side by side, and the verifier's record
// tables are visible (top-N + one ShowMore) instead of hidden behind chevrons.
// Data shape unchanged — presentation only.
import { useTranslation } from "react-i18next";
import type { PropertySummary } from "../../lib/types";
import { formatDate } from "../../lib/format";
import { InfoTooltip } from "../InfoTooltip";
import { PropertyTimeline } from "./PropertyTimeline";
import { SubSection, ShowMore } from "./ProfileModule";

function fmtDollar(n: number | null | undefined): string {
  if (n == null) return "—";
  return `$${Math.round(n).toLocaleString()}`;
}

const TaxIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const BuildingIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z" />
  </svg>
);

function Fact({ label, value, sourceHint, tip }: {
  label: string;
  value: string | null | undefined;
  /** Provenance note for non-assessor values ("via parcel geometry", "via city
      footprint data") — rendered as a muted suffix so derived numbers are
      honest without shouting. */
  sourceHint?: string | null;
  /** Term definition, shown on hover/tap (tooltip rule — never on-page copy). */
  tip?: string;
}) {
  if (!value || value === "—") return null;
  return (
    <div>
      <dt className="text-caption text-text-muted">
        {tip ? (
          <InfoTooltip content={{ label, description: tip, bullets: [] }}>{label}</InfoTooltip>
        ) : (
          label
        )}
      </dt>
      <dd className="text-body text-text-primary mt-0.5">
        {value}
        {sourceHint && <span className="text-micro text-text-muted"> {sourceHint}</span>}
      </dd>
    </div>
  );
}

/** Sources that deserve a label: everything except the assessor's own data
    (assessor = the default expectation; gis is the county's parcel layer, close enough). */
function sourceHintFor(source: string | null | undefined, t: (k: string) => string): string | null {
  if (!source || source === "assessor" || source === "gis") return null;
  const key = `property.sources.${source}`;
  const label = t(key);
  return label === key ? null : label;
}

export function ScorecardPropertyCard({ data }: { data: PropertySummary }) {
  const { t } = useTranslation("data");

  // Two distinct absent-building states, never conflated: vacant land (class
  // 1xx) has NO building — a fact, stated affirmatively; anything else with no
  // building facts is a data gap, stated as unavailable.
  const isVacantLand = /^1/.test(String(data.bldg_class ?? "").replace("-", ""));
  const hasBuildingFacts = data.bldg_sqft != null || data.bldg_age != null
    || data.stories != null || data.units != null || data.rooms != null;

  const assessed = data.total_assessed_value;
  const tax = data.estimated_annual_tax;
  // Server-computed, class-aware (see types.ts) — never derive these here.
  const effectiveRate = data.effective_tax_rate != null
    ? `${(data.effective_tax_rate * 100).toFixed(2)}%`
    : null;
  const marketValue = data.implied_market_value;

  const baths = [
    data.full_baths ? `${data.full_baths}F` : null,
    data.half_baths ? `${data.half_baths}H` : null,
  ].filter(Boolean).join(" / ") || null;
  const classLabel = [data.bldg_class, data.bldg_class_description].filter(Boolean).join(" — ");

  return (
    <div className="space-y-8">
      {/* The timeline — assessment trajectory (land/building split), sales and
          won appeals on one axis. Falls back to nothing on <2 years of data;
          the record tables below still carry everything. */}
      {data.assessment_history.length >= 2 && (
        <div>
          <div className="text-overline uppercase tracking-wider text-text-muted mb-2">
            {t("property.assessmentHistory")}
          </div>
          <PropertyTimeline
            history={data.assessment_history}
            sales={data.sales_history}
            appeals={data.appeals?.records}
          />
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-x-10 gap-y-8 md:items-start">
        {/* Tax detail */}
        <SubSection icon={TaxIcon} title={t("property.taxDetail")}>
          <div className="space-y-4">
            {(assessed != null || tax != null) && (
              <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                {assessed != null && (
                  <div>
                    <div className="text-caption text-text-muted">
                      <InfoTooltip content={{ label: t("property.assessedValue"), description: t("property.tips.assessed"), bullets: [] }}>
                        {t("property.assessedValue")}
                      </InfoTooltip>
                    </div>
                    <div className="text-body font-medium text-text-primary tabular-nums">{fmtDollar(assessed)}</div>
                  </div>
                )}
                {marketValue != null && (
                  <div>
                    <div className="text-caption text-text-muted">
                      <InfoTooltip content={{ label: t("property.impliedMarketValue"), description: t("property.tips.implied"), bullets: [] }}>
                        {t("property.impliedMarketValue")}
                      </InfoTooltip>
                    </div>
                    <div className="text-body font-medium text-text-primary tabular-nums">{fmtDollar(marketValue)}</div>
                  </div>
                )}
                {tax != null && (
                  <div>
                    <div className="text-caption text-text-muted">
                      <InfoTooltip content={{ label: t("property.annualTax"), description: t("property.tips.annualTax"), bullets: [] }}>
                        {`${t("property.annualTax")}${data.tax_year ? ` (${data.tax_year})` : ""}`}
                      </InfoTooltip>
                    </div>
                    <div className="text-body font-medium text-text-primary tabular-nums">{fmtDollar(tax)}</div>
                  </div>
                )}
                {effectiveRate && (
                  <div>
                    <div className="text-caption text-text-muted">
                      <InfoTooltip content={{ label: t("property.effectiveRate"), description: t("property.tips.effRate"), bullets: [] }}>
                        {t("property.effectiveRate")}
                      </InfoTooltip>
                    </div>
                    <div className="text-body font-medium text-text-primary tabular-nums">{effectiveRate}</div>
                  </div>
                )}
              </div>
            )}

            {/* The agency-by-agency breakdown is deliberately NOT here (2026-07-07
                cut list): every Chicago parcel splits roughly the same way, so it's
                trivia at decision time — it stays in the CSV export and the $25
                report. What remains is the decision-relevant tax context. */}

            {/* Exemptions on the current bill — a buyer loses owner-occupancy
                exemptions at transfer, so this bill understates their future bill. */}
            {(data.tax_exemptions ?? []).length > 0 && (
              <div className="text-caption text-text-secondary">
                {t("property.exemptionsApplied", {
                  kinds: data.tax_exemptions.map((e) => e.kind).join(", "),
                  eav: Math.round(data.tax_exemptions.reduce((s, e) => s + e.eav_reduction, 0)).toLocaleString(),
                })}
                <span className="text-text-muted"> {t("property.exemptionsCaveat")}</span>
              </div>
            )}

            {/* Appeal history — "appealing here works" is direct-dollars context. */}
            {(data.appeals?.records?.length || data.appeals?.nearby_appeal_count) ? (
              <div>
                <div className="text-caption text-text-muted mb-1">
                  <InfoTooltip content={{ label: t("property.appeals.title"), description: t("property.tips.appeals"), bullets: [] }}>
                    {t("property.appeals.title")}
                  </InfoTooltip>
                </div>
                <div className="space-y-1">
                  {(data.appeals.records ?? []).slice(0, 3).map((r, i) => (
                    <div key={i} className="text-caption text-text-secondary">
                      {r.year ?? "—"} · {r.stage === "board_of_review"
                        ? t("property.appeals.stageBor") : t("property.appeals.stageAssessor")} ·{" "}
                      {r.reduction_pct != null ? (
                        <span className="text-state-positive">
                          {t("property.appeals.won", {
                            before: fmtDollar(r.before_total), after: fmtDollar(r.after_total),
                            pct: r.reduction_pct,
                          })}
                        </span>
                      ) : (
                        <span>{t("property.appeals.noChange")}</span>
                      )}
                    </div>
                  ))}
                  {data.appeals.nearby_appeal_count > 0 && (
                    <p className="text-caption text-text-muted">
                      {t("property.appeals.nearby", {
                        count: data.appeals.nearby_capped
                          ? `${data.appeals.nearby_appeal_count}+`
                          : data.appeals.nearby_appeal_count,
                        reduced: data.appeals.nearby_reduced_count,
                      })}
                      {data.appeals.nearby_median_reduction_pct != null &&
                        ` ${t("property.appeals.nearbyMedian", { pct: data.appeals.nearby_median_reduction_pct })}`}
                    </p>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </SubSection>

        {/* Building & lot facts */}
        <SubSection icon={BuildingIcon} title={t("property.buildingAndLot")}>
          <div className="space-y-4">
            {/* Absent-building states: vacant = affirmative fact, else = honest gap */}
            {isVacantLand ? (
              <p className="text-caption text-text-secondary">{t("property.noBuildingVacant")}</p>
            ) : !hasBuildingFacts ? (
              <p className="text-caption text-text-muted">{t("property.buildingDetailsUnavailable")}</p>
            ) : null}

            <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
              <Fact label={t("property.class")} tip={t("property.tips.class")} value={classLabel || null} />
              <Fact label={t("property.floorArea")} tip={t("property.floorAreaTip")}
                value={data.bldg_sqft ? `${data.bldg_sqft.toLocaleString()} ft²` : null}
                sourceHint={sourceHintFor(data.bldg_sqft_source, t)} />
              <Fact label={t("property.landSqft")} value={data.land_sqft ? data.land_sqft.toLocaleString() : null}
                sourceHint={sourceHintFor(data.land_sqft_source, t)} />
              <Fact label={t("property.stories")} value={data.stories ? String(data.stories) : null}
                sourceHint={sourceHintFor(data.stories_source, t)} />
              <Fact label={t("property.units")} value={data.units ? String(data.units) : null} />
              <Fact label={t("property.commercialUnits")} value={data.commercial_units ? String(data.commercial_units) : null} />
              <Fact label={t("property.rooms")} value={data.rooms ? String(data.rooms) : null} />
              <Fact label={t("property.bedrooms")} value={data.bedrooms ? String(data.bedrooms) : null} />
              <Fact label={t("property.baths")} value={baths} />
              <Fact label={t("property.buildingAge")} value={data.bldg_age != null ? `${data.bldg_age} ${t("property.yrs")}` : null}
                sourceHint={sourceHintFor(data.year_built_source, t)} />
            </dl>

            {/* Distress/opportunity flags. Tax-sale mentions carry their years —
                the public datasets end ~2014, so this is title history, not
                current distress. City-owned reads as an opportunity. */}
            {data.flags && (
              <div className="flex flex-col gap-1">
                {data.flags.city_owned && (
                  <span className="text-caption text-state-positive">
                    {t("property.flags.cityOwned")}
                    {data.flags.city_owned_application_url && (
                      <>
                        {" · "}
                        <a href={data.flags.city_owned_application_url} target="_blank" rel="noopener noreferrer"
                          className="underline hover:text-accent">
                          {t("property.flags.cityOwnedApply")}
                        </a>
                      </>
                    )}
                  </span>
                )}
                {data.flags.scofflaw && (
                  <span className="text-caption text-state-negative">{t("property.flags.scofflaw")}</span>
                )}
                {data.flags.chrs_rating && (
                  <span className="text-caption text-state-warning">
                    {t("property.flags.chrs", {
                      color: t(`property.flags.chrsColor.${data.flags.chrs_rating}`),
                    })}
                    {data.flags.chrs_name && (
                      <span className="text-text-muted"> — {data.flags.chrs_name}</span>
                    )}
                  </span>
                )}
                {data.flags.str_prohibited && (
                  <span className="text-caption text-text-secondary">{t("property.flags.strProhibited")}</span>
                )}
                {data.flags.tax_sale_years.length > 0 && (
                  <span className="text-caption text-text-secondary">
                    {t("property.flags.taxSale", { years: data.flags.tax_sale_years.join(", ") })}
                  </span>
                )}
                {data.flags.scavenger_sale_years.length > 0 && (
                  <span className="text-caption text-text-secondary">
                    {t("property.flags.scavengerSale", { years: data.flags.scavenger_sale_years.join(", ") })}
                  </span>
                )}
              </div>
            )}

            {/* Energy benchmarking (≥50k-sqft buildings): a missing report is
                itself a compliance fact, stated rather than silently omitted. */}
            {data.energy && (data.energy.chicago_energy_rating != null || data.energy.energy_star_score != null) ? (
              <div className="text-caption text-text-secondary">
                {[
                  data.energy.chicago_energy_rating != null
                    ? t("property.energy.rating", { rating: data.energy.chicago_energy_rating })
                    : null,
                  data.energy.energy_star_score != null
                    ? t("property.energy.star", { score: data.energy.energy_star_score })
                    : null,
                  data.energy.site_eui != null
                    ? t("property.energy.eui", { eui: data.energy.site_eui })
                    : null,
                ].filter(Boolean).join(" · ")}
                {data.energy.data_year && (
                  <span className="text-text-muted"> ({data.energy.data_year})</span>
                )}
              </div>
            ) : data.energy?.not_submitted ? (
              <p className="text-caption text-text-muted">
                {t("property.energy.notSubmitted", { year: data.energy.data_year ?? "" })}
              </p>
            ) : null}
          </div>
        </SubSection>
      </div>

      {/* Full records for the verifier persona — visible, top-N + ShowMore */}
      {(data.sales_history.length > 0 || data.assessment_history.length > 0) && (
        <div className="grid sm:grid-cols-2 gap-x-10 gap-y-6">
          {data.sales_history.length > 0 && (
            <ShowMore
              items={data.sales_history}
              limit={5}
              render={(rows) => (
                <RecordTable
                  caption={t("property.salesHistory")}
                  headers={[t("property.date"), t("property.price"), t("property.deed")]}
                  rows={rows.map((s) => [
                    s.date ? formatDate(s.date) : "—",
                    fmtDollar(s.price),
                    s.deed_type ?? "—",
                  ])}
                />
              )}
            />
          )}
          {data.assessment_history.length > 0 && (
            <ShowMore
              items={[...data.assessment_history].sort((a, b) => (b.year ?? 0) - (a.year ?? 0))}
              limit={5}
              render={(rows) => (
                <RecordTable
                  caption={t("property.assessmentHistory")}
                  headers={[t("property.year"), t("property.land"), t("property.building"), t("property.total")]}
                  rows={rows.map((a) => [
                    a.year != null ? String(a.year) : "—",
                    fmtDollar(a.land),
                    fmtDollar(a.building),
                    fmtDollar(a.total),
                  ])}
                />
              )}
            />
          )}
        </div>
      )}
    </div>
  );
}

function RecordTable({ caption, headers, rows }: { caption: string; headers: string[]; rows: string[][] }) {
  return (
    <div>
      <div className="text-caption text-text-muted mb-1.5">{caption}</div>
      <table className="w-full text-caption">
        <thead>
          <tr className="text-text-muted border-b border-dark-border">
            {headers.map((h) => (
              <th key={h} className="text-left pb-1.5 pr-2 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-dark-border/50">
              {row.map((cell, j) => (
                <td key={j} className={`py-1.5 pr-2 text-text-primary ${j > 0 ? "tabular-nums" : ""}`}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
