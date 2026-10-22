// "Answered Oct 2, 2026 · since then: …" under an assistant answer on a reopened or shared conversation (WS6 M9).
// The date is always there; what follows comes from the server's re-check of the facts the answer rested on
// (never a model call). It loads after the conversation renders, so no spinner: the date shows first.
import { useTranslation } from "react-i18next";
import { formatDate } from "../lib/format";
import { describeChange, hasSinceThenLine, uncheckedWords } from "../lib/sinceThen";
import type { SinceThenResult } from "../lib/types";

interface Props {
  /** When the answer was stored (epoch ms). */
  createdAt: number;
  note?: SinceThenResult;
  /** The held parcel's Profile link (`/scorecard?pin=…`), when the answer resolved one. */
  profileHref?: string | null;
  /** Owner only: send the question again as a normal chat turn. Absent on a shared link. */
  onAskAgain?: () => void;
}

export function AnsweredOnNote({ createdAt, note, profileHref, onAskAgain }: Props) {
  const { t } = useTranslation("chat");
  const date = formatDate(new Date(createdAt).toISOString());
  const answered = t("sinceThen.answeredOn", { date });

  if (note?.status === "changes") {
    return (
      <div className="mt-2 pl-9" data-testid="since-then">
        <p className="text-caption text-text-muted">{answered}</p>
        <div className="mt-1.5 rounded-lg border border-state-warning/40 bg-state-warning/10 px-3 py-2" data-testid="since-then-changes">
          <p className="text-caption font-medium text-text-primary">{t("sinceThen.heading", { date })}</p>
          <ul className="mt-1 space-y-1">
            {note.changes.map((c, i) => {
              const line = describeChange(c, t);
              return (
                <li key={i} className="text-caption text-text-secondary">
                  {line.text}
                  {line.url && line.record && (
                    <>
                      {" "}
                      <a href={line.url} target="_blank" rel="noopener noreferrer" className="text-link hover:underline">
                        {t("sinceThen.recordLink", { record: line.record })}
                      </a>
                    </>
                  )}
                </li>
              );
            })}
          </ul>
          {note.unchecked.length > 0 && (
            <p className="mt-1 text-caption text-text-muted">{t("sinceThen.partial", { what: uncheckedWords(note.unchecked, t) })}</p>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            {profileHref && (
              <a href={profileHref} className="px-2.5 py-1 rounded-md border border-dark-border text-caption text-text-secondary hover:text-accent hover:border-accent/40 transition-colors">
                {t("sinceThen.openProfile")}
              </a>
            )}
            {onAskAgain && (
              <button type="button" onClick={onAskAgain} className="px-2.5 py-1 rounded-md border border-dark-border text-caption text-text-secondary hover:text-accent hover:border-accent/40 transition-colors">
                {t("sinceThen.askAgain")}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  let tail: string | null = null;
  if (note && hasSinceThenLine(note)) {
    if (note.status === "none") tail = t("sinceThen.noChange");
    else if (note.status === "partial") tail = t("sinceThen.partial", { what: uncheckedWords(note.unchecked, t) });
    else if (note.status === "unavailable") tail = t("sinceThen.unavailable");
  }
  return (
    <p className="mt-2 pl-9 text-caption text-text-muted" data-testid="since-then">
      {answered}
      {tail && <> · {tail}</>}
      {note?.reconstructed && tail && <> · {t("sinceThen.rebuilt")}</>}
    </p>
  );
}
