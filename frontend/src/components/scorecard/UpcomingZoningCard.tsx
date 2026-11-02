import { useTranslation } from "react-i18next";
import type { UpcomingZoningFiling, UpcomingZoningSummary } from "../../lib/types";
import { titleCaseAddress } from "../../lib/format";
import { ConfidenceState } from "../ui/ConfidenceState";
import { StatusLabel } from "../ui/StatusLabel";
import { DateLine, ToolTray } from "../ui/ToolTray";
import { ShowMore, SubSection } from "./ProfileModule";

const FilingIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5V5.625A3.375 3.375 0 0011.25 2.25H6.375A1.875 1.875 0 004.5 4.125v15.75a1.875 1.875 0 001.875 1.875h11.25a1.875 1.875 0 001.875-1.875v-5.625z" />
  </svg>
);

function day(value?: string | null): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" }).format(parsed);
}

/** "4-In Committee" → "In Committee": the Clerk's stage number is not for people. */
function stage(status: string): string {
  return status.replace(/^\d+\s*-\s*/, "");
}

// One filing = one line (decision Item 54): where, how far, and a visible "Proposed" label. The Clerk
// number, the official title and the dates sit behind the tool tray.
function FilingRow({ filing }: { filing: UpcomingZoningFiling }) {
  const { t } = useTranslation("data");
  const headline = filing.segment ? titleCaseAddress(filing.segment) : filing.title;
  return (
    <li className="flex min-w-0 items-start justify-between gap-3 border-t border-dark-border py-2.5 first:border-t-0" data-filing={filing.record_number}>
      <span className="min-w-0">
        <span className="block text-body text-text-primary break-words">{headline}</span>
        <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-text-secondary">
          <span>
            {filing.match_kind === "nearby"
              ? t("regulatory.upcoming.distance", { distance: filing.distance_mi?.toFixed(2) ?? "—" })
              : t("regulatory.upcoming.subjectMatch")}
          </span>
          <StatusLabel tone="neutral" glyph={null}>{t("regulatory.upcoming.proposedStatus", { status: stage(filing.sub_status || filing.status) })}</StatusLabel>
        </span>
      </span>
      <ToolTray
        label={headline}
        dates={
          <span className="block space-y-1">
            <DateLine what={t("regulatory.pendingText.dateIntroduced")} when={day(filing.introduced_at)} />
            <DateLine what={t("regulatory.pendingText.dateLastAction")} when={day(filing.latest_action_at)} />
          </span>
        }
        source={{ href: filing.url, title: `${filing.record_number}: ${filing.title}` }}
        explain={filing.title}
      />
    </li>
  );
}

function FilingList({ filings, limit }: { filings: UpcomingZoningFiling[]; limit: number }) {
  return (
    <ShowMore
      items={filings}
      limit={limit}
      render={(visible) => <ul>{visible.map((filing) => <FilingRow key={filing.record_number} filing={filing} />)}</ul>}
    />
  );
}

export function UpcomingZoningCard({ data }: { data: UpcomingZoningSummary }) {
  const { t } = useTranslation("data");
  const count = data.subject_filings.length + data.nearby_filings.length;
  const title = t("regulatory.upcoming.title");

  return (
    <SubSection
      icon={FilingIcon}
      title={title}
      meta={
        <ToolTray
          label={title}
          dates={<DateLine what={t("regulatory.pendingText.dateChecked")} when={day(data.checked_at)} />}
          explain={t("regulatory.upcoming.disclaimer")}
        />
      }
      className="mb-8"
    >
      {data.status === "unavailable" && (
        <p className="flex items-center gap-1.5 text-caption text-text-secondary">
          <ConfidenceState kind="not_checked" tone="warning" explanation={t("regulatory.upcoming.unavailable")} explainLabel={title} />
        </p>
      )}

      {data.status !== "unavailable" && (
        <>
          {data.status === "stale" && (
            <p className="mb-2 flex items-center gap-1.5 text-caption">
              <StatusLabel tone="warning">{t("regulatory.upcoming.staleShort")}</StatusLabel>
              <ToolTray label={title} explain={t("regulatory.upcoming.stale")} align="start" />
            </p>
          )}
          {data.placement_status === "partial" && (
            <p className="mb-2 flex items-center gap-1.5 text-caption">
              {/* Neutral, not amber: placement is partial citywide, so it says nothing about THIS parcel and
                  would fire on every Profile (amber is for what changes this decision; decision Item 54). */}
              <StatusLabel tone="neutral">{t("regulatory.upcoming.partialShort", { count: data.unplaced_count })}</StatusLabel>
              <ToolTray label={title} explain={t("regulatory.upcoming.partial", { count: data.unplaced_count })} align="start" />
            </p>
          )}
          {count === 0 && data.placement_status === "complete" && (
            <p className="flex flex-wrap items-center gap-1.5 text-caption text-text-secondary" data-testid="upcoming-none">
              <ConfidenceState kind="none_found" />
              <span>{t("regulatory.upcoming.noneNear", { radius: data.radius_mi })}</span>
            </p>
          )}
          {data.subject_filings.length > 0 && (
            <div className="mb-4">
              <h5 className="text-caption font-medium uppercase tracking-wide text-text-muted mb-1">
                {t("regulatory.upcoming.subject")}
              </h5>
              <FilingList filings={data.subject_filings} limit={3} />
            </div>
          )}
          {data.nearby_filings.length > 0 && (
            <div>
              <h5 className="text-caption font-medium uppercase tracking-wide text-text-muted mb-1">
                {t("regulatory.upcoming.nearby", { radius: data.radius_mi })}
              </h5>
              <FilingList filings={data.nearby_filings} limit={4} />
            </div>
          )}
        </>
      )}
    </SubSection>
  );
}
