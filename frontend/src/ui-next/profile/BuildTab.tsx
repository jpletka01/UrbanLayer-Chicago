// Build tab (brief "Property Profile"; decision Item 76): takeaway sentence → one wide main visual (allowed vs
// built, the deciding limit in black) → two smaller visuals (pending rezonings as a stage tracker, rules as
// yes/no chips) → a collapsed details table. Missing data keeps its slot.
import { useTranslation } from "react-i18next";
import { ChevronDown, ChevronRight, SquareArrowOutUpRight } from "lucide-react";
import { useAskHandoff } from "../ask/askContext";
import type { ScorecardResponse } from "../../lib/api";
import type { ScorecardVerdict } from "../../lib/scorecardVerdict";
import { buildClause } from "../../lib/answerSentence";
import { ConfidenceState } from "../../components/ui/ConfidenceState";
import { Toggletip } from "../../components/ui/Toggletip";
import { formatDay } from "../../lib/format";
import { Block, Pill, ShareBar, type PillTone } from "../ui/Blocks";
import { ICON, STROKE } from "../icons";
import { allowedVsBuilt, numLocale, pendingRezonings, ruleChips, STAGES, type RuleChip } from "./profileModel";

const LIMIT_ICON = { floorArea: ICON.floorArea, units: ICON.units, height: ICON.height } as const;

