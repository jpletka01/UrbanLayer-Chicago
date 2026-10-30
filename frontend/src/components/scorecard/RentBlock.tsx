// Current official rent for the parcel's area (WS4 PR2). Rents are the Census Bureau's ACS 5-year
// estimates, never a listing price: the community area's overall median (our sum of Census rent
// brackets, with a margin we derived), the parcel's tract median, and the Census's own medians by
// bedroom count for the tract, else its PUMA. There is no community-area figure by bedroom count.
// Below them, as a separate series (WS4 PR3), sits the County Assessor's MODELED apartment income for the
// community area: never merged with the Census rents, never called a rent, never by bedroom count.
// The backend decides each figure's confidence state; this block only says it (guide:
// claude-context/guides/source-confidence.md).
import { useTranslation } from "react-i18next";
import type { Provenance } from "../../lib/api";
import { useFact } from "../../lib/provenanceContext";
import type { AssessorModelRent, BedroomRent, NeighborhoodSummary } from "../../lib/types";
import { ConfidenceCaption, ConfidenceValue, SourceTooltip } from "../ui/Confidence";

const BEDROOMS = ["1_bedroom", "2_bedrooms", "3_bedrooms"] as const;

const usd = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;

function Tile({ testId, label, tip, entry, value, sub, note, suffix }: {
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
      <ConfidenceCaption entry={entry} size="micro" unit="usd" />
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
      sub={entry?.confidence === "withheld" ? undefined : t("scorecard.rent.assessor.sub", { buildings: model.priced.toLocaleString("en-US") })}
    />
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
  if (!hasAcs && !model && !modelUnchecked) return null;
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
      {(model || modelUnchecked) && (
        <div className="space-y-3" data-testid="rent-assessor">
          <div>
            <div className="text-overline uppercase tracking-wider text-text-muted">{t("scorecard.rent.assessor.title")}</div>
            <p className="text-caption text-text-muted leading-snug mt-0.5">
              {model
                ? t("scorecard.rent.assessor.scope", { year: model.year, cycle: model.cycle })
                : t("scorecard.rent.assessor.unchecked")}
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-x-6 gap-y-4">
            <AssessorModelTile model={model} unchecked={modelUnchecked} />
          </div>
        </div>
      )}
    </div>
  );
}
