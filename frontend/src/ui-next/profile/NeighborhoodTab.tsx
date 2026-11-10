// Neighborhood tab (brief "Property Profile", Neighborhood: "What's the area like?"; decision Item 102). The takeaway
// sentence → stat tiles (walk, transit and bike scores as rings; violent crime per resident) → construction nearby
// (its pace by quarter, a filterable list whose every permit opens its own page; the same permits are the map's pins)
// → how the area is changing (sale prices by year, rent then and now) → who lives here (Census Reporter's style:
// headline figures, donuts, labeled columns) → safety and 311 beside schools (two columns that pack from the top) → cards for what is around the lot (CTA, Metra, Divvy, traffic, ward, the area).
// On a phone a row of jump links sticks under the tab bar (owner's pick). Race and ethnicity are left out (owner); the
// tract is compared with its community area, never the city (rule 6). Late blocks follow Item 89's skeleton rule.
// Nothing here is advice or a forecast (rule 11).
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  Bike, BookOpen, Building2, Bus, Calculator, Car, GraduationCap, Footprints, Minus, Shield, TrendingDown, TrendingUp, ChevronDown, ChevronRight, Landmark, Mail, MapPin, Phone, SquareArrowOutUpRight, TrainFront, TrainTrack, Users as UsersIcon, Wrench,
} from "lucide-react";
import type { ConstructionProject, NextUiSchool, ScorecardResponse, TractShare } from "../../lib/api";
import { humanizeShoutyCase } from "../../lib/format";
import { Block, Pill, StatTile, type PillTone } from "../ui/Blocks";
import { LowConfidence } from "../ui/LowConfidence";
import { Toggletip } from "../../components/ui/Toggletip";
import { Term } from "../ui/Term";
import { ScoreRing } from "../ui/ScoreRing";
import { ColumnChart } from "../ui/ColumnChart";
import { useAskHandoff } from "../ask/askContext";
import { ICON, STROKE } from "../icons";
import { numLocale } from "./profileModel";
import { niceCeil, usd, type LateBlockState } from "./moneyModel";
import { BarsSkeleton, LateSlot } from "./LateSlot";
import { PIN_COLORS } from "../map/pins";
import { Donut } from "../ui/Donut";
import {
  areaDemographics, constructionModel, crimeModel, designationTone, neighborhoodSentence, peopleModel, permitList,
  permitQuarters, permitWords, schoolsModel, scores, sourceState, three11Model, totalCost, trendModel,
  type ConstructionModel, type CrimeModel, type PeopleModel, type PermitFilter, type PermitSort,
} from "./neighborhoodModel";

const SECTIONS = ["around", "nearby", "building", "changing", "people", "safety", "311", "schools"] as const;
type SectionId = (typeof SECTIONS)[number];
const PROJECTS_SHOWN = 5;
// CTA's own line colors (the line dot on the rail card).
const CTA_LINE: Record<string, string> = {
  Red: "#C60C30", Blue: "#00A1DE", Brown: "#62361B", Green: "#009B3A", Orange: "#F9461C", Pink: "#E27EA6", Purple: "#522398", Yellow: "#F9E300",
};

// The Coastal palette in order (Item 74), and a neutral gray for "everything else".
const SERIES = [1, 2, 3, 4, 5].map((n) => `rgb(var(--nx-cat-${n}))`);
const OTHER = "rgb(var(--nx-cat-6))";