export function BuildTab({ data, verdict, buildingPending = false }: { data: ScorecardResponse; verdict: ScorecardVerdict; buildingPending?: boolean }) {
  const { t, i18n } = useTranslation("next");
  const { t: tp } = useTranslation("pages");
  const rows = allowedVsBuilt(data, verdict, t, i18n.language, { buildingPending });
  const pending = pendingRezonings(data);
  const rules = ruleChips(data, verdict);
  const zdef = data.zone_definition;
  const deciding = rows.find((r) => r.deciding);

  return (
    <div className="flex flex-col gap-7">
      <p className="text-nx-answer">{buildClause(data, verdict, tp)}.</p>

      <Block
        title={t("profile.build.allowedVsBuilt")}
        icon={ICON.floorArea}
        labelledBy="nx-avb"
        aside={zdef?.zone_class ? t("profile.build.underDistrict", { zone: zdef.zone_class }) : undefined}
      >
        {rows.length === 0 ? (
          <p className="nx-muted">{t("profile.build.noLimits")}</p>
        ) : (
          <ul className="flex flex-col gap-4" data-testid="allowed-vs-built">
            {rows.map((r) => {
              const Icon = LIMIT_ICON[r.key];
              const label = t(`profile.build.limit.${r.key}`);
              return (
                <li key={r.key} className="grid grid-cols-[minmax(0,7.5rem)_minmax(0,1fr)] items-center gap-x-3 gap-y-1 sm:grid-cols-[9rem_minmax(0,1fr)_auto]" data-deciding={r.deciding || undefined}>
                  <span className="flex items-center gap-1.5 text-caption">
                    <Icon aria-hidden className="h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} />
                    <span className={r.deciding ? "font-semibold" : ""}>{label}</span>
                  </span>
                  <ShareBar
                    share={r.share}
                    emphasis={r.deciding}
                    hatched={r.share == null}
                    label={t("profile.build.barLabel", { limit: label, built: r.builtText, allowed: r.allowedText })}
                  />
                  <span className="col-span-2 flex flex-wrap items-center gap-1.5 text-caption tabular-nums sm:col-span-1 sm:justify-end">
                    <span>{r.share != null ? t("profile.build.builtOfAllowed", { built: r.builtText, allowed: r.allowedText }) : t("profile.build.allowedBuiltUnknown", { built: r.builtText, allowed: r.allowedText })}</span>
                    {r.state && <ConfidenceState kind={r.state.kind} low={r.state.low} />}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        <p className="text-caption nx-muted">
          {deciding ? t("profile.build.decidingNote", { limit: t(`profile.build.limit.${deciding.key}`).toLowerCase() }) : t("profile.build.noDeciding")}
          {" "}
          <Toggletip label={t("profile.build.howToRead")}>
            <p>{t("profile.build.howToReadBody")}</p>
          </Toggletip>
        </p>
      </Block>

      <div className="grid gap-7 md:grid-cols-2">
        <Block title={t("profile.build.pending")} icon={ICON.pending} labelledBy="nx-pending"
          aside={pending.checkedAt ? t("profile.build.checked", { date: formatDay(pending.checkedAt) }) : undefined}>
          {pending.state === "unavailable" ? (
            <p className="nx-muted">{t("profile.build.pendingUnavailable")}</p>
          ) : pending.filings.length === 0 ? (
            <p className="nx-muted">{t("profile.build.pendingNone", { radius: pending.radiusMi ?? 0.5 })}</p>
          ) : (
            <ul className="flex flex-col gap-5">
              {pending.state === "stale" && <li><Pill tone="yellow">{t("profile.build.pendingStale")}</Pill></li>}
              {pending.filings.map((f) => (
                <li key={f.record_number} className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Pill tone={f.onThisLot ? "yellow" : "blue"}>{f.onThisLot ? t("profile.build.onThisLot") : t("profile.build.nearby", { distance: (f.distance_mi ?? 0).toFixed(2) })}</Pill>
                    <a href={f.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-w-0 items-center gap-1 text-caption underline underline-offset-2">
                      <span className="truncate">{f.title || f.record_number}</span>
                      <SquareArrowOutUpRight aria-hidden className="h-3 w-3 shrink-0" strokeWidth={STROKE} />
                      <span className="sr-only">{t("profile.opensInNewTab")}</span>
                    </a>
                  </div>
                  <StageTracker stage={f.stage} status={f.sub_status || f.status} />
                </li>
              ))}
            </ul>
          )}
        </Block>

        <Block title={t("profile.build.rules")} icon={ICON.rules} labelledBy="nx-rules">
          <ul className="flex flex-wrap gap-2" data-testid="rule-chips">
            {rules.map((r) => <RuleItem key={r.key} rule={r} />)}
          </ul>
          <p className="text-caption nx-muted">{t("profile.build.rulesNote")}</p>
        </Block>
      </div>

      <details className="group rounded-2xl bg-nx-block p-5 sm:p-6">
        <summary className="flex cursor-pointer list-none items-center gap-2 font-semibold">
          <ChevronDown aria-hidden className="h-4 w-4 transition-transform group-open:rotate-180" strokeWidth={STROKE} />
          {t("profile.build.details")}
        </summary>
        <table className="mt-4 w-full text-caption">
          <tbody>
            {[
              [t("profile.build.row.district"), [zdef?.zone_class, zdef?.name].filter(Boolean).join(" · ") || "—"],
              [t("profile.build.row.section"), zdef?.code_section || "—"],
              [t("profile.build.row.far"), zdef?.far != null ? String(zdef.far) : "—"],
              [t("profile.build.row.height"), zdef?.max_height || "—"],
              [t("profile.build.row.perUnit"), zdef?.min_lot_area_per_unit != null ? t("profile.build.sqft", { value: zdef.min_lot_area_per_unit.toLocaleString(numLocale(i18n.language)) }) : "—"],
              [t("profile.build.row.lot"), data.context?.property?.land_sqft != null ? t("profile.build.sqft", { value: data.context.property.land_sqft.toLocaleString(numLocale(i18n.language)) }) : "—"],
              [t("profile.build.row.unitMath"), data.context?.unit_yield?.arithmetic || "—"],
            ].map(([k, v]) => (
              <tr key={k} className="border-b border-nx-ink/5 last:border-0">
                <th scope="row" className="py-2 pr-4 text-left font-normal nx-muted">{k}</th>
                <td className="py-2">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

function StageTracker({ stage, status }: { stage: (typeof STAGES)[number] | null; status: string }) {
  const { t } = useTranslation("next");
  if (!stage) return <span className="text-caption nx-muted">{t("profile.build.clerkStatus", { status })}</span>;
  const at = STAGES.indexOf(stage);
  return (
    <ol className="grid grid-cols-4 gap-2" aria-label={t("profile.build.stageLabel", { stage: t(`profile.build.stage.${stage}`) })}>
      {STAGES.map((s, i) => (
        <li key={s} className="relative flex min-w-0 flex-col gap-1 text-caption" aria-current={i === at ? "step" : undefined}>
          <span aria-hidden className={`relative z-[1] block h-3.5 w-3.5 rounded-full border-2 ${i < at ? "border-nx-ink bg-nx-ink" : i === at ? "border-nx-ink bg-nx-page shadow-[0_0_0_4px_rgb(var(--nx-ink)/0.1)]" : "border-nx-ink/20 bg-nx-page"}`} />
          {i < STAGES.length - 1 && <span aria-hidden className={`absolute left-3.5 right-[-0.5rem] top-1.5 h-0.5 ${i < at ? "bg-nx-ink" : "bg-nx-ink/10"}`} />}
          <span className={`leading-tight [overflow-wrap:anywhere] ${i === at ? "font-semibold" : i > at ? "nx-muted" : ""}`}>{t(`profile.build.stage.${s}`)}</span>
        </li>
      ))}
    </ol>
  );
}

function RuleItem({ rule }: { rule: RuleChip }) {
  const { t } = useTranslation("next");
  const ask = useAskHandoff();
  const tone: PillTone = rule.answer === "notChecked" ? "gray" : rule.answer === "yes" ? (rule.blocks ? "yellow" : "blue") : "gray";
  // The whole chip opens the rule's page in the right panel, like Money's incentive chips (owner, Item 99); the TIF
  // chip opens the TIF's program page.
  const open = rule.key === "tif" ? (ask?.openProgram ? () => ask.openProgram!("tif") : undefined)
    : ask?.openRule ? () => ask.openRule!(rule.key as Exclude<RuleChip["key"], "tif">) : undefined;
  return (
    <li data-rule={rule.key} data-answer={rule.answer}>
      <button
        type="button"
        onClick={open}
        disabled={!open}
        aria-haspopup="dialog"
        className="group flex items-center gap-1.5 rounded-xl bg-nx-page py-1.5 pl-2.5 pr-1.5 text-left hover:bg-nx-ink/5 disabled:cursor-default touch-target"
      >
        <span className="text-caption">{t(`profile.build.rule.${rule.key}`)}</span>
        <Pill tone={tone}>{t(`profile.build.answer.${rule.answer}`)}</Pill>
        <ChevronRight aria-hidden className="h-3.5 w-3.5 nx-muted transition-transform group-hover:translate-x-0.5" strokeWidth={STROKE} />
      </button>
    </li>
  );
}
