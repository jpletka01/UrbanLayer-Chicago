// A Build rule's page in the right panel (decision Item 99): clicking a rule chip on the Build tab opens what the
// rule means for this lot, built to be read like Money's program pages (owner: Build's pills should open like Money's):
// whether it applies, what it means here (the City's own code-pinned sentence for each record when there is one),
// the records themselves with their source links, rule-specific facts (FEMA's zone, the transit-served and ADU notes,
// affordable projects in the area), who decides, what it is, the source; "Ask the analyst" last. Facts only (rule 11).
import { useTranslation } from "react-i18next";
import { CircleCheck, CircleDashed, CircleMinus, SquareArrowOutUpRight, TriangleAlert } from "lucide-react";
import type { ScorecardResponse } from "../../lib/api";
import { RightDrawer } from "../ui/RightDrawer";
import { Pill } from "../ui/Blocks";
import { useAskHandoff } from "../ask/askContext";
import { ICON, STROKE } from "../icons";
import type { RuleAnswer } from "./profileModel";
import { ruleDetail, type RuleKey } from "./ruleModel";

const H3 = "text-caption font-semibold uppercase tracking-wide nx-muted";

export function RulePanel({ data, rule, answer, blocks, onClose, closing, instant }: {
  data: ScorecardResponse;
  rule: RuleKey;
  answer: RuleAnswer;
  blocks: boolean;
  onClose: () => void;
  closing?: boolean;
  instant?: boolean;
}) {
  const { t, i18n } = useTranslation("next");
  const ask = useAskHandoff();
  const d = ruleDetail(data, { key: rule, answer, blocks });
  const k = `profile.rule.${rule}`;
  const label = t(`profile.build.rule.${rule}`);
  const AskIcon = ICON.ask;
  // The City's own sentence for each record wins: it is pinned to the code section that says it.
  const cityLines = d.records.map((r) => r.detail).filter((x): x is string => !!x);
  const means =
    answer === "notChecked" ? t("profile.program.notChecked")
    : answer === "no" ? t(`${k}.meansOut`)
    : d.backendNote ?? (cityLines.length && rule !== "flood" ? null : t(`${k}.meansIn`, { zone: d.flood?.zone ?? "" }));

  return (
    <RightDrawer testId="rule-panel" title={label} onClose={onClose} closing={closing} instant={instant}
      subtitle={(
        <span className="mt-1 inline-flex flex-wrap gap-1.5">
          {answer === "yes" ? <Pill tone={blocks ? "yellow" : "blue"} icon={CircleCheck}>{t("profile.rule.status.applies")}</Pill>
            : answer === "no" ? <Pill tone="gray" icon={CircleMinus}>{t("profile.rule.status.doesNot")}</Pill>
            : <Pill tone="gray" icon={CircleDashed}>{t("profile.build.answer.notChecked")}</Pill>}
          {answer === "yes" && blocks && <Pill tone="yellow" icon={TriangleAlert}>{t("profile.rule.status.changesBuild")}</Pill>}
        </span>
      )}>
      <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto pb-20 pr-1 lg:pb-0" data-rule-panel={rule} data-answer={answer}>
        <section className="flex flex-col gap-2">
          <h3 className={H3}>{t("profile.program.forThisLot")}</h3>
          {means && <p className="leading-relaxed" data-testid="rule-means">{means}</p>}
          {answer === "yes" && !d.backendNote && cityLines.length > 0 && rule !== "flood" && (
            <ul className="flex flex-col gap-2" data-testid="rule-means">
              {cityLines.map((line) => <li key={line} className="leading-relaxed">{line}</li>)}
            </ul>
          )}
        </section>

        {answer === "yes" && d.records.length > 0 && (
          <section className="flex flex-col gap-2">
            <h3 className={H3}>{t("profile.rule.records", { count: d.records.length })}</h3>
            <ul className="flex flex-col divide-y divide-nx-ink/5" data-testid="rule-records">
              {d.records.map((r, i) => (
                <li key={`${r.layer_type}-${r.name}-${i}`} className="flex flex-col gap-0.5 py-2 text-caption">
                  <span className="font-semibold">{r.name ?? r.description ?? label}</span>
                  {r.description && r.name && <span className="nx-muted">{r.description}</span>}
                  {r.link && (
                    <a href={r.link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 self-start underline underline-offset-2">
                      {t("profile.rule.readSource")}
                      <SquareArrowOutUpRight aria-hidden className="h-3 w-3" strokeWidth={STROKE} />
                      <span className="sr-only">{t("profile.opensInNewTab")}</span>
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {rule === "flood" && d.flood && answer !== "notChecked" && (
          <dl className="grid grid-cols-2 gap-3" data-testid="flood-facts">
            <Fact label={t("profile.rule.flood.zone")} value={d.flood.zone} note={d.flood.subtype ?? undefined} />
            <Fact label={t("profile.rule.flood.special")}
              value={d.flood.special == null ? "—" : d.flood.special ? t("profile.program.nmtc.severe") : t("profile.program.nmtc.notSevere")} />
          </dl>
        )}

        {rule === "aro" && d.aroNearby && (
          <p className="text-caption" data-testid="aro-nearby">
            {t("profile.rule.aro.nearby", { count: d.aroNearby.projects, units: d.aroNearby.units.toLocaleString(i18n.language.startsWith("es") ? "es-MX" : "en-US") })}
          </p>
        )}

        <section className="flex flex-col gap-2">
          <h3 className={H3}>{t("profile.program.whoDecides")}</h3>
          <p className="text-caption leading-relaxed">{t(`${k}.who`)}</p>
        </section>

        <section className="flex flex-col gap-2">
          <h3 className={H3}>{t("profile.program.whatItIs")}</h3>
          <p className="text-caption leading-relaxed">{t(`${k}.what`)}</p>
        </section>

        <p className="text-caption nx-muted">{t(`${k}.source`)}</p>

        {ask && (
          <button
            type="button"
            disabled={!ask.ready}
            onClick={() => ask.open(t("profile.rule.ask", { rule: label, address: ask.address }))}
            className="mt-auto inline-flex items-center gap-1.5 self-start text-caption nx-muted underline underline-offset-2 hover:text-nx-ink disabled:no-underline disabled:opacity-60 touch-target"
            data-testid="rule-ask"
          >
            <AskIcon aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
            {ask.ready ? t("term.ask") : t("term.askLater")}
          </button>
        )}
      </div>
    </RightDrawer>
  );
}

function Fact({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl bg-nx-block p-3">
      <dt className="text-caption nx-muted">{label}</dt>
      <dd className="text-nx-figure tabular-nums">{value}</dd>
      {note && <dd className="text-caption nx-muted">{note}</dd>}
    </div>
  );
}
