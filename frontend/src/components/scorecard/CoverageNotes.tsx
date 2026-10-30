// "What this page doesn't cover": where the analysis stops for THIS parcel. A screening
// page that never says so reads as a determination. Notes about what was found on this
// parcel (a PD, a landmark, a demolition hold, a recent rezoning, ADU limits) lead; the
// ones true of every parcel (the alderman's role, the map's lag, the code's vintage and
// the City's official letter) sit in a disclosure. Text is translated by note id, with
// the backend's English as the fallback so a new note never renders blank. How current
// the code text is (and the Council amendments passed since) is not a disclosure item: it
// sits with the parcel notes, with the amendment list one click away.
import { useTranslation } from "react-i18next";
import type { CodeCurrency, CoverageNote } from "../../lib/types";
import { AmendmentList } from "./AmendmentList";

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

export function CoverageNotes({ notes, codeCurrency }: { notes?: CoverageNote[] | null; codeCurrency?: CodeCurrency | null }) {
  const { t } = useTranslation("pages");
  if (!notes?.length) return null;
  const parcel = notes.filter((n) => n.applies === "parcel");
  const currency = codeCurrency ? notes.find((n) => n.id === "code_currency") : undefined;
  const general = notes.filter((n) => n.applies === "general" && n !== currency);
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
      {currency && codeCurrency && (
        <div data-testid="coverage-currency">
          <ul>
            <NoteLine note={currency} />
          </ul>
          {codeCurrency.amendments.length > 0 && (
            <details className="mt-1.5" data-testid="coverage-amendments">
              <summary className="cursor-pointer text-caption text-text-muted hover:text-accent transition-colors">
                {t("scorecard.amendments.listSummary", { count: codeCurrency.amendments.length })}
              </summary>
              <div className="mt-2">
                <AmendmentList amendments={codeCurrency.amendments} />
              </div>
            </details>
          )}
        </div>
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
