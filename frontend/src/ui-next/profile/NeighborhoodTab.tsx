// Neighborhood tab (brief "Property Profile", Neighborhood: "What's the area like?"; decision Item 102). The tab
// shape of every Profile tab: the takeaway sentence → a row of stat tiles (walk, transit and bike scores; violent
// crime per resident) → one wide block (construction nearby; the same permits are the map's pins) → the smaller
// blocks (safety, 311, who lives here, schools) → a collapsed details table. On a phone a row of jump links sticks
// under the tab bar (owner's pick from the mockup) and lights the block in view. Race and ethnicity are left out
// (owner); the tract is compared with its community area, never the city (rule 6). Blocks that read a late part
// follow Item 89's skeleton rule. Nothing here is advice or a forecast (rule 11).
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, MapPin, SquareArrowOutUpRight } from "lucide-react";
import type { ScorecardResponse } from "../../lib/api";
import { ConfidenceState } from "../../components/ui/ConfidenceState";
import { humanizeShoutyCase } from "../../lib/format";
import { Block, Pill, StatTile } from "../ui/Blocks";
import { Term } from "../ui/Term";
import { useAskHandoff } from "../ask/askContext";
import { ICON, STROKE } from "../icons";
import { numLocale } from "./profileModel";
import { usd, type LateBlockState } from "./moneyModel";
import { BarsSkeleton, LateSlot } from "./LateSlot";
import {
  areaDemographics, constructionModel, crimeModel, designationTone, neighborhoodSentence, peopleModel, permitWords, schoolsModel, scores,
  sourceState, three11Model, type ConstructionModel, type CrimeModel, type PeopleModel,
} from "./neighborhoodModel";
import type { NextUiSchool } from "../../lib/api";

const SECTIONS = ["around", "building", "safety", "311", "people", "schools"] as const;
type SectionId = (typeof SECTIONS)[number];
const PROJECTS_SHOWN = 6;

