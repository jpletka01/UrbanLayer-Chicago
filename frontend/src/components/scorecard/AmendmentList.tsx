// The Council amendments passed after the Municipal Code text's vintage, one row each:
// date · record (linked to the Clerk) · the reviewed summary (the ordinance title until
// someone has read it) · whether this page reflects it. The Profile's coverage note and
// the section viewers share it, so the same amendment never reads two ways.
import { useTranslation } from "react-i18next";
import { formatDay } from "../../lib/format";
import type { Amendment } from "../../lib/types";

/** applied → reflected; pending / never reviewed → not yet reviewed; reviewed, no change → not reflected. */
export function amendmentStatus(a: Pick<Amendment, "review_status" | "product_effect">): "applied" | "none" | "pending" {
  if (a.review_status !== "reviewed" || a.product_effect === "pending" || !a.product_effect) return "pending";
  return a.product_effect === "applied" ? "applied" : "none";
}

export function RecordLink({ a }: { a: Pick<Amendment, "record" | "url"> }) {
  return a.url ? (
    <a href={a.url} target="_blank" rel="noopener noreferrer" className="font-mono text-text-primary underline hover:text-accent">
      {a.record}
    </a>
  ) : (
    <span className="font-mono">{a.record}</span>
  );
}

export function AmendmentList({ amendments }: { amendments: Amendment[] }) {
  const { t } = useTranslation("pages");
  return (
    <ul className="space-y-2" data-testid="amendment-list">
      {amendments.map((a) => {
        const status = amendmentStatus(a);
        return (
          <li key={a.record} className="text-caption text-text-secondary leading-snug" data-testid={`amendment-${a.record}`}>
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-text-muted">{formatDay(a.passed_on)}</span>
              <RecordLink a={a} />
              <span
                className={status === "applied" ? "text-state-positive" : status === "pending" ? "text-state-warning" : "text-text-muted"}
                data-testid={`amendment-status-${a.record}`}
              >
                · {t(`scorecard.amendments.status.${status}`)}
              </span>
            </div>
            <div className="mt-0.5">{a.summary || a.title}</div>
          </li>
        );
      })}
    </ul>
  );
}
