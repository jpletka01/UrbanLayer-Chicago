import { useTranslation } from "react-i18next";
import type { PendingTextImpact, UpcomingZoningSummary } from "../../lib/types";
import { ConfidenceState } from "../ui/ConfidenceState";
import { StatusLabel } from "../ui/StatusLabel";
import { DateLine, ToolTray } from "../ui/ToolTray";
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

/** "4-In Committee Referred" → "In Committee Referred": the Clerk's stage number is not for people. */
function stage(status: string): string {
  return status.replace(/^\d+\s*-\s*/, "");
}

// One proposal = one line (decision Item 54): the rule it would change, in words, and today's value.
// The Clerk number, the official title, the dates, the code sections and the explanation sit behind the
// tool tray instead of being printed. "Proposed" stays a visible label: a proposal is never law.
function ImpactRow({ impact }: { impact: PendingTextImpact }) {
  const { t } = useTranslation("data");
  const fact = impact.effects[0]?.affected[0];
  const headline = fact?.label ?? impact.title;
  const today = fact && fact.current_value != null && fact.current_value !== "" ? String(fact.current_value) : null;
  const sections = [...new Set(impact.effects.flatMap((e) => e.sections))];
  const untested = impact.effects.some((e) => e.reach === "untested");
  return (
    <li className="flex min-w-0 items-start justify-between gap-3 border-t border-dark-border py-2.5 first:border-t-0" data-impact={impact.record_number}>
      <span className="min-w-0">
        <span className="block text-body text-text-primary break-words">{headline}</span>
        <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-text-secondary">
          {today && <span>{t("regulatory.pendingText.todayValue", { value: today })}</span>}
          <StatusLabel tone="neutral" glyph={null}>{t("regulatory.pendingText.proposedStatus", { status: stage(impact.sub_status || impact.status) })}</StatusLabel>
          {untested && <StatusLabel tone="neutral" glyph={null}>{t("regulatory.pendingText.untested")}</StatusLabel>}
        </span>
      </span>
      <ToolTray
        label={headline}
        dates={
          <span className="block space-y-1">
            <DateLine what={t("regulatory.pendingText.dateIntroduced")} when={day(impact.introduced_at)} />
            <DateLine what={t("regulatory.pendingText.dateLastAction")} when={day(impact.latest_action_at)} />
            <DateLine what={t("regulatory.pendingText.dateReviewed")} when={dateOnly(impact.reviewed_on)} />
          </span>
        }
        code={sections.length ? <span className="font-mono">{sections.map((s) => `§${s}`).join(", ")}</span> : undefined}
        source={{ href: impact.url, title: `${impact.record_number}: ${impact.title}` }}
        explain={
          <span className="block space-y-2">
            {impact.effects.map((effect) => (
              <span key={effect.id} className="block">
                <span className="block font-medium text-text-primary">{t("regulatory.pendingText.couldChange")}</span>
                <span className="block first-letter:uppercase">{effect.could_change}</span>
                {effect.reach === "untested" && effect.reach_note && <span className="mt-1 block text-text-muted">{effect.reach_note}</span>}
              </span>
            ))}
            <span className="block">
              <span className="block font-medium text-text-primary">{t("regulatory.pendingText.today")}</span>
              {impact.effects.flatMap((e) => e.affected).map((f) => (
                <span key={f.fact_id} className="block break-words">
                  {f.current_value != null && f.current_value !== ""
                    ? t("regulatory.pendingText.valueOf", { label: f.label, value: String(f.current_value) })
                    : <><span className="text-text-primary">{f.label}.</span> {f.current_law}</>}
                </span>
              ))}
            </span>
            {impact.summary && <span className="block text-text-muted">{impact.summary}</span>}
          </span>
        }
      />
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
  const unavailable = review.status === "unavailable";
  const title = t("regulatory.pendingText.title");

  return (
    <SubSection
      icon={ChangeIcon}
      title={title}
      meta={
        <ToolTray
          label={title}
          dates={<DateLine what={t("regulatory.pendingText.dateChecked")} when={day(data.checked_at)} />}
          explain={t("regulatory.pendingText.disclaimer")}
        />
      }
      className="mb-8"
    >
      {unavailable && (
        <p className="flex items-center gap-1.5 text-caption text-text-secondary">
          <ConfidenceState kind="not_checked" tone="warning" explanation={t("regulatory.pendingText.unavailable")} explainLabel={title} />
        </p>
      )}

      {!unavailable && (
        <>
          {data.status === "stale" && (
            <p className="mb-2 flex items-center gap-1.5 text-caption text-text-secondary">
              <StatusLabel tone="warning">{t("regulatory.pendingText.staleShort")}</StatusLabel>
              <ToolTray label={title} explain={t("regulatory.pendingText.stale")} align="start" />
            </p>
          )}
          {review.status === "incomplete" && (
            <p className="mb-2 flex flex-wrap items-center gap-1.5 text-caption text-text-secondary">
              <StatusLabel tone="warning">{t("regulatory.pendingText.incompleteShort", { count: review.unreviewed.length })}</StatusLabel>
              <ToolTray
                label={title}
                align="start"
                explain={
                  <span className="block space-y-1">
                    <span className="block">{t("regulatory.pendingText.incomplete", { count: review.unreviewed.length })}</span>
                    {review.unreviewed.map((u) => (
                      <span key={u.record_number} className="block break-words">
                        <a href={u.url} target="_blank" rel="noopener noreferrer" className="text-link hover:underline">{u.record_number}</a>
                        {" — "}
                        {u.reason === "outdated" ? t("regulatory.pendingText.reasonOutdated") : t("regulatory.pendingText.reasonUnreviewed")}
                        {u.waiting_days != null && ` (${t("regulatory.pendingText.waiting", { days: u.waiting_days })})`}
                      </span>
                    ))}
                  </span>
                }
              />
            </p>
          )}
          {impacts.length === 0 && review.status === "complete" && (
            <p className="flex flex-wrap items-center gap-1.5 text-caption text-text-secondary" data-testid="pending-none">
              <ConfidenceState kind="none_found" />
              <span>
                {review.pending_count === 0
                  ? t("regulatory.pendingText.emptyNone")
                  : t("regulatory.pendingText.noneApply", { count: review.pending_count })}
              </span>
            </p>
          )}
          {impacts.length > 0 && (
            <>
              <p className="mb-1 text-caption text-text-secondary">{t("regulatory.pendingText.count", { count: impacts.length })}</p>
              <ShowMore
                items={impacts}
                limit={3}
                render={(visible) => (
                  <ul>
                    {visible.map((impact) => <ImpactRow key={impact.record_number} impact={impact} />)}
                  </ul>
                )}
              />
            </>
          )}
        </>
      )}
    </SubSection>
  );
}