export function NeighborhoodTab({
  data,
  late,
  timedOutActivity,
  onRetry,
}: {
  data: ScorecardResponse;
  /** `neighborhood` (tract, transit, demographics) and `activity` (crime, 311, schools, construction). */
  late: { neighborhood: LateBlockState; activity: LateBlockState };
  /** The activity part's sources that passed the deadline. */
  timedOutActivity: string[];
  onRetry: (part: "neighborhood" | "activity") => void;
}) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const ask = useAskHandoff();
  const q = (key: string) => t(`profile.nb.ask.${key}`, { address: ask?.address ?? "" });
  const def = (key: string) => t(`profile.nb.define.${key}`);
  const nf = (n: number, digits = 0) => n.toLocaleString(numLocale(lng), { maximumFractionDigits: digits, minimumFractionDigits: digits });

  const st = (s: "crime" | "area_311" | "schools" | "construction_within") => sourceState(data, late.activity, s, timedOutActivity);
  const crimeSt = st("crime"), s311 = st("area_311"), schoolsSt = st("schools"), buildSt = st("construction_within");
  const sc = scores(data);
  const crime = crimeSt === "ready" ? crimeModel(data) : null;
  const t311 = s311 === "ready" ? three11Model(data) : null;
  const build = buildSt === "ready" ? constructionModel(data) : null;
  const people = peopleModel(data);
  const schools = schoolsSt === "ready" ? schoolsModel(data) : null;
  const area = data.community_area_name ? humanizeShoutyCase(data.community_area_name) : t("profile.nb.theArea");
  const nb = data.context?.neighborhood;

  // Jump links (phones): the block in view lights its chip.
  const [inView, setInView] = useState<SectionId>("around");
  const section = (id: SectionId) => document.getElementById(`nb-${id}`);
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver((entries) => {
      const shown = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (shown[0]) setInView(shown[0].target.getAttribute("data-section") as SectionId);
    }, { rootMargin: "-30% 0px -60% 0px" });
    for (const id of SECTIONS) { const el = section(id); if (el) io.observe(el); }
    return () => io.disconnect();
  }, []);
  useEffect(() => {
    document.querySelector(`[data-testid="nb-jump"] [data-chip="${inView}"]`)?.scrollIntoView?.({ inline: "nearest", block: "nearest" });
  }, [inView]);
  const jump = (id: SectionId) => {
    setInView(id);
    section(id)?.scrollIntoView({ behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  };
  const anchor = (id: SectionId) => ({
    "data-section": id,
    id: `nb-${id}`,
    className: "scroll-mt-[calc(var(--nx-tabbar-h,3rem)+3.5rem)] md:scroll-mt-[calc(var(--nx-tabbar-h,3rem)+1rem)]",
  });

  const scoreTile = (key: "walk" | "transit" | "bike", tone: "a" | "b") => {
    const s = sc?.find((x) => x.key === key);
    return (
      <StatTile
        key={key} testId={`tile-${key}`} tone={tone}
        label={<Term label={t(`profile.nb.score.${key}`)} definition={def(key)} question={q("scores")} />}
        figure={s?.score != null ? String(s.score) : "—"}
        unit={s?.score != null ? t("profile.tiles.of100") : undefined}
        note={s?.score != null ? s.description ?? undefined : t("profile.tiles.walkUnchecked")}
      />
    );
  };

  return (
    <div className="flex flex-col gap-7" data-testid="neighborhood-tab">
      <nav
        aria-label={t("profile.nb.jumpLabel")}
        className="sticky top-[var(--nx-tabbar-h,3rem)] z-20 -mx-4 -mt-3 flex gap-2 overflow-x-auto bg-nx-page px-4 py-2 [scrollbar-width:none] md:hidden [&::-webkit-scrollbar]:hidden"
        data-testid="nb-jump"
      >
        {SECTIONS.map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => jump(id)}
            aria-current={inView === id ? "true" : undefined}
            data-chip={id}
            className={`shrink-0 rounded-full px-3 py-1 text-caption touch-target ${inView === id ? "bg-nx-primary text-nx-primary-fg" : "bg-nx-block"}`}
          >
            {t(`profile.nb.jump.${id}`)}
          </button>
        ))}
      </nav>

      <p className="text-nx-answer" data-testid="nb-sentence">{neighborhoodSentence(data, t, { building: buildSt === "ready", crime: crimeSt === "ready" })}</p>

      <section {...anchor("around")} aria-label={t("profile.nb.jump.around")}>
        <ul className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:gap-7 xl:grid-cols-4" data-testid="nb-tiles">
          {scoreTile("walk", "a")}
          {scoreTile("transit", "b")}
          {scoreTile("bike", "b")}
          <StatTile
            testId="tile-violent" tone="a"
            label={<Term label={t("profile.nb.crime.tile")} definition={def("crime")} question={q("crime")} />}
            checking={crimeSt === "loading"}
            figure={crime?.violentPer1k != null ? nf(crime.violentPer1k, 1) : crime ? nf(crime.violent) : "—"}
            unit={crime?.violentPer1k != null ? t("profile.nb.crime.perThousand") : crime ? t("profile.nb.crime.crimes") : undefined}
            note={crimeSt === "loading" ? t("profile.money.checking", { what: t("profile.nb.crime.what") })
              : crime ? [t("profile.nb.crime.window", { area }), crime.violentChange != null ? changeWords(crime.violentChange, t) : null].filter(Boolean).join(" · ")
              : t("profile.nb.crime.notChecked")}
          />
        </ul>
      </section>

      <section {...anchor("building")}>
        <Block
          title={<Term label={t("profile.nb.building.title")} definition={def("building")} question={q("building")} />}
          icon={ICON.construction}
          labelledBy="nx-building"
          aside={build && build.projects.length > 0 ? (
            <span className="inline-flex items-center gap-1"><MapPin aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{t("profile.nb.building.onMap")}</span>
          ) : undefined}
        >
          <LateSlot state={buildSt} what={t("profile.nb.building.what")} onRetry={() => onRetry("activity")} skeleton={<BarsSkeleton rows={4} />}>
            {build ? <BuildingBody build={build} /> : null}
          </LateSlot>
        </Block>
      </section>

      <div className="grid items-start gap-7 md:grid-cols-2">
        <section {...anchor("safety")}>
          <Block title={<Term label={t("profile.nb.crime.title")} definition={def("crime")} question={q("crime")} />} icon={ICON.safety} labelledBy="nx-safety"
            aside={crime?.currentLabel ?? undefined}>
            <LateSlot state={crimeSt} what={t("profile.nb.crime.what")} onRetry={() => onRetry("activity")} skeleton={<BarsSkeleton rows={2} />}>
              {crime ? <SafetyBody crime={crime} area={area} /> : null}
            </LateSlot>
          </Block>
        </section>

        <section {...anchor("311")}>
          <Block title={<Term label={t("profile.nb.r311.title")} definition={def("r311")} question={q("r311")} />} icon={ICON.requests311} labelledBy="nx-311">
            <LateSlot state={s311} what={t("profile.nb.r311.what")} onRetry={() => onRetry("activity")} skeleton={<BarsSkeleton rows={5} />}>
              {t311 ? (
                t311.top.length === 0 ? <p className="nx-muted">{t("profile.nb.r311.none", { area, days: t311.days })}</p> : (
                  <figure className="flex flex-col gap-3">
                    <ul className="flex flex-col gap-2.5" data-testid="nb-311-bars">
                      {t311.top.map((r) => (
                        <li key={r.type} className="flex flex-col gap-1 text-caption">
                          <span className="flex items-baseline justify-between gap-2"><span>{r.type}</span><span className="tabular-nums">{nf(r.count)}</span></span>
                          <span className="relative block h-2.5 overflow-hidden rounded bg-nx-ink/5" aria-hidden>
                            <span className="absolute inset-y-0 left-0 rounded bg-nx-chart-1" style={{ width: `${(r.count / t311.top[0].count) * 100}%` }} />
                          </span>
                        </li>
                      ))}
                    </ul>
                    <figcaption className="text-caption nx-muted">{t("profile.nb.r311.caption", { total: nf(t311.total), area, days: t311.days })}</figcaption>
                  </figure>
                )
              ) : null}
            </LateSlot>
          </Block>
        </section>

        <section {...anchor("people")}>
          <Block title={<Term label={t("profile.nb.people.title")} definition={def("people")} question={q("people")} />} icon={ICON.people} labelledBy="nx-people"
            aside={people?.period ? t("profile.money.rent.census", { period: people.period }) : undefined}>
            <LateSlot state={late.neighborhood} what={t("profile.nb.people.what")} onRetry={() => onRetry("neighborhood")} skeleton={<BarsSkeleton rows={2} />}>
              {people ? <PeopleBody people={people} area={area} areaPending={late.activity === "loading"} /> : <p className="nx-muted">{t("profile.nb.people.notChecked")}</p>}
            </LateSlot>
          </Block>
        </section>

        <section {...anchor("schools")}>
          <Block title={<Term label={t("profile.nb.schools.title")} definition={def("schools")} question={q("schools")} />} icon={ICON.schools} labelledBy="nx-schools">
            <LateSlot state={schoolsSt} what={t("profile.nb.schools.what")} onRetry={() => onRetry("activity")} skeleton={<BarsSkeleton rows={3} />}>
              {schools ? (
                <div className="flex flex-col gap-4">
                  {schools.schools.map((s) => <SchoolCard key={s.school_id} school={s} />)}
                  {schools.noneAssigned.map((lvl) => (
                    <p key={lvl} className="text-caption nx-muted">{t(`profile.nb.schools.noBoundary.${lvl}`)}</p>
                  ))}
                  <p className="text-caption nx-muted">{t("profile.nb.schools.caption", { boundary: schools.boundaryYear, year: schools.reportYear ?? "—" })}</p>
                </div>
              ) : null}
            </LateSlot>
          </Block>
        </section>
      </div>

      <details className="group rounded-2xl bg-nx-block p-5 sm:p-6" data-testid="nb-details">
        <summary className="flex cursor-pointer list-none items-center gap-2 font-semibold">
          <ChevronDown aria-hidden className="h-4 w-4 transition-transform group-open:rotate-180" strokeWidth={STROKE} />
          {t("profile.nb.details.title")}
        </summary>
        <table className="mt-4 w-full text-caption">
          <tbody>
            {([
              [t("profile.nb.details.rail"), nb?.transit?.nearest_cta_rail ? t("profile.nb.details.at", { name: nb.transit.nearest_cta_rail, mi: nb.transit.cta_rail_distance_mi?.toFixed(2) ?? "—" }) + (nb.transit.cta_lines.length ? ` · ${nb.transit.cta_lines.join(", ")}` : "") : "—"],
              [t("profile.nb.details.metra"), nb?.transit?.nearest_metra ? t("profile.nb.details.at", { name: nb.transit.nearest_metra, mi: nb.transit.metra_distance_mi?.toFixed(2) ?? "—" }) : "—"],
              [t("profile.nb.details.divvy"), nb?.divvy?.nearest_station ? t("profile.nb.details.at", { name: nb.divvy.nearest_station, mi: nb.divvy.distance_mi?.toFixed(2) ?? "—" }) : "—"],
              [t("profile.nb.details.traffic"), nb?.traffic?.road && nb.traffic.daily_vehicles != null ? t("profile.nb.details.trafficValue", { road: humanizeShoutyCase(nb.traffic.road), n: nf(nb.traffic.daily_vehicles) }) : "—"],
              [t("profile.nb.details.ward"), nb?.ward ? t("profile.nb.details.wardValue", { ward: nb.ward.ward, name: nb.ward.alderman ?? "—" }) : "—"],
              [t("profile.nb.details.areaPop"), areaDemographics(data)?.population != null ? nf(areaDemographics(data)!.population!) : "—"],
              [t("profile.nb.details.property"), crime ? `${nf(crime.property)} · ${crime.propertyPer1k != null ? `${nf(crime.propertyPer1k, 1)} ${t("profile.nb.crime.perThousand")}` : "—"}` : "—"],
              [t("profile.nb.details.tract"), people?.tractName ?? "—"],
            ] as Array<[string, string]>).map(([k, v]) => (
              <tr key={k} className="border-b border-nx-ink/5 last:border-0">
                <th scope="row" className="py-2 pr-4 text-left font-normal nx-muted">{k}</th>
                <td className="py-2 tabular-nums">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {build && build.projects.length > PROJECTS_SHOWN && (
          <>
            <h4 className="mt-6 font-semibold">{t("profile.nb.details.allProjects", { count: build.projects.length })}</h4>
            <ProjectList projects={build.projects} />
          </>
        )}
      </details>
    </div>
  );
}

function changeWords(pct: number, t: (k: string, o?: Record<string, unknown>) => string): string {
  if (pct === 0) return t("profile.nb.crime.flat");
  return t(pct < 0 ? "profile.nb.crime.down" : "profile.nb.crime.up", { pct: Math.abs(pct) });
}

// ── Construction nearby ────────────────────────────────────────────────────────────────────────────────

function BuildingBody({ build }: { build: ConstructionModel }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const chips = [
    t("profile.nb.building.rule.radius", { mi: build.radiusMi.toLocaleString(numLocale(lng)) }),
    t("profile.nb.building.rule.months", { count: build.months }),
    t("profile.nb.building.rule.floor", { floor: usd(build.costFloor, lng) }),
  ];
  return (
    <div className="flex flex-col gap-5">
      <ul className="flex flex-wrap gap-2" aria-label={t("profile.nb.building.ruleLabel")} data-testid="nb-building-rule">
        {chips.map((c) => <li key={c}><Pill tone="gray">{c}</Pill></li>)}
      </ul>
      {build.projects.length === 0 ? (
        <p className="nx-muted">{t("profile.nb.building.none")}</p>
      ) : (
        <>
          <p className="text-caption" data-testid="nb-building-counts">
            {[
              t("profile.nb.building.newCount", { count: build.newCount }),
              t("profile.nb.building.renoCount", { count: build.renovationCount }),
              build.unitsAdded > 0 ? t("profile.nb.building.units", { count: build.unitsAdded }) : null,
            ].filter(Boolean).join(" · ")}
            {build.capped ? ` · ${t("profile.nb.building.capped")}` : ""}
          </p>
          <ProjectList projects={build.projects.slice(0, PROJECTS_SHOWN)} />
          {build.projects.length > PROJECTS_SHOWN && (
            <p className="text-caption nx-muted">{t("profile.nb.building.more", { count: build.projects.length - PROJECTS_SHOWN })}</p>
          )}
        </>
      )}
    </div>
  );
}

function ProjectList({ projects }: { projects: ConstructionModel["projects"] }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const date = (iso: string | null) => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString(numLocale(lng), { month: "short", year: "numeric" }) : "—");
  return (
    <ul className="flex flex-col divide-y divide-nx-ink/5" data-testid="nb-projects">
      {projects.map((p, i) => (
        <li key={`${p.permit ?? i}`} className="flex flex-col gap-1 py-2.5 first:pt-0">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Pill tone={p.kind === "new" ? "green" : "gray"}>{t(`profile.nb.building.kind.${p.kind}`)}</Pill>
            <span className="font-semibold">{p.address ?? t("profile.nb.building.noAddress")}</span>
            <span className="text-caption nx-muted">{[date(p.issued), t("profile.money.miles", { mi: p.distance_mi.toFixed(2) })].join(" · ")}</span>
          </span>
          {permitWords(p.description) && <span className="text-caption">{permitWords(p.description)}</span>}
          <span className="text-caption nx-muted tabular-nums">
            {[p.cost != null ? t("profile.nb.building.cost", { cost: usd(p.cost, lng) }) : null,
              p.units_added ? t(p.units_added > 0 ? "profile.nb.building.addsUnits" : "profile.nb.building.removesUnits", { count: Math.abs(p.units_added) }) : null,
              p.permit ? t("profile.nb.building.permit", { n: p.permit }) : null].filter(Boolean).join(" · ")}
          </span>
        </li>
      ))}
    </ul>
  );
}