const compactUsd = (n: number, lng: string) =>
  new Intl.NumberFormat(numLocale(lng), { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(n);

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
  const trend = trendModel(data);
  const area = data.community_area_name ? humanizeShoutyCase(data.community_area_name) : t("profile.nb.theArea");

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
  const anchorCls = "scroll-mt-[calc(var(--nx-tabbar-h,3rem)+3.5rem)] md:scroll-mt-[calc(var(--nx-tabbar-h,3rem)+1rem)]";
  const anchor = (id: SectionId) => ({ "data-section": id, id: `nb-${id}`, className: anchorCls });

  const TILE_ICON = { walk: Footprints, transit: Bus, bike: Bike } as const;
  const scoreTile = (key: "walk" | "transit" | "bike", tone: "a" | "b") => {
    const s = sc?.find((x) => x.key === key);
    const label = t(`profile.nb.score.${key}`);
    const Icon = TILE_ICON[key];
    return (
      <StatTile
        key={key} testId={`tile-${key}`} tone={tone}
        icon={<Icon className="h-5 w-5" strokeWidth={STROKE} />}
        label={<Term label={label} definition={def(key)} question={q("scores")} />}
        note={s?.score != null ? s.description ?? t("profile.nb.score.of100", { score: s.score }) : t("profile.tiles.walkUnchecked")}
        visual={s?.score != null ? <ScoreRing value={s.score} size={64} label={t("profile.nb.score.ringLabel", { label, score: s.score })} testId={`ring-${key}`} /> : <span className="text-nx-figure">—</span>}
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
        <div className="nx-cq">
        <ul className="nx-tiles" data-testid="nb-tiles">
          {scoreTile("walk", "a")}
          {scoreTile("transit", "b")}
          {scoreTile("bike", "b")}
          <StatTile
            testId="tile-violent" tone="a"
            icon={<Shield className="h-5 w-5" strokeWidth={STROKE} />}
            label={<Term label={t("profile.nb.crime.tile")} definition={def("crime")} question={q("crime")} />}
            // The figure and its window together on the card's right, like the score rings (owner).
            note={crimeSt === "loading" ? t("profile.money.checking", { what: t("profile.nb.crime.what") }) : !crime ? t("profile.nb.crime.notChecked") : undefined}
            visual={crime ? (
              <span className="flex shrink-0 flex-col items-end text-right" data-testid="nb-violent-figure">
                <span className="flex items-baseline gap-1"><span className="text-nx-figure tabular-nums leading-none">{crime.violentPer1k != null ? nf(crime.violentPer1k, 1) : nf(crime.violent)}</span>
                  <span className="text-caption nx-card-muted">{crime.violentPer1k != null ? t("profile.nb.crime.perThousand") : t("profile.nb.crime.crimes")}</span></span>
                <span className="mt-1 text-caption nx-card-muted">{t("profile.nb.crime.window", { area })}</span>
                {crime.violentChange != null && <span className="mt-1.5"><ChangeBadge pct={crime.violentChange} goodWhen="down" text={t("profile.nb.badge.vsYear", { pct: Math.abs(crime.violentChange) })} testId="nb-violent-badge" /></span>}
              </span>
            ) : crimeSt === "loading" ? <span aria-hidden className="block h-8 w-20 animate-pulse rounded bg-nx-card-ink/10" /> : <span className="text-nx-figure">—</span>}
          />
        </ul>
        </div>
      </section>

      <section data-section="nearby" id="nb-nearby" aria-labelledby="nx-nearby" className={`${anchorCls} flex flex-col gap-4`}>
        <h3 id="nx-nearby" className="text-body font-semibold">{t("profile.nb.near.title")}</h3>
        <LateSlot state={late.neighborhood} what={t("profile.nb.near.what")} onRetry={() => onRetry("neighborhood")} skeleton={<BarsSkeleton rows={2} />}>
          <NearbyCards data={data} area={area} />
        </LateSlot>
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

      {(trend.sales || trend.rent || late.neighborhood === "loading") && (
        <section {...anchor("changing")}>
          <Block title={<Term label={t("profile.nb.trend.title", { area })} definition={def("trend")} question={q("trend")} />} icon={ICON.valueOverTime} labelledBy="nx-changing">
            <LateSlot state={late.neighborhood} what={t("profile.nb.trend.what")} onRetry={() => onRetry("neighborhood")} skeleton={<BarsSkeleton rows={3} />}>
              <TrendBody trend={trend} area={area} />
            </LateSlot>
          </Block>
        </section>
      )}

      {/* Who lives here, wide (owner's reference: Census Reporter's profiles); then two columns that each pack from
          the top (owner's review: no gaps beside a short block): safety and 311 in one, schools in the other. */}
      <section {...anchor("people")}>
        <Block title={<Term label={t("profile.nb.people.title")} definition={def("people")} question={q("people")} />} icon={ICON.people} labelledBy="nx-people"
          aside={people?.period ? t("profile.money.rent.census", { period: people.period }) : undefined}>
          <LateSlot state={late.neighborhood} what={t("profile.nb.people.what")} onRetry={() => onRetry("neighborhood")} skeleton={<BarsSkeleton rows={4} />}>
            {people ? <PeopleBody data={data} people={people} area={area} areaPending={late.activity === "loading"} /> : <p className="nx-muted">{t("profile.nb.people.notChecked")}</p>}
          </LateSlot>
        </Block>
      </section>

      <div className="grid items-start gap-7 lg:grid-cols-2" data-testid="nb-columns">
        <div className="flex min-w-0 flex-col gap-7">
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
                      <div className="flex flex-col gap-3" data-testid="nb-311-bars">
                        <Donut testId="nb-311-donut" title={t("profile.nb.r311.byType")} size={136}
                          center={{ label: t("profile.nb.r311.requests"), value: nf(t311.total) }}
                          segments={[
                            ...t311.top.map((r, i) => ({ key: r.type, label: r.type, pct: (r.count / t311.total) * 100, color: SERIES[i], note: nf(r.count) })),
                            ...(t311.total > t311.top.reduce((a, r) => a + r.count, 0) ? [{
                              key: "other", label: t("profile.nb.r311.other"), color: OTHER,
                              pct: ((t311.total - t311.top.reduce((a, r) => a + r.count, 0)) / t311.total) * 100,
                              note: nf(t311.total - t311.top.reduce((a, r) => a + r.count, 0)),
                            }] : []),
                          ]} />
                        <p className="text-caption nx-muted">{t("profile.nb.r311.caption", { total: nf(t311.total), area, days: t311.days })}</p>
                      </div>
                    )
                ) : null}
              </LateSlot>
            </Block>
          </section>
        </div>
        <div className="flex min-w-0 flex-col gap-7">
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
      </div>

    </div>
  );
}

/** A change as a badge (owner's third review: the insight as a small visual, not a line of tiny text). `goodWhen`:
    which direction is good (crime: down), green and red then; null = neither, Sapphire-blue. */
function ChangeBadge({ pct, text, goodWhen = null, testId }: { pct: number; text: string; goodWhen?: "up" | "down" | null; testId?: string }) {
  const Icon = pct > 0 ? TrendingUp : pct < 0 ? TrendingDown : Minus;
  const tone: PillTone = goodWhen == null || pct === 0 ? "blue" : (pct < 0) === (goodWhen === "down") ? "green" : "red";
  return <span data-testid={testId}><Pill tone={tone} icon={Icon}>{text}</Pill></span>;
}

/** "1.5× West Town": a figure against its community area's. */
function RatioBadge({ v, ref_, area }: { v: number; ref_: number; area: string }) {
  const { t, i18n } = useTranslation("next");
  const r = v / ref_;
  const same = Math.abs(r - 1) < 0.05;
  return (
    <span data-testid="nb-ratio-badge">
      <Pill tone="purple" icon={same ? Minus : r > 1 ? TrendingUp : TrendingDown}>
        {same ? t("profile.nb.badge.same", { area }) : t("profile.nb.badge.times", { r: r.toLocaleString(numLocale(i18n.language), { maximumFractionDigits: 1, minimumFractionDigits: 1 }), area })}
      </Pill>
    </span>
  );
}

/** A permit's kind as the map draws it: the pin's color and icon (owner: the two kinds must read apart). */
function KindBadge({ kind, size = 28 }: { kind: "new" | "renovation"; size?: number }) {
  const Icon = kind === "new" ? Building2 : Wrench;
  return (
    <span aria-hidden className="grid shrink-0 place-items-center rounded-full text-[#1C1C1C]" style={{ width: size, height: size, background: kind === "new" ? PIN_COLORS.build : PIN_COLORS.reno }}>
      <Icon className="h-[55%] w-[55%]" strokeWidth={1.75} />
    </span>
  );
}

// ── Construction nearby ────────────────────────────────────────────────────────────────────────────────

/** How a builder reads it: how much is being built around the lot and how fast (the counts and the chart), what kind
    and how big (the filter and sort), and each project in detail (a row opens the permit's own page). */
