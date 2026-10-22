// The dates behind a page, in words (WS6 M6). The backend (`backend/data_health/vintages.py`) decides which
// dates and of what kind; this only words them in the reader's language, so the Profile footer, the chat
// footer and the PDF cover show the same list. A date we don't have is never invented: a source that gave
// none reads "checked <day we asked>".
import type { TFunction } from "i18next";
import { formatDay } from "./format";

export interface DataDate {
  key: string;
  kind: "record" | "through" | "period" | "checked";
  source_id?: string;
  /** ISO day; for `checked` the day we asked. */
  as_of?: string;
  /** "2020–2024" or "2025": a survey or tax year, where the period is the date. */
  period?: string;
  url?: string;
  /** Code text only: amendments passed since; absent when we couldn't check recently. */
  since?: number;
  since_state?: "fresh" | "aging" | "unknown";
  since_checked_at?: string;
}

/** "Crime through Oct 14, 2026", "ACS (tract) 2020–2024", "Sales checked Oct 22, 2026". */
export function dataDatePhrase(d: DataDate, t: TFunction): string {
  const noun = t(`dataDates.noun.${d.key}`, { defaultValue: d.key });
  const v = d.kind === "period" && d.period ? d.period : formatDay(d.as_of);
  let text = t(`dataDates.${d.kind}`, { noun, v });
  if (d.key === "code_text") {
    if (d.since != null) {
      text += " " + t(d.since_state === "aging" ? "dataDates.sinceAging" : "dataDates.since", {
        count: d.since, d: formatDay(d.since_checked_at),
      });
    } else if (d.since_state === "unknown") {
      text += " " + t("dataDates.sinceUnknown");
    }
  }
  return text;
}