// ── Safety ───────────────────────────────────────────────────────────────────────────────────────────────

function SafetyBody({ crime, area }: { crime: CrimeModel; area: string }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const nf = (n: number, d = 0) => n.toLocaleString(numLocale(lng), { maximumFractionDigits: d, minimumFractionDigits: d });
  const rows = [
    { key: "violent", now: crime.violent, prior: crime.priorViolent, rate: crime.violentPer1k, change: crime.violentChange },
    { key: "property", now: crime.property, prior: crime.priorProperty, rate: crime.propertyPer1k, change: crime.propertyChange },
  ] as const;
  const max = Math.max(1, ...rows.flatMap((r) => [r.now, r.prior ?? 0]));
  const hasPrior = rows.some((r) => r.prior != null);
  return (
    <figure className="flex flex-col gap-4">
      <ul className="flex flex-col gap-4" data-testid="nb-crime-bars">
        {rows.map((r) => (
          <li key={r.key} className="flex flex-col gap-1.5 text-caption">
            <span className="flex flex-wrap items-baseline justify-between gap-x-2">
              <span className="font-semibold">{t(`profile.nb.crime.${r.key}`)}</span>
              <span className="tabular-nums">
                {r.rate != null ? `${nf(r.rate, 1)} ${t("profile.nb.crime.perThousand")}` : `${nf(r.now)} ${t("profile.nb.crime.crimes")}`}
                {r.change != null ? ` · ${changeWords(r.change, t)}` : ""}
              </span>
            </span>
            <span className="relative block h-3 overflow-hidden rounded bg-nx-ink/5" role="img"
              aria-label={t("profile.nb.crime.barLabel", { kind: t(`profile.nb.crime.${r.key}`), now: nf(r.now), prior: r.prior != null ? nf(r.prior) : "—" })}>
              <span className="absolute inset-y-0 left-0 rounded bg-nx-chart-1" style={{ width: `${(r.now / max) * 100}%` }} />
            </span>
            {r.prior != null && (
              <span aria-hidden className="relative block h-1.5 overflow-hidden rounded bg-nx-ink/5">
                <span className="absolute inset-y-0 left-0 rounded bg-nx-ink/30" style={{ width: `${(r.prior / max) * 100}%` }} />
              </span>
            )}
          </li>
        ))}
      </ul>
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-caption nx-muted">
        <span className="inline-flex items-center gap-1.5"><span aria-hidden className="h-2.5 w-3 rounded-sm bg-nx-chart-1" />{t("profile.nb.crime.legendNow")}</span>
        {hasPrior && <span className="inline-flex items-center gap-1.5"><span aria-hidden className="h-1.5 w-3 rounded-sm bg-nx-ink/30" />{t("profile.nb.crime.legendPrior", { period: crime.priorLabel ?? "" })}</span>}
        <span>{crime.population != null ? t("profile.nb.crime.caption", { area, pop: nf(crime.population) }) : t("profile.nb.crime.captionNoPop", { area })}</span>
      </figcaption>
    </figure>
  );
}

