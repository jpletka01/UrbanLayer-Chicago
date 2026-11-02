// ToolTray — the page's fixed set of tools (decision Item 54; Jack, 2026-11-02): evidence lives one click
// away, always behind the same icon, in the same order, instead of printed as text. Each tool is a real
// button or link with an accessible name; icons are neutral and turn orange on hover/focus (orange =
// clickable). Order: Dates · Code · Official record · Explain · Ask.
//
//   Calendar          every date for this item, each with its plain meaning
//   Scale             the Municipal Code rule(s) behind it
//   SquareArrowOut…   the official record (Clerk filing, Assessor page, City map), opened in a new tab
//   Info              what it means, in a sentence or two
//   MessageCircle?    ask the analyst about this item
import type { ReactNode } from "react";
import { MessageCircleQuestion, SquareArrowOutUpRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Toggletip } from "./Toggletip";

export interface ToolTrayProps {
  /** Names the item for every tool's accessible name ("Dates: Minimum lot area per unit"). */
  label: string;
  dates?: ReactNode;
  /** Text kept visible beside the calendar (a year that changes the decision). */
  datesVisible?: string;
  code?: ReactNode;
  source?: { href: string; title?: string };
  explain?: ReactNode;
  onAsk?: () => void;
  align?: "start" | "end";
}

export function ToolTray({ label, dates, datesVisible, code, source, explain, onAsk, align = "end" }: ToolTrayProps) {
  const { t } = useTranslation("common");
  return (
    <span className="inline-flex shrink-0 items-center gap-0.5" data-tool-tray>
      {dates != null && (
        <Toggletip kind="date" label={t("tools.dates", { label })} visible={datesVisible} align={align}>{dates}</Toggletip>
      )}
      {code != null && <Toggletip kind="code" label={t("tools.code", { label })} align={align}>{code}</Toggletip>}
      {source && (
        <a
          href={source.href}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={t("tools.source", { label })}
          title={source.title ?? t("tools.source", { label })}
          className="inline-flex items-center rounded px-0.5 text-text-muted cursor-pointer transition-colors hover:text-link focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={2} />
        </a>
      )}
      {explain != null && <Toggletip kind="info" label={t("tools.explain", { label })} align={align}>{explain}</Toggletip>}
      {onAsk && (
        <button
          type="button"
          onClick={onAsk}
          aria-label={t("tools.ask", { label })}
          className="inline-flex items-center rounded px-0.5 text-text-muted cursor-pointer transition-colors hover:text-link focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <MessageCircleQuestion aria-hidden className="h-3.5 w-3.5" strokeWidth={2} />
        </button>
      )}
    </span>
  );
}

/** One line inside a Dates tool: what the date means, then the date. */
export function DateLine({ what, when }: { what: string; when: string | null | undefined }) {
  if (!when) return null;
  return (
    <span className="flex justify-between gap-3">
      <span>{what}</span>
      <span className="shrink-0 tabular-nums text-text-primary">{when}</span>
    </span>
  );
}
