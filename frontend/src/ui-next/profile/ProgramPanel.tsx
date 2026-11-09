// A program's page in the right panel (decision Item 99): clicking an incentive chip on the Money tab opens what
// that program means for this lot, built to be read (owner: questions cost money, so reading should be enough):
// what it means here, the program's own figures, the projects a TIF has paid for, City grants in the area, who
// decides, and the source; "Ask the analyst" is last and quiet. Facts only, no advice (rule 11).
import { useTranslation } from "react-i18next";
import { CircleCheck, CircleDashed, CircleMinus, LoaderCircle, RotateCw, SquareArrowOutUpRight } from "lucide-react";
import type { ScorecardResponse } from "../../lib/api";
import { RightDrawer } from "../ui/RightDrawer";
import { Pill } from "../ui/Blocks";
import { useAskHandoff } from "../ask/askContext";
import { ICON, STROKE } from "../icons";
import { niceCeil, usd, type IncentiveAnswer, type IncentiveKey, type LateBlockState } from "./moneyModel";
import { numLocale } from "./profileModel";
import { programDetail, tractLabel, type FundYear } from "./programModel";

/** The City's own dataset of TIF-funded projects (annual reports), for the record behind the list. */
const TIF_PROJECTS_URL = "https://data.cityofchicago.org/d/72uz-ikdv";