function BuildingBody({ build }: { build: ConstructionModel }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const ask = useAskHandoff();
  const [filter, setFilter] = useState<PermitFilter>("all");
  const [sort, setSort] = useState<PermitSort>("newest");
  const [all, setAll] = useState(false);
  const listRef = useRef<HTMLUListElement | null>(null);
  const toggleAll = () => {
    setAll((a) => !a);
    listRef.current?.scrollTo?.({ top: 0 });
    if (all) listRef.current?.scrollIntoView?.({ block: "nearest" });
  };
  const chips = [
    t("profile.nb.building.rule.radius", { mi: build.radiusMi.toLocaleString(numLocale(lng)) }),
    t("profile.nb.building.rule.months", { count: build.months }),
    t("profile.nb.building.rule.floor", { floor: usd(build.costFloor, lng) }),
  ];
  if (build.projects.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <ul className="flex flex-wrap gap-2" aria-label={t("profile.nb.building.ruleLabel")}>{chips.map((c) => <li key={c}><Pill tone="gray">{c}</Pill></li>)}</ul>
        <p className="nx-muted">{t("profile.nb.building.none")}</p>
      </div>
    );
  }
  const quarters = permitQuarters(build.projects, build.months);
  const top = Math.max(1, niceCeil(Math.max(...quarters.map((x) => x.newCount + x.renoCount))));
  const list = permitList(build.projects, filter, sort);
  const shown = all ? list : list.slice(0, PROJECTS_SHOWN);
  const stat = (figure: string, label: string, kind?: "new" | "renovation") => (
    <div className="flex items-center gap-3 rounded-xl bg-nx-page p-3">
      {kind ? <KindBadge kind={kind} size={32} /> : null}
      <span className="flex flex-col"><span className="text-nx-figure tabular-nums leading-tight">{figure}</span><span className="text-caption nx-muted">{label}</span></span>
    </div>
  );
  return (
    <div className="flex flex-col gap-5">
      <ul className="flex flex-wrap gap-2" aria-label={t("profile.nb.building.ruleLabel")} data-testid="nb-building-rule">
        {chips.map((c) => <li key={c}><Pill tone="gray">{c}</Pill></li>)}
        {build.capped && <li><Pill tone="yellow">{t("profile.nb.building.capped")}</Pill></li>}
      </ul>

      <div className="nx-cq"><div className="nx-split">
        <div className="flex min-w-0 flex-col gap-5">
      <div className="grid grid-cols-2 gap-3" data-testid="nb-building-counts">
        {stat(String(build.newCount), t("profile.nb.building.statNew", { count: build.newCount }), "new")}
        {stat(String(build.renovationCount), t("profile.nb.building.statReno", { count: build.renovationCount }), "renovation")}
        {stat(build.unitsAdded.toLocaleString(numLocale(lng)), t("profile.nb.building.statHomes", { count: build.unitsAdded }))}
        {stat(compactUsd(totalCost(build.projects), lng), t("profile.nb.building.statCost"))}
      </div>

      <figure className="flex flex-col gap-2">
        <figcaption className="flex flex-wrap items-center justify-between gap-2 text-caption">
          <span className="font-semibold">{t("profile.nb.building.pace")}</span>
          <span className="flex gap-3 nx-muted">
            <span className="inline-flex items-center gap-1.5"><span aria-hidden className="h-2.5 w-2.5 rounded-sm" style={{ background: PIN_COLORS.build }} />{t("profile.nb.building.kind.new")}</span>
            <span className="inline-flex items-center gap-1.5"><span aria-hidden className="h-2.5 w-2.5 rounded-sm" style={{ background: PIN_COLORS.reno }} />{t("profile.nb.building.kind.renovation")}</span>
          </span>
        </figcaption>
        <ColumnChart
          testId="nb-permit-quarters"
          ariaLabel={t("profile.nb.building.pace")}
          top={top}
          scale={[String(top), String(top / 2), "0"]}
          heightClass="h-28"
          columns={quarters.map((x) => ({
            key: x.key, tick: x.tick, label: x.label, value: x.newCount + x.renoCount,
            valueText: t("profile.nb.building.quarterValue", { n: x.newCount, r: x.renoCount }),
            segments: [{ value: x.newCount, className: "bg-[#FE9179]" }, { value: x.renoCount, className: "bg-[#B89D47]" }],
          }))}
        />
      </figure>

        </div>
        <div className="flex min-w-0 flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="radiogroup" aria-label={t("profile.nb.building.filterLabel")} className="flex overflow-hidden rounded-lg border border-nx-ink/15 text-caption" data-testid="nb-building-filter">
          {(["all", "new", "renovation"] as const).map((f) => {
            const n = f === "all" ? build.projects.length : f === "new" ? build.newCount : build.renovationCount;
            return (
              <button key={f} type="button" role="radio" aria-checked={filter === f} onClick={() => { setFilter(f); setAll(false); }}
                className={`px-3 py-1.5 touch-target ${filter === f ? "bg-nx-ink text-nx-on-ink" : "hover:bg-nx-ink/5"}`}>
                {t(`profile.nb.building.filter.${f}`, { count: n })}
              </button>
            );
          })}
        </div>
        {list.length > PROJECTS_SHOWN && (
          <button type="button" onClick={toggleAll} aria-expanded={all}
            className="inline-flex items-center gap-1 text-caption underline underline-offset-2 touch-target" data-testid="nb-projects-toggle">
            {all ? t("profile.nb.building.fewer") : t("profile.nb.building.showAll", { count: list.length })}
          </button>
        )}
        <label className="flex items-center gap-2 text-caption">
          <span className="nx-muted">{t("profile.nb.building.sortLabel")}</span>
          <select value={sort} onChange={(e) => setSort(e.target.value as PermitSort)} className="appearance-none rounded-lg border border-nx-ink/15 bg-nx-page px-2.5 py-1.5 touch-field" data-testid="nb-building-sort">
            {(["newest", "closest", "largest"] as const).map((s) => <option key={s} value={s}>{t(`profile.nb.building.sort.${s}`)}</option>)}
          </select>
        </label>
      </div>

      {/* Expanded, the list scrolls inside its own height, so "Show fewer" (above and below) stays near (owner). */}
      <ul ref={listRef} className={`flex flex-col gap-2 ${all ? "max-h-[34rem] overflow-y-auto overscroll-contain pr-1" : ""}`} data-testid="nb-projects">
        {shown.map((p, i) => <ProjectRow key={`${p.permit ?? i}`} p={p} onOpen={ask?.openPermit ? () => ask.openPermit!(p) : undefined} />)}
      </ul>
      {list.length > PROJECTS_SHOWN && (
        <button type="button" onClick={toggleAll} aria-expanded={all}
          className="inline-flex w-fit items-center gap-1.5 rounded-lg bg-nx-page px-3 py-2 text-caption font-semibold hover:bg-nx-ink/5 touch-target" data-testid="nb-projects-more">
          <ChevronDown aria-hidden className={`h-4 w-4 transition-transform ${all ? "rotate-180" : ""}`} strokeWidth={STROKE} />
          {all ? t("profile.nb.building.fewer") : t("profile.nb.building.showAll", { count: list.length })}
        </button>
      )}
        </div>
      </div></div>
    </div>
  );
}

