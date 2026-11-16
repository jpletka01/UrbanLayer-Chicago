// The building records page in the right panel (History, decision Item 103; owner's pick C: a "Records differ" badge
// opens a page). For year built, stories and floor area: each source's value side by side, the one the Profile shows
// marked, the gap named when they differ, and why records can differ. Facts only; we never pick a winner beyond the
// Profile's own order (the Assessor's figure first). "Ask the analyst" last.
import { useTranslation } from "react-i18next";
import { CircleCheck, TriangleAlert } from "lucide-react";
import type { ScorecardResponse } from "../../lib/api";
import { RightDrawer } from "../ui/RightDrawer";
import { Pill } from "../ui/Blocks";
import { useAskHandoff } from "../ask/askContext";
import { ICON, STROKE } from "../icons";
import { BUILDING_FACTS, factRows, factText, rangeText, type BuildingFact, type BuildingRecords } from "./historyModel";

const H3 = "text-caption font-semibold uppercase tracking-wide nx-muted";

export function RecordsPanel({ data, fact, onClose, closing, instant }: {
  data: ScorecardResponse;
  /** The fact whose badge opened the page: listed first. */
  fact?: BuildingFact;
  onClose: () => void;
  closing?: boolean;
  instant?: boolean;
}) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const ask = useAskHandoff();
  const rec = (data.next_ui?.building_records ?? null) as BuildingRecords | null;
  const rows = factRows(data, rec).filter((r) => r.fact !== "units") as Array<ReturnType<typeof factRows>[number] & { fact: BuildingFact }>;
  const order = fact ? [fact, ...BUILDING_FACTS.filter((f) => f !== fact)] : BUILDING_FACTS;
  const AskIcon = ICON.ask;

  return (
    <RightDrawer testId="records-panel" title={t("profile.history.records.title")} onClose={onClose} closing={closing} instant={instant}
      subtitle={<span className="text-caption nx-muted">{t("profile.history.records.subtitle")}</span>}>
      <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto pb-20 pr-1 lg:pb-0">
        {order.map((f) => {
          const row = rows.find((r) => r.fact === f)!;
          const range = row.differs ? rangeText(f, row.sources, lng) : null;
          return (
            <section key={f} className="flex flex-col gap-2" data-fact={f}>
              <h3 className={`${H3} flex items-center gap-2`}>
                {t(`profile.history.fact.${f}`)}
                {row.differs && <Pill tone="yellow" icon={TriangleAlert}>{t("profile.history.records.differ")}</Pill>}
              </h3>
              {row.sources.length === 0 ? (
                <p className="nx-muted">{t("profile.history.records.noneOnRecord")}</p>
              ) : (
                <ul className="flex flex-col divide-y divide-nx-ink/10 rounded-xl bg-nx-block">
                  {row.sources.map((s, i) => (
                    <li key={s.source} className="flex items-start justify-between gap-3 px-3 py-2.5">
                      <span className="flex min-w-0 flex-col">
                        <span className="font-semibold">{t(`profile.history.source.${s.source}`, { defaultValue: s.source })}</span>
                        <span className="text-caption nx-muted">
                          {[t(`profile.history.sourceWhat.${s.source}`, { defaultValue: "" }) || null, s.as_of ? t("profile.history.records.asOf", { year: s.as_of }) : null].filter(Boolean).join(" · ")}
                        </span>
                        {i === 0 && (
                          <span className="mt-1 inline-flex items-center gap-1 text-caption">
                            <CircleCheck aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{t("profile.history.records.shown")}
                          </span>
                        )}
                      </span>
                      <span className="shrink-0 text-body font-semibold tabular-nums">{factText(f, s.value, lng)}{f === "bldg_sqft" ? ` ${t("profile.history.sqft")}` : ""}</span>
                    </li>
                  ))}
                </ul>
              )}
              {range && <p className="text-caption" data-testid={`records-range-${f}`}>{t("profile.history.records.range", { range })}</p>}
            </section>
          );
        })}

        {(rec?.unanswered?.length ?? 0) > 0 && (
          <p className="flex items-start gap-2 text-caption" role="note">
            <TriangleAlert aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} />
            {t("profile.history.records.unanswered", { list: rec!.unanswered.map((s) => t(`profile.history.source.${s}`, { defaultValue: s })).join(", ") })}
          </p>
        )}

        <section className="flex flex-col gap-2">
          <h3 className={H3}>{t("profile.history.records.whyTitle")}</h3>
          <p className="leading-relaxed">{t("profile.history.records.why")}</p>
        </section>

        {ask && (
          <button type="button" disabled={!ask.ready} data-testid="records-ask"
            onClick={() => ask.open(t("profile.history.ask.records", { address: ask.address }))}
            className="mt-auto inline-flex w-fit items-center gap-1.5 text-caption nx-muted underline underline-offset-2 hover:text-nx-ink disabled:no-underline disabled:opacity-60 touch-target">
            <AskIcon aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{ask.ready ? t("term.ask") : t("term.askLater")}
          </button>
        )}
      </div>
    </RightDrawer>
  );
}
