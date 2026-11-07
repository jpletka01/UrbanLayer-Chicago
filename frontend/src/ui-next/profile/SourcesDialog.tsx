// Sources (the top bar's Sources tool): the page's dated sources, what couldn't be checked, and every figure's
// provenance from the backend's own map. Same content as today's "Sources & coverage" sheet, in the new frame.
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { SquareArrowOutUpRight, X } from "lucide-react";
import type { ScorecardResponse } from "../../lib/api";
import { confidenceStateFor, sourceBullets } from "../../lib/confidence";
import { dataDatePhrase } from "../../lib/dataDates";
import { ConfidenceState } from "../../components/ui/ConfidenceState";
import { STROKE } from "../icons";

export function SourcesDialog({ data, open, onOpenChange }: { data: ScorecardResponse; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t } = useTranslation("next");
  const { t: tc } = useTranslation("common");
  const prov = data.provenance ?? {};
  const facts = Object.keys(prov).sort((a, b) => (prov[a].label ?? a).localeCompare(prov[b].label ?? b));
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <div className="ui-next">
          <Dialog.Overlay className="fixed inset-0 z-[65] bg-black/30" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-[66] flex max-h-[85dvh] w-[min(640px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 flex-col gap-4 rounded-2xl bg-nx-page p-6 text-body text-nx-ink shadow-[0_8px_32px_rgb(0_0_0/0.2)]">
            <div className="flex items-start justify-between gap-3">
              <Dialog.Title className="text-body font-semibold">{t("sources.title")}</Dialog.Title>
              <Dialog.Close aria-label={t("sources.close")} className="grid h-8 w-8 place-items-center rounded-lg hover:bg-nx-ink/5 touch-target">
                <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
              </Dialog.Close>
            </div>
            <Dialog.Description className="text-caption nx-muted">{t("sources.description")}</Dialog.Description>
            <div className="min-h-0 space-y-5 overflow-y-auto pr-1 text-caption" data-testid="next-sources">
              {(data.data_dates ?? []).length > 0 && (
                <section>
                  <h3 className="mb-1.5 font-semibold">{t("sources.dates")}</h3>
                  <ul className="space-y-0.5">
                    {data.data_dates!.map((d) => <li key={d.key}>{dataDatePhrase(d, tc)}</li>)}
                  </ul>
                </section>
              )}
              {(data.failed_sources ?? []).length > 0 && (
                <section>
                  <h3 className="mb-1.5 font-semibold">{t("sources.notChecked")}</h3>
                  <ul className="space-y-0.5">
                    {data.failed_sources!.flatMap((f) => f.labels).map((l) => <li key={l}>{l}</li>)}
                  </ul>
                </section>
              )}
              <section>
                <h3 className="mb-1.5 font-semibold">{t("sources.figures")}</h3>
                <ul className="space-y-3">
                  {facts.map((id) => {
                    const entry = prov[id];
                    const state = confidenceStateFor(entry);
                    return (
                      <li key={id} className="border-t border-nx-ink/10 pt-2.5 first:border-t-0 first:pt-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="font-medium">{entry.label}</span>
                          {state && <ConfidenceState kind={state.kind} low={state.low} />}
                        </div>
                        {entry.source && <p className="mt-0.5">{entry.source}</p>}
                        <ul className="mt-1 space-y-0.5 nx-muted">
                          {sourceBullets(entry, tc).map((b, i) => <li key={i}>{b}</li>)}
                        </ul>
                        {entry.url && (
                          <a href={entry.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 underline underline-offset-2">
                            {t("sources.open")}
                            <SquareArrowOutUpRight aria-hidden className="h-3 w-3" strokeWidth={STROKE} />
                          </a>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </section>
            </div>
          </Dialog.Content>
        </div>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
