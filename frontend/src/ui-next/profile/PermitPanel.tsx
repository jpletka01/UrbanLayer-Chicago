// A building permit's page in the right panel (Neighborhood, decision Item 102; owner's review: a permit should be
// something you can click into, not a line you can't open). Built to be read like Build's rule pages: what is being
// built in the City's words, where the permit stands on the City's path (applied → issued → inspections → complete),
// its facts, a button that shows it on the map, the City's records, then "Ask the analyst" last. Facts only (rule 11).
import { useTranslation } from "react-i18next";
import { Building2, CircleCheck, MapPin, SquareArrowOutUpRight, TriangleAlert, Wrench } from "lucide-react";
import type { ConstructionProject } from "../../lib/api";
import { RightDrawer } from "../ui/RightDrawer";
import { Pill } from "../ui/Blocks";
import { useAskHandoff } from "../ask/askContext";
import { ICON, STROKE } from "../icons";
import { numLocale } from "./profileModel";
import { usd } from "./moneyModel";
import { permitStage, permitWords } from "./neighborhoodModel";

const H3 = "text-caption font-semibold uppercase tracking-wide nx-muted";
const PERMITS_DATASET = "https://data.cityofchicago.org/Buildings/Building-Permits/ydr8-5enu";
const BUILDING_RECORDS = "https://webapps1.chicago.gov/buildingrecords/home";

