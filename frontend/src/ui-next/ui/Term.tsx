// A label that defines itself (decision Item 99): the words stay plain on the page; a small Info icon beside them
// opens a popover with a one- or two-sentence definition and "Ask about this", which opens the Ask drawer with a
// question about this lot already written (not sent). One idiom for every block title and rule chip, so a
// definition is always one click away and never printed on the page.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Toggletip } from "../../components/ui/Toggletip";
import { useAskHandoff } from "../ask/askContext";
import { ICON, STROKE } from "../icons";

export function Term({ label, definition, question, children }: {
  /** The term as the visitor reads it ("Rent nearby"). */
  label: string;
  definition: ReactNode;
  /** The question "Ask about this" writes, with `{{address}}` filled in by the caller. */
  question?: string;
  /** What shows on the page; the label when omitted. */
  children?: ReactNode;
}) {
  const { t } = useTranslation("next");
  const ask = useAskHandoff();
  const AskIcon = ICON.ask;
  return (
    <span className="inline-flex items-center gap-1">
      {children ?? label}
      <Toggletip label={t("term.what", { term: label })}>
        <span className="flex flex-col gap-2" data-term={label}>
          <span>{definition}</span>
          {ask && question && (
            <button
              type="button"
              disabled={!ask.ready}
              onClick={() => ask.open(question)}
              className="inline-flex items-center gap-1.5 self-start font-medium underline underline-offset-2 disabled:no-underline disabled:opacity-60 touch-target"
              data-testid="term-ask"
            >
              <AskIcon aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
              {ask.ready ? t("term.ask") : t("term.askLater")}
            </button>
          )}
        </span>
      </Toggletip>
    </span>
  );
}
