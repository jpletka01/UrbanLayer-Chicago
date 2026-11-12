// An answer's sources as a short list, one open at a time (brief "Chat"): each Municipal Code passage shown as what it
// is, a quote of the code with its section, and any amendment the Council passed after the text's date. A numbered
// pill in the answer opens its source here.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown } from "lucide-react";
import type { CodeChunk } from "../../lib/types";
import { STROKE } from "../icons";

export function SourcesList({ chunks, openIndex }: { chunks: CodeChunk[]; openIndex: number | null }) {
  const { t, i18n } = useTranslation("next");
  const [open, setOpen] = useState<number | null>(openIndex ?? (chunks.length === 1 ? 0 : null));
  const rows = useRef<Array<HTMLLIElement | null>>([]);
  useEffect(() => {
    if (openIndex == null) return;
    setOpen(openIndex);
    rows.current[openIndex]?.scrollIntoView?.({ block: "nearest" });
  }, [openIndex]);

  const dateFmt = new Intl.DateTimeFormat(i18n.language.startsWith("es") ? "es-MX" : "en-US", { month: "short", day: "numeric", year: "numeric" });

  return (
    <ol className="flex flex-col gap-2" data-testid="chat-sources">
      {chunks.map((c, i) => {
        const isOpen = open === i;
        const name = c.section_title ? `§ ${c.section} · ${c.section_title}` : `§ ${c.section}`;
        return (
          <li key={i} ref={(el) => { rows.current[i] = el; }} className={`rounded-2xl ${isOpen ? "bg-nx-block" : "ring-1 ring-nx-ink/10"}`}>
            <button
              type="button"
              aria-expanded={isOpen}
              onClick={() => setOpen(isOpen ? null : i)}
              className="flex w-full items-center gap-3 px-3 py-2.5 text-left touch-target"
            >
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-nx-pill-purple-bg text-caption font-semibold text-nx-pill-purple">{i + 1}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{name}</span>
                <span className="block text-caption nx-muted">{t("chat.codeSource")}</span>
              </span>
              <ChevronDown aria-hidden className={`h-4 w-4 shrink-0 transition-transform ${isOpen ? "rotate-180" : ""}`} strokeWidth={STROKE} />
            </button>
            {isOpen && (
              <div className="flex flex-col gap-2 px-3 pb-3 pl-12">
                <blockquote className="whitespace-pre-line border-l-2 border-nx-ai-a pl-3 text-caption leading-relaxed">{c.text}</blockquote>
                {(c.amended_since?.length ?? 0) > 0 && (
                  <p className="rounded-lg bg-nx-pill-yellow-bg px-2 py-1 text-caption text-nx-pill-yellow">
                    {t("chat.amendedSince", { count: c.amended_since!.length, date: dateFmt.format(new Date(`${c.amended_since![0].passed_on}T12:00:00`)) })}
                  </p>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
