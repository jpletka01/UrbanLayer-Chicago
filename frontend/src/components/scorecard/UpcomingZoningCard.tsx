import { useTranslation } from "react-i18next";
import type { UpcomingZoningFiling, UpcomingZoningSummary } from "../../lib/types";
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

function FilingRow({ filing }: { filing: UpcomingZoningFiling }) {
  const { t } = useTranslation("data");
  const when = day(filing.latest_action_at ?? filing.introduced_at);
  return (
    <li className="rounded-lg border border-dark-border bg-dark-elevated/40 px-3 py-3 min-w-0">
      <div className="flex flex-wrap items-start gap-x-3 gap-y-1">
        <a href={filing.url} target="_blank" rel="noopener noreferrer"
          className="text-body font-medium text-text-primary hover:text-accent transition-colors break-all">
          {filing.record_number}
        </a>
        <span className="text-caption text-text-muted">
          {filing.match_kind === "nearby"
            ? t("regulatory.upcoming.distance", { distance: filing.distance_mi?.toFixed(2) ?? "—" })
            : t("regulatory.upcoming.subjectMatch")}
        </span>
      </div>
      <p className="text-body text-text-secondary leading-snug mt-1 break-words">{filing.title}</p>
      <div className="text-caption text-text-muted mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
        <span>{filing.sub_status || filing.status}</span>
        {filing.segment && <span>{filing.segment}</span>}
        {when && <span>{t("regulatory.upcoming.updated", { date: when })}</span>}
      </div>
    </li>
  );
}

function FilingList({ filings, limit }: { filings: UpcomingZoningFiling[]; limit: number }) {
  return (
    <ShowMore
      items={filings}
      limit={limit}
      render={(visible) => <ul className="space-y-2">{visible.map((filing) => <FilingRow key={filing.record_number} filing={filing} />)}</ul>}
    />
  );
}

export function UpcomingZoningCard({ data }: { data: UpcomingZoningSummary }) {
  const { t } = useTranslation("data");
  const checked = day(data.checked_at);
  const count = data.subject_filings.length + data.nearby_filings.length;

  return (
    <SubSection
      icon={FilingIcon}
      title={t("regulatory.upcoming.title")}
      meta={checked ? t("regulatory.upcoming.checked", { date: checked }) : undefined}
      className="mb-8"
    >
      <p className="text-caption text-text-muted mb-3">{t("regulatory.upcoming.disclaimer")}</p>

      {data.status === "unavailable" && (
        <div className="rounded-lg border border-state-warning/30 bg-state-warning/5 px-3 py-2.5 text-body text-text-secondary">
          {t("regulatory.upcoming.unavailable")}
        </div>
      )}

      {data.status !== "unavailable" && (
        <>
          {data.status === "stale" && (
            <div className="rounded-lg border border-state-warning/30 bg-state-warning/5 px-3 py-2.5 text-body text-text-secondary mb-3">
              {t("regulatory.upcoming.stale")}
            </div>
          )}
          {data.placement_status === "partial" && (
            <div className="rounded-lg border border-state-warning/20 bg-state-warning/5 px-3 py-2.5 text-caption text-text-secondary mb-3">
              {t("regulatory.upcoming.partial", { count: data.unplaced_count })}
            </div>
          )}
          {count === 0 && data.placement_status === "complete" && (
            <div className="rounded-lg border border-dark-border bg-dark-elevated/40 px-3 py-2.5 text-body text-text-secondary">
              {t("regulatory.upcoming.empty", { radius: data.radius_mi })}
            </div>
          )}
          {data.subject_filings.length > 0 && (
            <div className="mb-5">
              <h5 className="text-caption font-medium uppercase tracking-wide text-text-muted mb-2">
                {t("regulatory.upcoming.subject")}
              </h5>
              <FilingList filings={data.subject_filings} limit={3} />
            </div>
          )}
          {data.nearby_filings.length > 0 && (
            <div>
              <h5 className="text-caption font-medium uppercase tracking-wide text-text-muted mb-2">
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