function ProjectRow({ p, onOpen }: { p: ConstructionProject; onOpen?: () => void }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const date = p.issued ? new Date(`${p.issued}T12:00:00`).toLocaleDateString(numLocale(lng), { month: "short", year: "numeric" }) : null;
  const words = permitWords(p.description, 110);
  const body = (
    <>
      <KindBadge kind={p.kind} />
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex flex-wrap items-baseline gap-x-2">
          <span className="font-semibold">{p.address ?? t("profile.nb.building.noAddress")}</span>
          <span className="text-caption nx-muted">{t(`profile.nb.building.kind.${p.kind}`)}</span>
        </span>
        {words && <span className="text-caption line-clamp-1">{words}</span>}
        <span className="flex flex-wrap gap-1.5">
          {date && <Pill tone="gray">{date}</Pill>}
          <Pill tone="gray">{t("profile.money.miles", { mi: p.distance_mi.toFixed(2) })}</Pill>
          {p.cost != null && <Pill tone="gray">{compactUsd(p.cost, lng)}</Pill>}
          {p.units_added ? <Pill tone={p.units_added > 0 ? "green" : "gray"}>{t(p.units_added > 0 ? "profile.nb.building.addsUnits" : "profile.nb.building.removesUnits", { count: Math.abs(p.units_added) })}</Pill> : null}
        </span>
      </span>
      {onOpen && <ChevronRight aria-hidden className="h-4 w-4 shrink-0 self-center nx-muted transition-transform group-hover:translate-x-0.5" strokeWidth={STROKE} />}
    </>
  );
  const cls = "group flex w-full items-start gap-3 rounded-xl bg-nx-page p-3 text-left";
  return (
    <li data-kind={p.kind}>
      {onOpen ? (
        <button type="button" onClick={onOpen} aria-haspopup="dialog" className={`${cls} hover:bg-nx-ink/5`}>{body}</button>
      ) : <div className={cls}>{body}</div>}
    </li>
  );
}

// ── How the area is changing ─────────────────────────────────────────────────────────────────────────────