// ── Who lives here ───────────────────────────────────────────────────────────────────────────────────────

function PeopleBody({ people, area, areaPending }: { people: PeopleModel; area: string; areaPending: boolean }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const inc = people.income;
  const max = Math.max(1, inc.tract ?? 0, inc.area ?? 0);
  const bar = (label: string, v: number | null, tone: string, low = false, pending = false) => (
    <li className="flex flex-col gap-1 text-caption">
      <span className="flex items-baseline justify-between gap-2">
        <span>{label}</span>
        <span className="flex items-center gap-1.5 tabular-nums">{v != null ? usd(v, lng) : pending ? <span className="nx-muted">{t("profile.money.checking", { what: label })}</span> : "—"}{low && <ConfidenceState kind="estimate" low />}</span>
      </span>
      <span className="relative block h-3 overflow-hidden rounded bg-nx-ink/5" aria-hidden>
        {v != null && <span className={`absolute inset-y-0 left-0 rounded ${tone}`} style={{ width: `${(v / max) * 100}%` }} />}
      </span>
    </li>
  );
  const fmt = (k: string, v: number | null) => (v == null ? "—" : k === "median_age" ? t("profile.nb.people.years", { n: v.toFixed(0) }) : `${v.toFixed(0)}%`);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <span className="text-caption font-semibold">{t("profile.nb.people.income")}</span>
        <ul className="flex flex-col gap-2.5" data-testid="nb-income-bars">
          {bar(t("profile.nb.people.thisTract"), inc.tract, "bg-nx-chart-1")}
          {bar(area, inc.area, "bg-nx-ink/30", inc.areaLow, areaPending)}
        </ul>
        {inc.tractWithheld && <p className="text-caption nx-muted">{t("profile.nb.people.withheld")}</p>}
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-caption" data-testid="nb-people-facts">
        {people.facts.map((f) => (
          <div key={f.key} className="flex flex-col gap-0.5">
            <dt className="nx-muted">{t(`profile.nb.people.fact.${f.key}`)}</dt>
            <dd className="flex items-center gap-1.5 font-semibold tabular-nums">
              {f.withheld ? <ConfidenceState kind="withheld" low={false} /> : fmt(f.key, f.value)}
              {!f.withheld && f.state?.low && <ConfidenceState kind="estimate" low />}
            </dd>
          </div>
        ))}
      </dl>
      <p className="text-caption nx-muted">{t("profile.nb.people.caption", { area })}</p>
    </div>
  );
}

