// "Couldn't check <thing> today" (WS6 M7). A module whose source didn't answer says so, in place, instead of
// disappearing: a missing figure reads as "nothing there", and that is not what happened.
import { useTranslation } from "react-i18next";

export function UncheckedRow({ labels, href, linkLabel, className = "" }: {
  /** What didn't answer, in the backend's words ("property records", "comparable sales"). */
  labels: string[];
  /** Where to look it up yourself, when there is an official place to. */
  href?: string;
  /** The link's words; the City zoning map's when omitted. */
  linkLabel?: string;
  className?: string;
}) {
  const { t } = useTranslation("pages");
  if (labels.length === 0) return null;
  return (
    <div role="status" data-testid="module-unchecked"
      className={`rounded-lg border border-state-warning/25 bg-state-warning/5 px-3 py-2.5 ${className}`}>
      <div className="text-body text-text-primary leading-snug">{t("scorecard.unchecked.title")}</div>
      <div className="text-caption text-text-muted mt-0.5 leading-snug">
        {t("scorecard.unchecked.body", { what: labels.join(", ") })}
        {href && (
          <>
            {" "}
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-link underline">
              {linkLabel ?? t("scorecard.unchecked.mapLink")}
            </a>
          </>
        )}
      </div>
    </div>
  );
}