function TrendBody({ trend, area }: { trend: ReturnType<typeof trendModel>; area: string }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const [group, setGroup] = useState(trend.sales?.groups[0] ?? null);
  if (!trend.sales && !trend.rent) return <p className="nx-muted">{t("profile.nb.trend.none", { area })}</p>;
  const years = trend.sales && group ? (trend.sales.byGroup[group] ?? []).filter((y) => y.median != null) : [];
  const top = years.length ? niceCeil(Math.max(...years.map((y) => y.median!))) : 1;
  const first = years[0], last = years[years.length - 1];
  const salesChange = first && last && first !== last ? Math.round(((last.median! - first.median!) / first.median!) * 100) : null;
  const r = trend.rent;
  const rentMax = r ? Math.max(r.earlier.median, r.later.median) : 1;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {trend.sales && group && (
        <figure className="flex flex-col gap-3" data-testid="nb-sales-trend">
          <figcaption className="flex flex-col gap-2">
            <span className="text-caption font-semibold">{t("profile.nb.trend.sales")}</span>
            {trend.sales.groups.length > 1 && (
              <span role="radiogroup" aria-label={t("profile.nb.trend.groupLabel")} className="flex w-fit overflow-hidden rounded-lg border border-nx-ink/15 text-caption">
                {trend.sales.groups.map((g) => (
                  <button key={g} type="button" role="radio" aria-checked={group === g} onClick={() => setGroup(g)}
                    className={`px-2.5 py-1 touch-target ${group === g ? "bg-nx-ink text-nx-on-ink" : "hover:bg-nx-ink/5"}`}>{t(`profile.nb.trend.group.${g}`)}</button>
                ))}
              </span>
            )}
          </figcaption>
          <ColumnChart
            ariaLabel={t("profile.nb.trend.sales")}
            top={top}
            scale={[compactUsd(top, lng), compactUsd(top / 2, lng), compactUsd(0, lng)]}
            columns={years.map((y, i) => ({ key: y.year, tick: `’${y.year.slice(2)}`, label: y.year, value: y.median!, valueText: `${compactUsd(y.median!, lng)} · ${t("profile.nb.trend.salesN", { count: y.n })}`, highlight: i === years.length - 1 }))}
          />
          {salesChange != null && <span className="flex"><ChangeBadge testId="nb-sales-badge" pct={salesChange} text={t("profile.nb.badge.since", { pct: Math.abs(salesChange), from: first.year, to: last.year })} /></span>}
        </figure>
      )}
      {r && (
        <figure className="flex flex-col gap-3" data-testid="nb-rent-trend">
          <figcaption className="text-caption font-semibold">{t("profile.nb.trend.rent")}</figcaption>
          <ul className="flex flex-col gap-3">
            {[r.earlier, r.later].map((p, i) => (
              <li key={p.period} className="flex flex-col gap-1 text-caption">
                <span className="flex items-baseline justify-between gap-2"><span>{p.period}</span><span className="font-semibold tabular-nums">{t("profile.money.perMonth", { value: usd(p.median, lng) })}</span></span>
                <span aria-hidden className="relative block h-3 overflow-hidden rounded bg-nx-ink/5">
                  <span className={`absolute inset-y-0 left-0 rounded ${i === 1 ? "bg-nx-chart-1" : "bg-nx-ink/30"}`} style={{ width: `${(p.median / rentMax) * 100}%` }} />
                </span>
              </li>
            ))}
          </ul>
          <span className="flex flex-wrap items-center gap-2">
            <ChangeBadge testId="nb-rent-badge" pct={r.change} text={t("profile.nb.badge.rent", { pct: Math.abs(Math.round(r.change)), real: Math.round(r.real) })} />
            {r.significant === false && <span className="text-caption nx-muted">{t("profile.nb.trend.notSignificant")}</span>}
          </span>
          {r.households && (
            <div className="flex items-center gap-3 rounded-xl bg-nx-page p-3" data-testid="nb-households">
              <UsersIcon aria-hidden className="h-5 w-5 shrink-0" strokeWidth={STROKE} />
              <span className="flex flex-wrap items-center gap-2 text-caption">{t("profile.nb.trend.households", { from: r.households.earlier.toLocaleString(numLocale(lng)), to: r.households.later.toLocaleString(numLocale(lng)) })}
                <ChangeBadge pct={r.households.change} text={`${Math.abs(r.households.change)}%`} /></span>
            </div>
          )}
        </figure>
      )}
      <p className="text-caption nx-muted lg:col-span-2">{t("profile.nb.trend.caption", { area })}</p>
    </div>
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
            <span className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
              <span className="flex items-baseline gap-2"><span className="font-semibold">{t(`profile.nb.crime.${r.key}`)}</span>
              <span className="tabular-nums">
                {r.rate != null ? `${nf(r.rate, 1)} ${t("profile.nb.crime.perThousand")}` : `${nf(r.now)} ${t("profile.nb.crime.crimes")}`}
              </span></span>
              {r.change != null && <ChangeBadge pct={r.change} goodWhen="down" text={t("profile.nb.badge.vsYear", { pct: Math.abs(r.change) })} />}
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

// ── Who lives here (owner's second review: the data from the Census Reporter reference, in our own style) ─────
// Headline figures as small cards, then one card per chart so two charts never read as one: Money's hover column
// chart for breakdowns that run in order, bars for the rest, donuts for shares of a whole. A chart with any share
// whose margin of error is at least 10% of it says "Low confidence" once, in its header, explained under the section.
// The comparison is the community area where the City publishes the same figure (rule 6).

const DONUT_SERIES = [...SERIES, OTHER];

function FigureCard({ value, label, compare, badge, testId }: { value: string; label: string; compare?: string | null; badge?: ReactNode; testId?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-xl bg-nx-page p-4" data-testid={testId}>
      <span className="text-nx-figure tabular-nums leading-tight">{value}</span>
      <span className="text-caption">{label}</span>
      {badge && <span className="mt-1 flex">{badge}</span>}
      {compare && <span className="text-caption nx-muted">{compare}</span>}
    </div>
  );
}

function ChartCard({ title, low, children, testId }: { title: string; low?: boolean; children: ReactNode; testId?: string }) {
  return (
    <figure className="flex min-w-0 flex-col gap-3 rounded-xl bg-nx-page p-4" data-testid={testId}>
      <figcaption className="flex flex-wrap items-center justify-between gap-2 text-caption font-semibold">
        {title}
        {low && <LowConfidence />}
      </figcaption>
      {children}
    </figure>
  );
}

/** Rows of bars, the share at the end (Money's rent bars). */
function ShareBars({ rows }: { rows: Array<{ key: string; label: string; pct: number }> }) {
  const max = Math.max(1, ...rows.map((r) => r.pct));
  return (
    <ul className="flex flex-col gap-2">
      {rows.map((r) => (
        <li key={r.key} className="flex flex-col gap-1 text-caption">
          <span className="flex items-baseline justify-between gap-2"><span className="nx-muted">{r.label}</span><span className="tabular-nums">{Math.round(r.pct)}%</span></span>
          <span aria-hidden className="relative block h-2.5 overflow-hidden rounded bg-nx-ink/5">
            <span className="absolute inset-y-0 left-0 rounded bg-nx-chart-1" style={{ width: `${(r.pct / max) * 100}%` }} />
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Shares in order as Money's column chart: hover or tap a column for its value. */
function ShareColumns({ rows, title }: { rows: Array<{ key: string; label: string; tick: string; pct: number }>; title: string }) {
  const { t } = useTranslation("next");
  const top = niceCeil(Math.max(1, ...rows.map((r) => r.pct)));
  return (
    <div className="flex flex-col gap-1.5">
      <ColumnChart ariaLabel={title} top={top} heightClass="h-28" scale={[`${top}%`, `${top / 2}%`, "0%"]}
        columns={rows.map((r) => ({ key: r.key, tick: r.tick, label: r.label, value: r.pct, valueText: `${Math.round(r.pct)}%` }))} />
      <span className="text-caption nx-muted">{t("profile.nb.people.hoverHint")}</span>
    </div>
  );
}

function SubSection({ title, scope, children }: { title: string; scope?: string | null; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3 border-t border-nx-ink/10 pt-5 first:border-0 first:pt-0">
      {/* Each section names the area its figures describe (owner: tract, neighborhood or city?). */}
      <h4 className="flex flex-wrap items-center gap-x-3 gap-y-1 font-semibold">
        {title}
        {scope && <span className="inline-flex items-center gap-1 text-caption font-normal nx-muted" data-testid="nb-scope"><MapPin aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{scope}</span>}
      </h4>
      {children}
    </section>
  );
}

function PeopleBody({ data, people, area, areaPending }: { data: ScorecardResponse; people: PeopleModel; area: string; areaPending: boolean }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const ct = data.context?.neighborhood?.census_tract;
  const x = data.next_ui?.tract;
  const h = x?.tract;
  const nf = (n: number, d = 0) => n.toLocaleString(numLocale(lng), { maximumFractionDigits: d, minimumFractionDigits: d });
  const L = (group: string, key: string) => t(`profile.nb.people.k.${group}.${key}`, { defaultValue: periodLabel(key, lng) });
  const rows = (group: string, list: TractShare[] | null | undefined) => (list ?? []).map((s) => ({ key: s.key, label: L(group, s.key), tick: t(`profile.nb.people.tick.${group}.${s.key}`, { defaultValue: shortPeriod(s.key) }), pct: s.pct }));
  const low = (list: TractShare[] | null | undefined) => (list ?? []).some((s) => s.low);
  const dist = (key: "age_distribution" | "education_distribution" | "transportation_distribution") =>
    (ct?.[key] ?? []).map((b) => ({ key: b.label, label: t(`profile.nb.people.bucket.${b.label}`, { defaultValue: b.label }), tick: t(`profile.nb.people.tick.age.${b.label}`, { defaultValue: b.label }), pct: b.value }));
  const donut = (title: string, list: Array<{ key: string; label: string; pct: number }>, opts: { lead?: string; low?: boolean; testId?: string } = {}) => (
    <ChartCard title={title} low={opts.low} testId={opts.testId}>
      <Donut title={title} showTitle={false} size={112} lead={opts.lead ?? [...list].sort((a, b) => b.pct - a.pct)[0]?.key}
        segments={list.map((s, i) => ({ key: s.key, label: s.label, pct: s.pct, color: DONUT_SERIES[i % DONUT_SERIES.length] }))} />
    </ChartCard>
  );
  const inc = people.income;
  const tractNo = (people.tractName ?? "").match(/Census Tract ([\d.]+)/i)?.[1];
  const scope = tractNo ? t("profile.nb.people.scope", { tract: tractNo }) : t("profile.nb.people.scopeNoNumber");
  const fact = (k: string) => people.facts.find((f) => f.key === k);
  const poverty = fact("poverty_rate"), bach = fact("bachelors_or_higher_pct");
  const pctText = (f?: { value: number | null; withheld: boolean }) => (f?.withheld ? t("profile.nb.people.withheldShort") : f?.value != null ? `${nf(f.value, 1)}%` : "—");

  return (
    <div className="flex flex-col gap-6">
      <SubSection title={t("profile.nb.people.sec.income")} scope={scope}>
        <div className="nx-cq"><div className="nx-masonry">
          <FigureCard testId="nb-income-headline" value={inc.tract != null ? usd(inc.tract, lng) : inc.tractWithheld ? t("profile.nb.people.withheldShort") : "—"} label={t("profile.nb.people.medianIncome")}
            badge={inc.tract != null && inc.area != null ? <RatioBadge v={inc.tract} ref_={inc.area} area={area} /> : undefined}
            compare={areaPending && inc.area == null ? t("profile.money.checking", { what: area }) : inc.area != null ? t("profile.nb.people.areaIs", { area, value: usd(inc.area, lng) }) : null} />
          {h?.per_capita_income != null && <FigureCard value={usd(h.per_capita_income, lng)} label={t("profile.nb.people.perCapita")} />}
          {poverty && <FigureCard value={pctText(poverty)} label={t("profile.nb.people.fact.poverty_rate")} />}
          {x?.income && <ChartCard title={t("profile.nb.people.chart.income")} low={low(x.income)} testId="nb-income-cols"><ShareColumns title={t("profile.nb.people.chart.income")} rows={rows("income", x.income)} /></ChartCard>}
        </div></div>
      </SubSection>

      {h && (
        <SubSection title={t("profile.nb.people.sec.housing")} scope={scope}>
          <div className="nx-cq"><div className="nx-masonry">
            {h.housing_units != null && <FigureCard value={nf(h.housing_units)} label={t("profile.nb.people.housingUnits")} />}
            {h.median_home_value != null && <FigureCard value={usd(h.median_home_value, lng)} label={t("profile.nb.people.homeValue")} />}
            {x?.occupancy && donut(t("profile.nb.people.chart.occupancy"), rows("occupancy", x.occupancy), { lead: "occupied", low: low(x.occupancy), testId: "nb-donut-occupancy" })}
            {x?.tenure && donut(t("profile.nb.people.chart.tenure"), rows("tenure", x.tenure), { low: low(x.tenure), testId: "nb-donut-tenure" })}
            {x?.structure && <ChartCard title={t("profile.nb.people.chart.structure")} low={low(x.structure)} testId="nb-structure-cols"><ShareBars rows={rows("structure", x.structure)} /></ChartCard>}
            {x?.moved_in && <ChartCard title={t("profile.nb.people.chart.movedIn")} low={low(x.moved_in)}><ShareColumns title={t("profile.nb.people.chart.movedIn")} rows={rows("moved_in", x.moved_in)} /></ChartCard>}
            {x?.home_value && <ChartCard title={t("profile.nb.people.chart.homeValue")} low={low(x.home_value)}><ShareBars rows={rows("home_value", x.home_value)} /></ChartCard>}
          </div></div>
        </SubSection>
      )}

      {h && (h.households != null || x?.household_type) && (
        <SubSection title={t("profile.nb.people.sec.households")} scope={scope}>
          <div className="nx-cq"><div className="nx-masonry">
            {h.households != null && <FigureCard value={nf(h.households)} label={t("profile.nb.people.households")} />}
            {h.persons_per_household != null && <FigureCard value={nf(h.persons_per_household, 1)} label={t("profile.nb.people.perHousehold")} />}
            {x?.household_type && donut(t("profile.nb.people.chart.householdType"), rows("household_type", x.household_type), { low: low(x.household_type), testId: "nb-donut-households" })}
          </div></div>
        </SubSection>
      )}

      <SubSection title={t("profile.nb.people.sec.work")} scope={scope}>
        <div className="nx-cq"><div className="nx-masonry">
          {h?.travel_minutes != null && <FigureCard value={t("profile.nb.people.minutes", { n: nf(h.travel_minutes, 1) })} label={t("profile.nb.people.travel")} />}
          {dist("transportation_distribution").length > 0 && <ChartCard title={t("profile.nb.people.dist.transportation_distribution")} testId="nb-commute-cols"><ShareBars rows={dist("transportation_distribution")} /></ChartCard>}
          {x?.travel_time && <ChartCard title={t("profile.nb.people.chart.travelTime")} low={low(x.travel_time)}><ShareColumns title={t("profile.nb.people.chart.travelTime")} rows={rows("travel_time", x.travel_time)} /></ChartCard>}
        </div></div>
      </SubSection>

      <SubSection title={t("profile.nb.people.sec.people")} scope={scope}>
        <div className="nx-cq"><div className="nx-masonry">
          {h?.median_age != null && <FigureCard value={nf(h.median_age, 1)} label={t("profile.nb.people.fact.median_age")} />}
          {bach && <FigureCard value={pctText(bach)} label={t("profile.nb.people.fact.bachelors_or_higher_pct")} />}
          {h?.moved_pct != null && <FigureCard value={`${nf(h.moved_pct, 1)}%`} label={t("profile.nb.people.moved")} />}
          {dist("age_distribution").length > 0 && <ChartCard title={t("profile.nb.people.dist.age_distribution")}><ShareColumns title={t("profile.nb.people.dist.age_distribution")} rows={dist("age_distribution")} /></ChartCard>}
          {dist("education_distribution").length > 0 && donut(t("profile.nb.people.dist.education_distribution"), dist("education_distribution"), { testId: "nb-donut-education" })}
          {x?.mobility && donut(t("profile.nb.people.chart.mobility"), rows("mobility", x.mobility), { lead: "same_house", low: low(x.mobility), testId: "nb-donut-mobility" })}
        </div></div>
      </SubSection>

      <p className="text-caption nx-muted">{t("profile.nb.people.caption", { area })}</p>
    </div>
  );
}

/** The Census's own period names ("2020 to 2022", "2023 or later") in the page's language. */
function periodLabel(key: string, lng: string): string {
  if (!lng.startsWith("es")) return key;
  return key.replace(" to ", " a ").replace(" or later", " o después").replace(" or earlier", " o antes");
}

/** A short column tick for a Census period ("2020 to 2022" → "’20–22", "2023 or later" → "’23+"). */
function shortPeriod(key: string): string {
  const m = key.match(/^(\d{4}) to (\d{4})$/);
  if (m) return `’${m[1].slice(2)}–${m[2].slice(2)}`;
  const later = key.match(/^(\d{4}) or later$/);
  if (later) return `’${later[1].slice(2)}+`;
  const earlier = key.match(/^(\d{4}) or earlier$/);
  if (earlier) return `<’${String(Number(earlier[1]) + 1).slice(2)}`;
  return key;
}

// ── Schools ─────────────────────────────────────────────────────────────────────────────────────────────
// The state's rating is the highlight (owner's third review). A+ grades and 1–10 scores are private companies'
// ratings, which the owner ruled out; ISBE's summative designation is the state's own, lowest to highest here.
const DESIGNATIONS = ["Intensive", "Comprehensive", "Targeted", "Commendable", "Exemplary"] as const;
// CPS's 5Essentials culture-and-climate levels, lowest to highest.
const CULTURE = ["not yet organized", "partially organized", "moderately organized", "organized", "well organized"];

/** A rating as five steps with this school's lit and named (the scale reads lowest to highest, left to right). */
function RatingScale({ title, definition, steps, at, tone, testId }: { title: string; definition: string; steps: string[]; at: number; tone: PillTone; testId?: string }) {
  const fill: Record<PillTone, string> = { green: "bg-nx-pill-green", blue: "bg-nx-pill-blue", yellow: "bg-nx-pill-yellow", gray: "bg-nx-ink", red: "bg-nx-pill-red", purple: "bg-nx-pill-purple" };
  return (
    <div className="flex flex-col gap-1.5" data-testid={testId}>
      <span className="flex items-center justify-between gap-2 text-caption">
        <span className="inline-flex items-center gap-1 nx-muted">{title}<Toggletip kind="info" label={title}>{definition}</Toggletip></span>
        <span className="font-semibold">{steps[at]}</span>
      </span>
      <span role="img" aria-label={`${title}: ${steps[at]} (${at + 1} / ${steps.length})`} className="grid grid-cols-5 gap-1">
        {steps.map((s, i) => <span key={s} aria-hidden title={s} className={`h-2 rounded-full ${i === at ? fill[tone] : "bg-nx-ink/10"}`} />)}
      </span>
    </div>
  );
}

function SchoolCard({ school }: { school: NextUiSchool }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const rc = school.report_card;
  return (
    <article className="flex flex-col gap-2 rounded-xl bg-nx-page p-4" data-testid={`nb-school-${school.level}`}>
      <span className="text-caption nx-muted">{t(`profile.nb.schools.level.${school.level}`)}{school.grades ? ` · ${t("profile.nb.schools.grades", { grades: school.grades })}` : ""}</span>
      <span className="flex flex-wrap items-center gap-2">
        {school.cps_url ? (
          <a href={school.cps_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-semibold underline underline-offset-2">
            {school.name ?? t("profile.nb.schools.unnamed")}<SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
          </a>
        ) : <span className="font-semibold">{school.name ?? t("profile.nb.schools.unnamed")}</span>}
      </span>
      {rc?.designation && (
        <RatingScale testId={`nb-rating-${school.level}`} title={t("profile.nb.schools.stateRating", { year: rc.year })} definition={t("profile.nb.schools.stateRatingDef")}
          steps={DESIGNATIONS.map((d) => t(`profile.nb.schools.designation.${d}`))} at={DESIGNATIONS.indexOf(rc.designation)} tone={designationTone(rc.designation)} />
      )}
      {rc?.culture && CULTURE.includes(rc.culture.toLowerCase()) && (
        <RatingScale testId={`nb-culture-${school.level}`} title={t("profile.nb.schools.culture")} definition={t("profile.nb.schools.cultureDef")}
          steps={CULTURE.map((c) => t(`profile.nb.schools.cultureLevel.${c.replace(/ /g, "_")}`))} at={CULTURE.indexOf(rc.culture.toLowerCase())} tone="gray" />
      )}
      {rc ? (
        // The rates as rings with icons, like the score tiles (owner: the numbers read tight as a list).
        <ul className="grid grid-cols-2 gap-3 min-[360px]:grid-cols-4" data-testid={`nb-school-rates-${school.level}`}>
          {([
            ["reading", BookOpen, rc.ela_pct, rc.ela_source],
            ["math", Calculator, rc.math_pct, rc.math_source],
            ...(school.level === "high" ? [["graduation", GraduationCap, rc.graduation_4yr_pct, undefined] as const] : []),
          ] as const).map(([key, Icon, v, src]) => (
            <li key={key} className="flex flex-col items-center gap-1 text-center">
              {v != null
                ? <ScoreRing value={Math.round(v)} suffix="%" size={48} inkClass="text-nx-ink" label={`${t(`profile.nb.schools.${key}`)}: ${Math.round(v)}%`} />
                : <span className="grid h-12 w-12 place-items-center rounded-full border-4 border-nx-ink/10 text-caption nx-muted">—</span>}
              <span className="inline-flex items-center gap-1 text-caption leading-tight"><Icon aria-hidden className="h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} />{t(`profile.nb.schools.short.${key}`)}</span>
              {src && <span className="text-[0.6875rem] leading-tight nx-muted">{t("profile.nb.schools.hsTest")}</span>}
              {v == null && <span className="text-[0.6875rem] leading-tight nx-muted">{t("profile.nb.schools.notPublished")}</span>}
            </li>
          ))}
          <li className="flex flex-col items-center gap-1 text-center">
            <span className="grid h-12 w-12 place-items-center rounded-full bg-nx-block"><UsersIcon aria-hidden className="h-5 w-5" strokeWidth={STROKE} /></span>
            <span className="text-caption font-semibold tabular-nums leading-tight">{rc.enrollment != null ? rc.enrollment.toLocaleString(numLocale(lng)) : "—"}</span>
            <span className="text-caption leading-tight nx-muted">{t("profile.nb.schools.short.students")}</span>
          </li>
        </ul>
      ) : <p className="text-caption nx-muted">{t("profile.nb.schools.noReportCard")}</p>}
      {school.report_card_url && (
        <a href={school.report_card_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-caption underline underline-offset-2">
          {t("profile.nb.schools.reportCard", { year: rc?.year ?? "" })}<SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
        </a>
      )}
    </article>
  );
}

// ── Around the lot: small cards (owner's review: the details table becomes cards) ───────────────────────────

function NearbyCards({ data, area }: { data: ScorecardResponse; area: string }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const nb = data.context?.neighborhood;
  const nf = (n: number) => n.toLocaleString(numLocale(lng));
  // A 20-minute mile, the usual walking pace: a distance reads as a walk.
  const walk = (mi: number | null | undefined) => (mi == null ? null : t("profile.nb.near.walk", { min: Math.max(1, Math.round(mi * 20)), mi: mi.toFixed(2) }));
  const cards: Array<{ key: string; icon: ReactNode; title: string; main: ReactNode; sub?: ReactNode }> = [];
  const tr = nb?.transit;
  if (tr?.nearest_cta_rail) {
    cards.push({
      key: "cta", icon: <TrainFront aria-hidden className="h-5 w-5" strokeWidth={STROKE} />, title: t("profile.nb.near.cta"),
      main: tr.nearest_cta_rail,
      sub: (
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          {tr.cta_lines.map((l) => { const c = CTA_LINE[l.replace(/ Line$/, "")]; return <span key={l} className="inline-flex items-center gap-1"><span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ background: c ?? "currentColor" }} />{l}</span>; })}
          <span>{walk(tr.cta_rail_distance_mi)}</span>
        </span>
      ),
    });
  }
  if (tr?.nearest_metra) {
    cards.push({ key: "metra", icon: <TrainTrack aria-hidden className="h-5 w-5" strokeWidth={STROKE} />, title: t("profile.nb.near.metra"), main: tr.nearest_metra, sub: [tr.metra_line, walk(tr.metra_distance_mi)].filter(Boolean).join(" · ") });
  }
  const dv = nb?.divvy;
  if (dv?.nearest_station) {
    cards.push({
      key: "divvy", icon: <Bike aria-hidden className="h-5 w-5" strokeWidth={STROKE} />, title: t("profile.nb.near.divvy"), main: dv.nearest_station,
      sub: [walk(dv.distance_mi), dv.docks != null ? t("profile.nb.near.docks", { count: dv.docks }) : null, t("profile.nb.near.stations", { count: dv.stations_within_radius })].filter(Boolean).join(" · "),
    });
  }
  const tf = nb?.traffic;
  if (tf?.road && tf.daily_vehicles != null) {
    const perMin = Math.round(tf.daily_vehicles / 1440);
    cards.push({
      key: "traffic", icon: <Car aria-hidden className="h-5 w-5" strokeWidth={STROKE} />, title: t("profile.nb.near.traffic"),
      main: <span className="tabular-nums">{t("profile.nb.near.perDay", { n: nf(tf.daily_vehicles) })}</span>,
      sub: t("profile.nb.near.trafficOn", { road: humanizeShoutyCase(tf.road), perMin }),
    });
  }
  const wd = nb?.ward;
  if (wd) {
    cards.push({
      key: "ward", icon: <Landmark aria-hidden className="h-5 w-5" strokeWidth={STROKE} />, title: t("profile.nb.near.ward", { ward: wd.ward }),
      main: wd.alderman ? t("profile.nb.near.alder", { name: wd.alderman.split(", ").reverse().join(" ") }) : t("profile.nb.near.noAlder"),
      sub: (
        <span className="flex flex-wrap gap-x-3 gap-y-1">
          {wd.phone && <a href={`tel:${wd.phone.replace(/[^0-9+]/g, "")}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline underline-offset-2"><Phone aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{wd.phone}</a>}
          {wd.email && <a href={`mailto:${wd.email}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline underline-offset-2"><Mail aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{t("profile.nb.near.email")}</a>}
          {wd.website && <a href={wd.website} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline underline-offset-2">{t("profile.nb.near.website")}<SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} /></a>}
        </span>
      ),
    });
  }
  const ad = areaDemographics(data);
  const hh = data.context?.neighborhood?.rent?.trend;
  if (ad?.population != null) {
    const ch = hh?.earlier.households && hh.later.households ? Math.round(((hh.later.households - hh.earlier.households) / hh.earlier.households) * 100) : null;
    cards.push({
      key: "area", icon: <UsersIcon aria-hidden className="h-5 w-5" strokeWidth={STROKE} />, title: t("profile.nb.near.area", { area }),
      main: <span className="tabular-nums">{t("profile.nb.near.residents", { n: nf(ad.population) })}</span>,
      sub: [ad.acs_period ? t("profile.money.rent.census", { period: ad.acs_period }) : null, ch != null ? t("profile.nb.near.renters", { pct: Math.abs(ch), sign: ch >= 0 ? "+" : "−", period: hh!.earlier.period }) : null].filter(Boolean).join(" · "),
    });
  }
  if (!cards.length) return <p className="nx-muted">{t("profile.nb.near.none")}</p>;
  return (
    <div className="nx-cq"><ul className="nx-cards nx-cards-even" data-testid="nb-nearby">
      {cards.map((c) => (
        <li key={c.key} className="flex gap-3 rounded-2xl bg-nx-block p-4" data-card={c.key}>
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-nx-page">{c.icon}</span>
          <span className="flex min-w-0 flex-col gap-1">
            <span className="text-caption nx-muted">{c.title}</span>
            <span className="font-semibold [overflow-wrap:anywhere]">{c.main}</span>
            {c.sub && <span className="text-caption nx-muted">{c.sub}</span>}
          </span>
        </li>
      ))}
    </ul></div>
  );
}
