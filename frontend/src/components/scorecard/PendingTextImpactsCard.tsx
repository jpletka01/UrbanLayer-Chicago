import { useTranslation } from "react-i18next";
import type {
  PendingTextAffectedFact,
  PendingTextEffect,
  PendingTextImpact,
  UpcomingZoningSummary,
} from "../../lib/types";
import { ShowMore, SubSection } from "./ProfileModule";

const ChangeIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden>
    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
  </svg>
);

function day(value?: string | null): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" }).format(parsed);
}

/** A YYYY-MM-DD review date has no time zone: build it from its parts so it never slips a day. */
function dateOnly(value: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!m) return day(value) ?? value;
  return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" })
    .format(new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
}

function FactToday({ fact }: { fact: PendingTextAffectedFact }) {
  const { t } = useTranslation("data");
  if (fact.current_value != null && fact.current_value !== "") {
    return (
      <li className="break-words">
        {t("regulatory.pendingText.valueOf", { label: fact.label, value: String(fact.current_value) })}
        {fact.section && <span className="text-text-muted"> (§{fact.section})</span>}
      </li>
    );
  }
  return (
    <li className="break-words">
      <span className="text-text-primary">{fact.label}.</span> {fact.current_law}
    </li>
  );
}

function Effect({ effect }: { effect: PendingTextEffect }) {
  const { t } = useTranslation("data");
  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2 sm:gap-4">
      <div className="rounded-lg border border-state-warning/30 bg-state-warning/5 px-3 py-2.5 min-w-0">
        <h6 className="text-caption font-medium uppercase tracking-wide text-text-muted mb-1">
          {t("regulatory.pendingText.couldChange")}
        </h6>
        <p className="text-body text-text-secondary leading-snug break-words first-letter:uppercase">{effect.could_change}</p>
        <p className="text-caption text-text-muted mt-1.5 break-words">
          {t("regulatory.pendingText.sections")}: {effect.sections.map((s) => `§${s}`).join(", ")}
        </p>
        {effect.reach === "untested" && (
          <p className="text-caption text-text-secondary mt-1.5 break-words">
            <span className="font-medium">{t("regulatory.pendingText.untested")}.</span>{" "}
            {effect.reach_note}
          </p>
        )}
      </div>
      <div className="rounded-lg border border-dark-border bg-dark-elevated/40 px-3 py-2.5 min-w-0">
        <h6 className="text-caption font-medium uppercase tracking-wide text-text-muted mb-1">
          {t("regulatory.pendingText.today")}
        </h6>
        <ul className="text-body text-text-secondary leading-snug space-y-1">
          {effect.affected.map((fact) => <FactToday key={fact.fact_id} fact={fact} />)}
        </ul>
      </div>
    </div>
  );
}

function ImpactRow({ impact }: { impact: PendingTextImpact }) {
  const { t } = useTranslation("data");
  const when = day(impact.latest_action_at ?? impact.introduced_at);
  return (
    <li className="rounded-lg border border-dark-border px-3 py-3 min-w-0">
      <div className="flex flex-wrap items-start gap-x-3 gap-y-1">
        <a href={impact.url} target="_blank" rel="noopener noreferrer"
          className="text-body font-medium text-text-primary hover:text-accent transition-colors break-all">
          {impact.record_number}
        </a>
        <span className="text-caption text-text-muted">
          {t("regulatory.pendingText.pending", { status: impact.sub_status || impact.status })}
        </span>
        {when && <span className="text-caption text-text-muted">{t("regulatory.pendingText.updated", { date: when })}</span>}
      </div>
      <p className="text-body text-text-secondary leading-snug mt-1 break-words">{impact.title}</p>
      {impact.effects.map((effect) => <Effect key={effect.id} effect={effect} />)}
      {impact.summary && (
        <details className="mt-3 text-caption text-text-secondary">
          <summary className="cursor-pointer text-text-muted hover:text-text-secondary">
            {t("regulatory.pendingText.summaryToggle")}
          </summary>
          <p className="mt-1.5 leading-snug break-words">{impact.summary}</p>
        </details>
      )}
      <p className="text-caption text-text-muted mt-2.5">
        {t("regulatory.pendingText.reviewed", { date: dateOnly(impact.reviewed_on) })}
        {" · "}
        <a href={impact.url} target="_blank" rel="noopener noreferrer" className="hover:text-text-secondary underline underline-offset-2">
          {t("regulatory.pendingText.official")}
        </a>
      </p>
    </li>
  );
}

/** Pending Title 17 amendments a committed review maps to this property. Always beside — never
    in place of — the current-law figures; "complete" is the only state that may say none map. */
export function PendingTextImpactsCard({ data }: { data: UpcomingZoningSummary }) {
  const { t } = useTranslation("data");
  const review = data.text_review;
  if (!review) return null;
  const impacts = data.text_impacts ?? [];
  const checked = day(data.checked_at);
  const unavailable = review.status === "unavailable";

  return (
    <SubSection
      icon={ChangeIcon}
      title={t("regulatory.pendingText.title")}
      meta={checked ? t("regulatory.pendingText.checked", { date: checked }) : undefined}
      className="mb-8"
    >
      <p className="text-caption text-text-muted mb-3">{t("regulatory.pendingText.disclaimer")}</p>

      {unavailable && (
        <div className="rounded-lg border border-state-warning/30 bg-state-warning/5 px-3 py-2.5 text-body text-text-secondary">
          {t("regulatory.pendingText.unavailable")}
        </div>
      )}

      {!unavailable && (
        <>
          {data.status === "stale" && (
            <div className="rounded-lg border border-state-warning/30 bg-state-warning/5 px-3 py-2.5 text-body text-text-secondary mb-3">
              {t("regulatory.pendingText.stale")}
            </div>
          )}
          {review.status === "incomplete" && (
            <div className="rounded-lg border border-state-warning/30 bg-state-warning/5 px-3 py-2.5 text-body text-text-secondary mb-3">
              <p>{t("regulatory.pendingText.incomplete", { count: review.unreviewed.length })}</p>
              <ul className="mt-1.5 space-y-1 text-caption text-text-muted">
                {review.unreviewed.map((u) => (
                  <li key={u.record_number} className="break-words">
                    <a href={u.url} target="_blank" rel="noopener noreferrer"
                      className="text-text-secondary hover:text-accent break-all">{u.record_number}</a>
                    {" — "}
                    {u.reason === "outdated" ? t("regulatory.pendingText.reasonOutdated") : t("regulatory.pendingText.reasonUnreviewed")}
                    {u.waiting_days != null && ` (${t("regulatory.pendingText.waiting", { days: u.waiting_days })})`}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {impacts.length === 0 && review.status === "complete" && (
            <div className="rounded-lg border border-dark-border bg-dark-elevated/40 px-3 py-2.5 text-body text-text-secondary">
              {review.pending_count === 0
                ? t("regulatory.pendingText.emptyNone")
                : t("regulatory.pendingText.empty", { count: review.pending_count })}
            </div>
          )}
          {impacts.length > 0 && (
            <ShowMore
              items={impacts}
              limit={3}
              render={(visible) => (
                <ul className="space-y-3">
                  {visible.map((impact) => <ImpactRow key={impact.record_number} impact={impact} />)}
                </ul>
              )}
            />
          )}
        </>
      )}
    </SubSection>
  );
}