// ── Schools ──────────────────────────────────────────────────────────────────────────────────────────────

function SchoolCard({ school }: { school: NextUiSchool }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const rc = school.report_card;
  const pct = (v: number | undefined, src?: string) => (v == null ? t("profile.nb.schools.notPublished") : `${v.toFixed(0)}%${src ? ` ${t("profile.nb.schools.hsTest")}` : ""}`);
  const rows: Array<[string, string]> = rc ? [
    [t("profile.nb.schools.reading"), pct(rc.ela_pct, rc.ela_source)],
    [t("profile.nb.schools.math"), pct(rc.math_pct, rc.math_source)],
    ...(school.level === "high" ? [[t("profile.nb.schools.graduation"), pct(rc.graduation_4yr_pct)] as [string, string]] : []),
    [t("profile.nb.schools.enrollment"), rc.enrollment != null ? rc.enrollment.toLocaleString(numLocale(lng)) : "—"],
  ] : [];
  return (
    <article className="flex flex-col gap-2 rounded-xl bg-nx-page p-4" data-testid={`nb-school-${school.level}`}>
      <span className="text-caption nx-muted">{t(`profile.nb.schools.level.${school.level}`)}{school.grades ? ` · ${t("profile.nb.schools.grades", { grades: school.grades })}` : ""}</span>
      <span className="flex flex-wrap items-center gap-2">
        {school.cps_url ? (
          <a href={school.cps_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-semibold underline underline-offset-2">
            {school.name ?? t("profile.nb.schools.unnamed")}<SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
          </a>
        ) : <span className="font-semibold">{school.name ?? t("profile.nb.schools.unnamed")}</span>}
        {rc?.designation && <Pill tone={designationTone(rc.designation)}>{t(`profile.nb.schools.designation.${rc.designation}`)}</Pill>}
      </span>
      {rc ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-caption">
          {rows.map(([k, v]) => (
            <div key={k} className="flex flex-col"><dt className="nx-muted">{k}</dt><dd className="font-semibold tabular-nums">{v}</dd></div>
          ))}
        </dl>
      ) : <p className="text-caption nx-muted">{t("profile.nb.schools.noReportCard")}</p>}
      {school.report_card_url && (
        <a href={school.report_card_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-caption underline underline-offset-2">
          {t("profile.nb.schools.reportCard", { year: rc?.year ?? "" })}<SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
        </a>
      )}
    </article>
  );
}