/** The City's description, readable: sentence case, its own words. */
function sentenceCase(s: string | null): string | null {
  if (!s) return null;
  const t = s.replace(/\s+/g, " ").trim().toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function PermitPanel({ permit, onClose, onShowOnMap, closing, instant }: {
  permit: ConstructionProject;
  onClose: () => void;
  onShowOnMap?: () => void;
  closing?: boolean;
  instant?: boolean;
}) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const ask = useAskHandoff();
  const date = (iso: string | null | undefined) => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString(numLocale(lng), { month: "short", day: "numeric", year: "numeric" }) : null);
  const { step, stopped } = permitStage(permit);
  const steps = [
    { key: "applied", when: date(permit.applied) },
    { key: "issued", when: date(permit.issued) },
    { key: "inspections", when: null },
    { key: "complete", when: null },
  ];
  const facts: Array<[string, string]> = [
    [t("profile.nb.permit.cost"), permit.cost != null ? usd(permit.cost, lng) : t("profile.nb.permit.notStated")],
    // The City's unit change: blank is "not stated", never "no change" (a 2-flat's permit can leave it blank).
    [t("profile.nb.permit.homes"), permit.units_added ? t(permit.units_added > 0 ? "profile.nb.building.addsUnits" : "profile.nb.building.removesUnits", { count: Math.abs(permit.units_added) })
      : permit.units_added === 0 ? t("profile.nb.permit.noUnitChange") : t("profile.nb.permit.unitsNotStated")],
    [t("profile.nb.permit.distance"), t("profile.money.miles", { mi: permit.distance_mi.toFixed(2) })],
    ...(permit.processing_days != null ? [[t("profile.nb.permit.reviewTime"), t("profile.nb.permit.days", { count: permit.processing_days })] as [string, string]] : []),
    ...(permit.review_type ? [[t("profile.nb.permit.reviewType"), sentenceCase(permit.review_type)!] as [string, string]] : []),
    ...(permit.permit ? [[t("profile.nb.permit.number"), permit.permit] as [string, string]] : []),
  ];
  const KindIcon = permit.kind === "new" ? Building2 : Wrench;
  const AskIcon = ICON.ask;

  return (
    <RightDrawer testId="permit-panel" title={permit.address ?? t("profile.nb.building.noAddress")} onClose={onClose} closing={closing} instant={instant}
      subtitle={(
        <span className="mt-1 inline-flex flex-wrap gap-1.5">
          <Pill tone={permit.kind === "new" ? "green" : "yellow"} icon={KindIcon}>{t(`profile.nb.building.kind.${permit.kind}`)}</Pill>
          {stopped ? <Pill tone="red" icon={TriangleAlert}>{sentenceCase(stopped)}</Pill>
            : step === 3 ? <Pill tone="gray" icon={CircleCheck}>{t("profile.nb.permit.step.complete")}</Pill> : null}
        </span>
      )}>
      <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto pb-20 pr-1 lg:pb-0" data-permit={permit.permit ?? ""}>
        <section className="flex flex-col gap-2">
          <h3 className={H3}>{t("profile.nb.permit.what")}</h3>
          <p className="leading-relaxed" data-testid="permit-description">{permitWords(permit.description, 5000) ?? t("profile.nb.permit.noDescription")}</p>
        </section>

        <section className="flex flex-col gap-3">
          <h3 className={H3}>{t("profile.nb.permit.where")}</h3>
          <ol className="flex flex-col gap-0" aria-label={t("profile.nb.permit.where")} data-testid="permit-stages">
            {steps.map((s, i) => {
              const done = i <= step && !stopped;
              const current = i === step;
              return (
                <li key={s.key} className="flex gap-3" aria-current={current ? "step" : undefined}>
                  <span className="flex flex-col items-center">
                    <span aria-hidden className={`mt-1 h-3 w-3 rounded-full border-2 ${done ? "border-nx-ink bg-nx-ink" : "border-nx-ink/30"} ${current ? "ring-4 ring-nx-ink/10" : ""}`} />
                    {i < steps.length - 1 && <span aria-hidden className={`w-0.5 flex-1 ${i < step && !stopped ? "bg-nx-ink" : "bg-nx-ink/15"}`} />}
                  </span>
                  <span className="flex flex-col pb-4">
                    <span className={current ? "font-semibold" : ""}>{t(`profile.nb.permit.step.${s.key}`)}</span>
                    {s.when && <span className="text-caption nx-muted">{s.when}</span>}
                    {current && s.key === "inspections" && permit.milestone && /OCCUPANCY/i.test(permit.milestone) && (
                      <span className="text-caption nx-muted">{t("profile.nb.permit.occupancy")}</span>
                    )}
                  </span>
                </li>
              );
            })}
          </ol>
        </section>

        <section className="flex flex-col gap-2">
          <h3 className={H3}>{t("profile.nb.permit.facts")}</h3>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-caption">
            {facts.map(([k, v]) => (
              <div key={k} className="flex flex-col gap-0.5"><dt className="nx-muted">{k}</dt><dd className="font-semibold tabular-nums [overflow-wrap:anywhere]">{v}</dd></div>
            ))}
          </dl>
        </section>

        {onShowOnMap && (
          <button type="button" onClick={onShowOnMap} className="inline-flex w-fit items-center gap-1.5 rounded-lg bg-nx-block px-3 py-2 font-semibold hover:bg-nx-ink/5 touch-target" data-testid="permit-show-map">
            <MapPin aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("profile.nb.permit.showOnMap")}
          </button>
        )}

        <section className="flex flex-col gap-2">
          <h3 className={H3}>{t("profile.nb.permit.records")}</h3>
          <a href={BUILDING_RECORDS} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline underline-offset-2">
            {t("profile.nb.permit.buildingRecords")}<SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
          </a>
          <p className="text-caption nx-muted">{t("profile.nb.permit.buildingRecordsHow", { address: permit.address ?? "" })}</p>
          <a href={PERMITS_DATASET} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-caption underline underline-offset-2">
            {t("profile.nb.permit.dataset")}<SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
          </a>
        </section>

        {ask && (
          <button type="button" disabled={!ask.ready} data-testid="permit-ask"
            onClick={() => ask.open(t("profile.nb.ask.permit", { permit: permit.address ?? permit.permit ?? "", address: ask.address }))}
            className="mt-auto inline-flex w-fit items-center gap-1.5 text-caption nx-muted underline underline-offset-2 hover:text-nx-ink disabled:no-underline disabled:opacity-60 touch-target">
            <AskIcon aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{ask.ready ? t("term.ask") : t("term.askLater")}
          </button>
        )}
      </div>
    </RightDrawer>
  );
}
