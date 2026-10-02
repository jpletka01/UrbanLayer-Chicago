// "What this page doesn't cover": where the analysis stops for THIS parcel. A screening
// page that never says so reads as a determination. Notes about what was found on this
// parcel (a PD, a landmark, a demolition hold, a recent rezoning, ADU limits) lead; the
// ones true of every parcel (the alderman's role, the map's lag, the code's vintage and
// the City's official letter) sit in a disclosure. Text is translated by note id, with
// the backend's English as the fallback so a new note never renders blank.
import { useTranslation } from "react-i18next";
import type { CoverageNote } from "../../lib/types";

function NoteLine({ note }: { note: CoverageNote }) {
  const { t } = useTranslation("pages");
  const text = t(`scorecard.coverage.notes.${note.id}`, { ...note.params, defaultValue: note.text });
  return (
    <li className="text-caption text-text-secondary leading-snug" data-testid={`coverage-${note.id}`}>
      {text}
      {note.link && (
        <>
          {" "}
          <a href={note.link} target="_blank" rel="noopener noreferrer" className="text-text-primary underline hover:text-accent">
            {t("scorecard.coverage.link")}
          </a>
        </>
      )}
    </li>
  );
}

export function CoverageNotes({ notes }: { notes?: CoverageNote[] | null }) {
  const { t } = useTranslation("pages");
  if (!notes?.length) return null;
  const parcel = notes.filter((n) => n.applies === "parcel");
  const general = notes.filter((n) => n.applies === "general");
  return (
    <div className="rounded-lg border border-border-subtle px-3 py-2.5 space-y-2" data-testid="coverage-notes">
      <div className="text-caption font-medium text-text-primary">{t("scorecard.coverage.title")}</div>
      {parcel.length > 0 && (
        <ul className="space-y-1.5" data-testid="coverage-parcel">
          {parcel.map((n) => (
            <NoteLine key={n.id} note={n} />
          ))}
        </ul>
      )}
      {general.length > 0 && (
        <details data-testid="coverage-general">
          <summary className="cursor-pointer text-caption text-text-muted hover:text-accent transition-colors">
            {t("scorecard.coverage.always", { count: general.length })}
          </summary>
          <ul className="mt-1.5 space-y-1.5">
            {general.map((n) => (
              <NoteLine key={n.id} note={n} />
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