const usdShort = (n: number, lng: string) =>
  new Intl.NumberFormat(numLocale(lng), { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(n);

export function ProgramPanel({ data, program, answer, reports = "ready", onRetry, onClose, closing, instant }: {
  data: ScorecardResponse;
  /** The late `incentives` part: a TIF's reports and grants (and QCT, NMTC) come with it (Item 89). */
  reports?: LateBlockState;
  onRetry?: () => void;
  program: IncentiveKey;
  answer: IncentiveAnswer;
  onClose: () => void;
  closing?: boolean;
  instant?: boolean;
}) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const ask = useAskHandoff();
  const d = programDetail(data, program, answer);
  const k = `profile.program.${program}`;
  const label = t(`profile.money.incentives.program.${program}`);
  const title = program === "tif" && d.name && answer === "yes" ? t("profile.program.tif.named", { name: d.name })
    : program === "ez" && d.name && answer === "yes" ? d.name : label;
  const tract = tractLabel(d.tract);
  const AskIcon = ICON.ask;

  return (
    <RightDrawer testId="program-panel" title={title} onClose={onClose} closing={closing} instant={instant}
      subtitle={<span className="mt-1 inline-flex"><StatusPill answer={answer} /></span>}>
      <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto pb-20 pr-1 lg:pb-0" data-program={program} data-answer={answer}>
        <section className="flex flex-col gap-2">
          <h3 className="text-caption font-semibold uppercase tracking-wide nx-muted">{t("profile.program.forThisLot")}</h3>
          <p className="leading-relaxed" data-testid="program-means">
            {answer === "yes" ? t(`${k}.meansIn`, { name: d.name ?? label, tract: tract ?? "" })
              : answer === "no" ? t(`${k}.meansOut`)
              : answer === "checking" ? t("profile.program.checking")
              : t("profile.program.notChecked")}
          </p>
        </section>

        {program === "tif" && answer === "yes" && (reports !== "ready" || (d.tif && d.tif.funds.length === 0 && d.tif.balance == null && d.tif.projects.length === 0)) && (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption" data-testid="tif-reports-late">
            {reports === "loading" ? <LoaderCircle aria-hidden className="h-3.5 w-3.5 animate-spin" strokeWidth={STROKE} /> : null}
            {reports === "loading" ? t("profile.program.tif.reportsChecking") : reports === "ready" ? t("profile.program.tif.reportsMissing") : t("profile.program.tif.reportsLate")}
            {reports !== "loading" && onRetry && (
              <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 underline underline-offset-2 touch-target">
                <RotateCw aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{t("profile.parts.retry")}
              </button>
            )}
          </p>
        )}
        {program === "tif" && d.tif && (
          <>
            <dl className="grid grid-cols-2 gap-3" data-testid="tif-figures">
              <Fact label={t("profile.program.tif.runs")} value={d.tif.start != null && d.tif.end != null ? `${d.tif.start}–${d.tif.end}` : "—"}
                note={d.tif.yearsLeft != null ? t("profile.program.tif.yearsLeft", { count: d.tif.yearsLeft }) : undefined} />
              {d.tif.balance != null && (
                <Fact label={t("profile.program.tif.balance")} value={usdShort(d.tif.balance, lng)}
                  note={d.tif.reportYear ? t("profile.program.tif.asOfReport", { year: d.tif.reportYear }) : undefined} />
              )}
            </dl>
            {d.tif.funds.length >= 2 && <FundBars funds={d.tif.funds} />}
            {d.tif.projects.length > 0 && (
              <section className="flex flex-col gap-2">
                <h3 className="text-caption font-semibold uppercase tracking-wide nx-muted">{t("profile.program.tif.projects")}</h3>
                <ul className="flex flex-col divide-y divide-nx-ink/5" data-testid="tif-projects">
                  {d.tif.projects.slice(0, 5).map((p) => (
                    <li key={p.name} className="flex flex-col gap-0.5 py-2 text-caption">
                      <span className="font-semibold">{p.name}</span>
                      <span className="nx-muted">
                        {[p.status,
                          p.publicFunds != null ? t("profile.program.tif.publicFunds", { value: usdShort(p.publicFunds, lng) }) : null,
                          p.privateFunds != null ? t("profile.program.tif.privateFunds", { value: usdShort(p.privateFunds, lng) }) : null,
                        ].filter(Boolean).join(" · ")}
                      </span>
                    </li>
                  ))}
                </ul>
                <a href={TIF_PROJECTS_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 self-start text-caption underline underline-offset-2">
                  {t("profile.program.tif.allProjects")}
                  <SquareArrowOutUpRight aria-hidden className="h-3 w-3" strokeWidth={STROKE} />
                  <span className="sr-only">{t("profile.opensInNewTab")}</span>
                </a>
              </section>
            )}
          </>
        )}

        {program === "nmtc" && answer === "yes" && d.nmtc && (
          <dl className="grid grid-cols-2 gap-3">
            <Fact label={t("profile.program.nmtc.poverty")} value={d.nmtc.povertyRate != null ? `${d.nmtc.povertyRate.toLocaleString(numLocale(lng))}%` : "—"}
              note={tract ? t("profile.program.tract", { tract }) : undefined} />
            <Fact label={t("profile.program.nmtc.distress")} value={d.nmtc.severe ? t("profile.program.nmtc.severe") : t("profile.program.nmtc.notSevere")} />
          </dl>
        )}

        {(program === "oz" || program === "qct") && answer === "yes" && tract && (
          <p className="text-caption nx-muted">{t("profile.program.tract", { tract })}</p>
        )}

        {program === "tif" && d.grants && (
          <section className="flex flex-col gap-1.5" data-testid="area-grants">
            <h3 className="text-caption font-semibold uppercase tracking-wide nx-muted">{t("profile.program.grants.title")}</h3>
            <p className="text-caption">
              {t("profile.program.grants.summary", { count: d.grants.projects, funding: usdShort(d.grants.funding, lng) })}
              {Object.keys(d.grants.byProgram).length > 0 && (
                <> {" · "}{Object.entries(d.grants.byProgram).map(([prog, n]) => t("profile.program.grants.by", { program: t(`profile.program.grants.name.${prog}`, { defaultValue: prog }), count: n })).join(", ")}</>
              )}
            </p>
            <p className="text-caption nx-muted">{t("profile.program.grants.what")}</p>
          </section>
        )}

        <section className="flex flex-col gap-2">
          <h3 className="text-caption font-semibold uppercase tracking-wide nx-muted">{t("profile.program.whoDecides")}</h3>
          <p className="text-caption leading-relaxed">{t(`${k}.who`)}</p>
        </section>

        <section className="flex flex-col gap-2">
          <h3 className="text-caption font-semibold uppercase tracking-wide nx-muted">{t("profile.program.whatItIs")}</h3>
          <p className="text-caption leading-relaxed">{t(`profile.money.define.program.${program}`)}</p>
        </section>

        <p className="text-caption nx-muted">
          {t(`${k}.source`)}{d.period ? ` · ${d.period}` : ""}
        </p>

        {ask && (
          <button
            type="button"
            disabled={!ask.ready}
            onClick={() => ask.open(t("profile.money.ask.program", { program: label, address: ask.address }))}
            className="mt-auto inline-flex items-center gap-1.5 self-start text-caption nx-muted underline underline-offset-2 hover:text-nx-ink disabled:no-underline disabled:opacity-60 touch-target"
            data-testid="program-ask"
          >
            <AskIcon aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
            {ask.ready ? t("term.ask") : t("term.askLater")}
          </button>
        )}
      </div>
    </RightDrawer>
  );
}

function StatusPill({ answer }: { answer: IncentiveAnswer }) {
  const { t } = useTranslation("next");
  if (answer === "yes") return <Pill tone="green" icon={CircleCheck}>{t("profile.program.status.in")}</Pill>;
  if (answer === "no") return <Pill tone="gray" icon={CircleMinus}>{t("profile.program.status.out")}</Pill>;
  if (answer === "checking") return <Pill tone="gray" icon={LoaderCircle}>{t("profile.money.incentives.checking")}</Pill>;
  return <Pill tone="gray" icon={CircleDashed}>{t("profile.build.answer.notChecked")}</Pill>;
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

/** The district's fund balance by report year, on a dollar scale (Sapphire; the latest year in black). */
function FundBars({ funds }: { funds: FundYear[] }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const top = niceCeil(Math.max(...funds.map((f) => f.balance)));
  const last = funds[funds.length - 1];
  return (
    <figure className="flex flex-col gap-2" data-testid="tif-funds">
      <figcaption className="text-caption font-semibold uppercase tracking-wide nx-muted">{t("profile.program.tif.balanceByYear")}</figcaption>
      <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-2">
        <div aria-hidden className="flex h-24 flex-col justify-between text-right text-caption nx-muted tabular-nums">
          {[top, top / 2, 0].map((v) => <span key={v} className="-my-2 leading-4">{usdShort(v, lng)}</span>)}
        </div>
        <div className="relative h-24">
          {[top, top / 2, 0].map((v) => <span key={v} aria-hidden className="absolute inset-x-0 border-t border-nx-ink/10" style={{ bottom: `${(v / top) * 100}%` }} />)}
          <div className="absolute inset-0 flex items-end gap-1.5" role="img"
            aria-label={funds.map((f) => `${f.year}: ${usd(f.balance, lng)}`).join(", ")}>
            {funds.map((f) => (
              <span key={f.year} title={`${f.year}: ${usd(f.balance, lng)}`}
                className={`block min-w-0 flex-1 rounded-t ${f === last ? "bg-nx-lot" : "bg-nx-chart-1"}`}
                style={{ height: `${Math.max(2, (f.balance / top) * 100)}%` }} />
            ))}
          </div>
        </div>
        <span aria-hidden />
        <div aria-hidden className="mt-1 flex gap-1.5 text-caption nx-muted tabular-nums">
          {funds.map((f) => <span key={f.year} className={`min-w-0 flex-1 text-center ${f === last ? "font-semibold text-nx-ink" : ""}`}>{`’${String(f.year).slice(2)}`}</span>)}
        </div>
      </div>
    </figure>
  );
}
