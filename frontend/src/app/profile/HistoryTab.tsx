// History tab (brief "Property Profile", History: "What has happened to this property?"; decision Item 103). The tab
// shape every tab has: the sentence → stat tiles (last market sale, year built, City permits, open violations) → one
// wide block, the timeline (kinds as chips, one lane per kind across the years, then the events newest first; a
// permit opens its page, an inspection expands its violations, a zoning record links to the Clerk) → the building
// (each fact, "Records differ" opening a page with every source) and what is on the record (City-owned, scofflaw,
// tax sales, the CHRS rating, tax appeals) → a collapsed list of the sources and what each covers. Appeals and
// non-market transfers start off (owner: everything but the noise). One plain column on a phone (owner). Late
// sources keep their place and say "Couldn't check in time · Retry" (Item 89). No predictions (rule 11).
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ArrowLeftRight, CalendarClock, ChevronDown, ChevronRight, FileClock, Hammer, LandPlot, Scale, SquareArrowOutUpRight, TriangleAlert, X,
  type LucideIcon,
} from "lucide-react";
import type { ScorecardResponse } from "../../lib/api";
import { Block, Pill, StatTile } from "../ui/Blocks";
import { Term } from "../ui/Term";
import { useAskHandoff } from "../ask/askContext";
import { ICON, STROKE } from "../icons";
import { numLocale } from "./profileModel";
import { usd, type LateBlockState } from "./moneyModel";
import { BarsSkeleton, LateSlot, RetryLine } from "./LateSlot";
import {
  DEFAULT_ON, KINDS, factRows, factText, historyModel, historySentence, historySource, laneMarks, listed, rangeText,
  type BuildingFact, type BuildingRecords, type EventKind, type HistoryEvent,
} from "./historyModel";

const SHOWN = 6;

/** Each kind's icon and color (Coastal categories; a sale of this lot is this lot's black). Never color alone. */
// Dark icons on the pale category colors (as the map's pins, Item 102); the page's own color on this lot's black/white.
const DARK = "#1C1C1C";
const KIND_LOOK: Record<EventKind, { icon: LucideIcon; color: string; ink: string }> = {
  sale: { icon: ICON.sale, color: "rgb(var(--nx-lot))", ink: "rgb(var(--nx-page))" },
  transfer: { icon: ArrowLeftRight, color: "rgb(var(--nx-cat-6))", ink: DARK },
  permit: { icon: Hammer, color: "rgb(var(--nx-cat-1))", ink: DARK },
  violation: { icon: TriangleAlert, color: "rgb(var(--nx-cat-5))", ink: DARK },
  zoning: { icon: LandPlot, color: "rgb(var(--nx-cat-3))", ink: DARK },
  appeal: { icon: Scale, color: "rgb(var(--nx-cat-7))", ink: DARK },
};

export function HistoryTab({ data, late, timedOutHistory, onRetry }: {
  data: ScorecardResponse;
  /** The `history` part: appeals, parcel flags, the City's permits and violations at the address, building records. */
  late: LateBlockState;
  timedOutHistory: string[];
  onRetry: () => void;
}) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const ask = useAskHandoff();
  const q = (key: string) => t(`profile.history.ask.${key}`, { address: ask?.address ?? "" });
  const def = (key: string) => t(`profile.history.define.${key}`);
  const st = {
    permits: historySource(data, late, "permits_at_address", timedOutHistory),
    violations: historySource(data, late, "violations_at_address", timedOutHistory),
  };
  const recordsSt = historySource(data, late, "building_records", timedOutHistory);
  // Appeals, City lists and the Assessor's permits come in one lookup (`property_history`): only its own deadline counts.
  const recordState: LateBlockState = late === "timedOut" ? (timedOutHistory.includes("property_history") ? "timedOut" : "ready") : late;
  const m = useMemo(() => historyModel(data, t, lng, st), [data, t, lng, st.permits, st.violations]); // eslint-disable-line react-hooks/exhaustive-deps
  const rec = (data.next_ui?.building_records ?? null) as BuildingRecords | null;
  const facts = factRows(data, recordsSt === "ready" ? rec : null);
  const built = facts.find((f) => f.fact === "year_built")!;
  const builtRange = built.differs ? rangeText("year_built", built.sources, lng) : null;
  const violationsRows = data.next_ui?.violations_at_address?.violations ?? [];
  const openViolations = violationsRows.filter((r) => r.status === "OPEN").length;
  const permits = m.events.filter((e) => e.kind === "permit");
  const lastPermitYear = permits[0]?.date.slice(0, 4);
  const firstPermitYear = permits.length ? permits[permits.length - 1].date.slice(0, 4) : null;
  const sale = m.marketSale;

  const [on, setOn] = useState<Set<EventKind>>(() => new Set(DEFAULT_ON));
  const toggle = (k: EventKind) => setOn((cur) => { const n = new Set(cur); if (n.has(k)) n.delete(k); else n.add(k); return n; });

  return (
    <div className="flex flex-col gap-7" data-testid="history-tab">
      <p className="text-nx-answer" data-testid="history-sentence">{historySentence(data, m, t, lng, st)}</p>

      <div className="nx-cq"><ul className="nx-tiles" data-testid="history-tiles">
        <StatTile
          testId="tile-sale" tone="a" icon={<ICON.sale className="h-5 w-5" strokeWidth={STROKE} />}
          label={<Term label={t("profile.tiles.lastSale")} definition={def("sale")} question={q("sale")} />}
          figure={sale?.price != null ? usd(sale.price, lng) : "—"}
          note={sale ? t("profile.history.tile.saleNote", { date: monthYear(sale.date, lng), years: yearsAgo(sale.date) })
            : m.counts.transfer > 0 ? t("profile.history.tile.onlyTransfers", { count: m.counts.transfer }) : t("profile.tiles.noSaleOnRecord")}
        />
        <StatTile
          testId="tile-built" tone="b" icon={<CalendarClock className="h-5 w-5" strokeWidth={STROKE} />}
          label={<Term label={t("profile.history.fact.year_built")} definition={def("built")} question={q("built")} />}
          checking={late === "loading" && built.value == null}
          figure={builtRange ?? factText("year_built", built.value, lng)}
          note={builtRange ? t("profile.history.tile.builtSources", { list: built.sources.map((x) => t(`profile.history.source.${x.source}`, { defaultValue: x.source })).join(" · ") })
            : built.source ? t("profile.history.tile.builtSource", { source: t(`profile.history.source.${built.source}`, { defaultValue: built.source }) }) : undefined}
          warning={built.differs ? <DifferButton fact="year_built" /> : undefined}
        />
        <StatTile
          testId="tile-permits" tone="a" icon={<Hammer className="h-5 w-5" strokeWidth={STROKE} />}
          label={<Term label={t("profile.history.tile.permits")} definition={def("permits")} question={q("permits")} />}
          checking={st.permits === "loading"}
          figure={m.permitsFrom ? String(m.counts.permit) : "—"}
          note={st.permits === "loading" ? t("profile.history.checking.permits")
            : m.permitsFrom === "city" ? (m.counts.permit ? t("profile.history.tile.permitsNote", { first: firstPermitYear, last: lastPermitYear }) : t("profile.history.tile.noPermits"))
            : m.permitsFrom === "assessor" ? t("profile.history.tile.permitsAssessor")
            : t("profile.history.tile.notChecked")}
        />
        <StatTile
          testId="tile-violations" tone="b" icon={<TriangleAlert className="h-5 w-5" strokeWidth={STROKE} />}
          label={<Term label={t("profile.history.tile.violations")} definition={def("violations")} question={q("violations")} />}
          checking={st.violations === "loading"}
          figure={st.violations === "ready" ? String(openViolations) : "—"}
          note={st.violations === "loading" ? t("profile.history.checking.violations")
            : st.violations === "ready" ? (violationsRows.length ? t("profile.history.tile.violationsNote", { count: violationsRows.length }) : t("profile.history.tile.noViolations"))
            : t("profile.history.tile.notChecked")}
        />
      </ul></div>

      <Block
        title={<Term label={t("profile.history.timeline.title")} definition={def("timeline")} question={q("timeline")} />}
        icon={FileClock}
        labelledBy="nx-history-timeline"
      >
        <Timeline data={data} events={m.events} counts={m.counts} on={on} toggle={toggle} firstYear={m.firstYear} lastYear={m.lastYear} />
        <SourceLines st={st} onRetry={onRetry} permitsFrom={m.permitsFrom} />
      </Block>

      <div className="nx-cq"><div className="nx-split nx-split-even">
        <Block title={<Term label={t("profile.history.building.title")} definition={def("building")} question={q("built")} />} icon={ICON.units} labelledBy="nx-history-building">
          <LateSlot state={recordsSt === "none" ? "ready" : recordsSt} what={t("profile.history.what.records")} onRetry={onRetry} skeleton={<BarsSkeleton rows={4} />}>
            <BuildingFacts rows={facts} vacant={recordsSt === "none" && !!data.context?.property} />
          </LateSlot>
        </Block>
        <Block title={<Term label={t("profile.history.record.title")} definition={def("record")} question={q("record")} />} icon={ICON.rules} labelledBy="nx-history-record">
          <LateSlot state={recordState} what={t("profile.history.what.record")} onRetry={onRetry} skeleton={<BarsSkeleton rows={4} />}>
            <OnTheRecord data={data} appealsOn={on.has("appeal")} showAppeals={() => { if (!on.has("appeal")) toggle("appeal"); document.getElementById("nx-history-timeline")?.scrollIntoView({ block: "start", behavior: "smooth" }); }} />
          </LateSlot>
        </Block>
      </div></div>

      <details className="group rounded-2xl bg-nx-block p-5 sm:p-6" data-testid="history-details">
        <summary className="flex cursor-pointer list-none items-center gap-2 font-semibold touch-target">
          <ChevronRight aria-hidden className="h-4 w-4 transition-transform group-open:rotate-90" strokeWidth={STROKE} />
          {t("profile.history.details.title")}
        </summary>
        <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 text-caption sm:grid-cols-2">
          {(["sales", "permits", "violations", "zoning", "appeals", "building"] as const).map((k) => (
            <div key={k} className="flex flex-col gap-0.5">
              <dt className="font-semibold">{t(`profile.history.details.${k}.name`)}</dt>
              <dd className="nx-muted">{t(`profile.history.details.${k}.covers`)}</dd>
            </div>
          ))}
        </dl>
      </details>
    </div>
  );
}

const monthYear = (iso: string, lng: string) => new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString(numLocale(lng), { month: "short", year: "numeric" });
const yearsAgo = (iso: string) => Math.max(0, new Date().getFullYear() - Number(iso.slice(0, 4)));

function DifferButton({ fact }: { fact: BuildingFact }) {
  const { t } = useTranslation("next");
  const ask = useAskHandoff();
  return (
    <button type="button" onClick={() => ask?.openRecords?.(fact)} aria-haspopup="dialog" data-testid={`differ-${fact}`}
      className="inline-flex items-center gap-1 rounded-lg bg-nx-pill-yellow-bg px-2 py-px text-caption text-nx-pill-yellow hover:underline touch-target">
      <TriangleAlert aria-hidden className="h-3 w-3" strokeWidth={2} />{t("profile.history.records.differ")}
      <ChevronRight aria-hidden className="h-3 w-3" strokeWidth={2} />
    </button>
  );
}

/** What each of History's own sources is doing: checking, couldn't check (Retry), or the Assessor standing in. */
function SourceLines({ st, onRetry, permitsFrom }: {
  st: { permits: LateBlockState | "none"; violations: LateBlockState | "none" }; onRetry: () => void; permitsFrom: "city" | "assessor" | null;
}) {
  const { t } = useTranslation("next");
  const lines: React.ReactNode[] = [];
  const checking = [st.permits === "loading" ? t("profile.history.what.permits") : null, st.violations === "loading" ? t("profile.history.what.violations") : null].filter(Boolean);
  if (checking.length) {
    lines.push(<p key="checking" role="status" className="text-caption nx-muted">{t("profile.money.checking", { what: checking.join(t("profile.history.and")) })}</p>);
  }
  for (const [k, s] of [["permits", st.permits], ["violations", st.violations]] as const) {
    if (s === "timedOut" || s === "failed") lines.push(<RetryLine key={k} state={s} what={t(`profile.history.what.${k}`)} onRetry={onRetry} />);
  }
  if (permitsFrom === "assessor") lines.push(<p key="assessor" className="text-caption nx-muted">{t("profile.history.assessorStandIn")}</p>);
  if (st.permits === "none" && st.violations === "none") lines.push(<p key="none" className="text-caption nx-muted">{t("profile.history.noAddressSearch")}</p>);
  return lines.length ? <div className="flex flex-col gap-1.5" data-testid="history-sources">{lines}</div> : null;
}

// ── The timeline ─────────────────────────────────────────────────────────────────────────────────────

function Timeline({ data, events, counts, on, toggle, firstYear, lastYear }: {
  data: ScorecardResponse; events: HistoryEvent[]; counts: Record<EventKind, number>; on: Set<EventKind>; toggle: (k: EventKind) => void;
  firstYear: number; lastYear: number;
}) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  const ask = useAskHandoff();
  const [pick, setPick] = useState<{ year: number; kind: EventKind } | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const listRef = useRef<HTMLUListElement | null>(null);
  const marks = laneMarks(events, on);
  const lanes = KINDS.filter((k) => on.has(k) && counts[k] > 0);
  const span = Math.max(1, lastYear - firstYear + 1);
  const x = (year: number) => ((year - firstYear + 0.5) / span) * 100;
  const step = span > 30 ? 10 : 5;
  const ticks: number[] = [];
  for (let y = Math.ceil(firstYear / step) * step; y <= lastYear; y += step) ticks.push(y);
  const rows = listed(events, on, pick?.year ?? null, pick?.kind ?? null);
  const shown = all ? rows : rows.slice(0, SHOWN);
  const toggleAll = () => { setAll((a) => !a); listRef.current?.scrollTo?.({ top: 0 }); };
  void data;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("profile.history.timeline.kinds")} data-testid="history-kinds">
        {KINDS.map((k) => {
          const Icon = KIND_LOOK[k].icon;
          const pressed = on.has(k);
          return (
            <button key={k} type="button" aria-pressed={pressed} onClick={() => { toggle(k); setPick(null); setAll(false); }} data-kind={k}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-caption touch-target ${pressed ? "border-nx-ink bg-nx-ink text-nx-on-ink" : "border-nx-ink/15 hover:bg-nx-ink/5"} ${counts[k] === 0 ? "opacity-60" : ""}`}>
              <Icon aria-hidden className="h-3.5 w-3.5" strokeWidth={2} />
              {t(`profile.history.kind.${k}`)}
              <span className="tabular-nums">{counts[k]}</span>
            </button>
          );
        })}
      </div>

      {lanes.length > 0 && (
        <figure className="flex flex-col gap-1" aria-label={t("profile.history.timeline.chart", { from: firstYear, to: lastYear })} data-testid="history-lanes">
          {lanes.map((k) => {
            const Icon = KIND_LOOK[k].icon;
            return (
              <div key={k} className="grid grid-cols-[minmax(0,6.5rem)_1fr] items-center gap-3" data-lane={k}>
                <span className="flex min-w-0 items-center gap-1.5 text-caption nx-muted">
                  <Icon aria-hidden className="h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} /><span className="truncate">{t(`profile.history.kind.${k}`)}</span>
                </span>
                <div className="relative h-8 border-b border-nx-ink/10">
                  {marks.filter((mk) => mk.kind === k).map((mk) => {
                    const id = `${k}:${mk.year}`;
                    const picked = pick?.year === mk.year && pick.kind === k;
                    const size = mk.count > 1 ? 22 : 14;
                    const words = t("profile.history.timeline.mark", { count: mk.count, kind: t(`profile.history.kindCount.${k}`, { count: mk.count }), year: mk.year });
                    return (
                      <button key={id} type="button" aria-label={words} aria-pressed={picked}
                        onClick={() => { setPick(picked ? null : { year: mk.year, kind: k }); setAll(false); }}
                        onMouseEnter={() => setHover(id)} onMouseLeave={() => setHover((h) => (h === id ? null : h))} onFocus={() => setHover(id)} onBlur={() => setHover(null)}
                        className={`absolute top-1/2 grid -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full text-[11px] font-semibold tabular-nums ${picked ? "ring-2 ring-nx-ink ring-offset-2 ring-offset-nx-block" : ""}`}
                        style={{ left: `${x(mk.year)}%`, width: size, height: size, background: KIND_LOOK[k].color, color: KIND_LOOK[k].ink }}>
                        {mk.count > 1 ? mk.count : null}
                        {hover === id && (
                          <span role="tooltip" className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 -translate-x-1/2 whitespace-nowrap rounded-lg bg-nx-ink px-2 py-1 text-caption font-normal text-nx-on-ink">{words}</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
          <div className="grid grid-cols-[minmax(0,6.5rem)_1fr] gap-3" aria-hidden>
            <span />
            <div className="relative h-4 text-caption nx-muted">
              {ticks.map((y) => <span key={y} className="absolute -translate-x-1/2 tabular-nums" style={{ left: `${x(y)}%` }}>{y}</span>)}
            </div>
          </div>
          <figcaption className="text-caption nx-muted">{t("profile.history.timeline.how")}</figcaption>
        </figure>
      )}

      {pick && (
        <p className="flex flex-wrap items-center gap-2 text-caption">
          <span>{t("profile.history.timeline.showing", { year: pick.year, kind: t(`profile.history.kind.${pick.kind}`) })}</span>
          <button type="button" onClick={() => setPick(null)} className="inline-flex items-center gap-1 underline underline-offset-2 touch-target" data-testid="history-unpick">
            <X aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{t("profile.history.timeline.allYears")}
          </button>
        </p>
      )}

      {rows.length === 0 ? (
        <p className="nx-muted" data-testid="history-empty">{events.length ? t("profile.history.timeline.noneOn") : t("profile.history.timeline.none")}</p>
      ) : (
        <ul ref={listRef} className={`flex flex-col gap-2 ${all ? "max-h-[34rem] overflow-y-auto overscroll-contain pr-1" : ""}`} data-testid="history-events">
          {shown.map((e) => <EventRow key={e.id} e={e} lng={lng} onOpenPermit={e.permit && ask?.openPermit ? () => ask.openPermit!(e.permit!) : undefined} />)}
        </ul>
      )}
      {rows.length > SHOWN && (
        <button type="button" onClick={toggleAll} aria-expanded={all}
          className="inline-flex w-fit items-center gap-1.5 rounded-lg bg-nx-page px-3 py-2 text-caption font-semibold hover:bg-nx-ink/5 touch-target" data-testid="history-more">
          <ChevronDown aria-hidden className={`h-4 w-4 transition-transform ${all ? "rotate-180" : ""}`} strokeWidth={STROKE} />
          {all ? t("profile.nb.building.fewer") : t("profile.nb.building.showAll", { count: rows.length })}
        </button>
      )}
    </div>
  );
}

function EventRow({ e, lng, onOpenPermit }: { e: HistoryEvent; lng: string; onOpenPermit?: () => void }) {
  const { t } = useTranslation("next");
  const [open, setOpen] = useState(false);
  const look = KIND_LOOK[e.kind];
  const Icon = look.icon;
  const when = e.yearOnly ? e.date.slice(0, 4) : monthYear(e.date, lng);
  const body = (
    <>
      <span aria-hidden className="grid h-7 w-7 shrink-0 place-items-center rounded-full" style={{ background: look.color, color: look.ink }}>
        <Icon className="h-3.5 w-3.5" strokeWidth={2} />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex flex-wrap items-baseline gap-x-2">
          <span className="font-semibold">{e.title}</span>
          <span className="text-caption nx-muted">{t(`profile.history.kind.${e.kind}`)}</span>
        </span>
        <span className="flex flex-wrap gap-1.5">
          <Pill tone="gray">{when}</Pill>
          {e.pills.map((p, i) => <Pill key={i} tone={p.tone ?? "gray"}>{p.text}</Pill>)}
        </span>
      </span>
    </>
  );
  const cls = "group flex w-full items-start gap-3 rounded-xl bg-nx-page p-3 text-left";
  if (onOpenPermit) {
    return (
      <li data-kind={e.kind}>
        <button type="button" onClick={onOpenPermit} aria-haspopup="dialog" className={`${cls} hover:bg-nx-ink/5`}>
          {body}<ChevronRight aria-hidden className="h-4 w-4 shrink-0 self-center nx-muted transition-transform group-hover:translate-x-0.5" strokeWidth={STROKE} />
        </button>
      </li>
    );
  }
  if (e.violations) {
    return (
      <li data-kind={e.kind} className="flex flex-col">
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className={`${cls} hover:bg-nx-ink/5`}>
          {body}<ChevronDown aria-hidden className={`h-4 w-4 shrink-0 self-center nx-muted transition-transform ${open ? "rotate-180" : ""}`} strokeWidth={STROKE} />
        </button>
        {open && (
          <ul className="ml-10 mt-1 flex flex-col gap-1.5 border-l border-nx-ink/10 pl-3" data-testid="violation-list">
            {e.violations.map((v, i) => (
              <li key={i} className="flex flex-wrap items-baseline justify-between gap-x-3 text-caption">
                <span className="min-w-0 flex-1">{sentence(v.description) ?? v.code ?? "—"}</span>
                <Pill tone={v.status === "OPEN" ? "red" : "gray"}>{v.status === "OPEN" ? t("profile.history.status.open") : v.status === "COMPLIED" ? t("profile.history.status.complied") : sentence(v.status) ?? "—"}</Pill>
              </li>
            ))}
          </ul>
        )}
      </li>
    );
  }
  if (e.href) {
    return (
      <li data-kind={e.kind}>
        <a href={e.href} target="_blank" rel="noopener noreferrer" className={`${cls} hover:bg-nx-ink/5`}>
          {body}<SquareArrowOutUpRight aria-hidden className="h-4 w-4 shrink-0 self-center nx-muted" strokeWidth={STROKE} />
          <span className="sr-only">{t("profile.opensInNewTab")}</span>
        </a>
      </li>
    );
  }
  return <li data-kind={e.kind}><div className={cls}>{body}</div></li>;
}

const sentence = (s: string | null | undefined) => {
  if (!s) return null;
  const x = s.replace(/\s+/g, " ").trim().toLowerCase();
  return x.charAt(0).toUpperCase() + x.slice(1);
};

// ── The building and what is on the record ─────────────────────────────────────────────────────────────

function BuildingFacts({ rows, vacant }: { rows: ReturnType<typeof factRows>; vacant: boolean }) {
  const { t, i18n } = useTranslation("next");
  const lng = i18n.language;
  if (vacant && rows.every((r) => r.value == null)) return <p className="nx-muted">{t("profile.history.building.vacant")}</p>;
  return (
    <dl className="flex flex-col divide-y divide-nx-ink/10" data-testid="history-building">
      {rows.map((r) => {
        const range = r.differs && r.fact !== "units" ? rangeText(r.fact, r.sources, lng) : null;
        return (
          <div key={r.fact} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 py-2.5">
            <dt className="flex flex-col">
              <span>{t(`profile.history.fact.${r.fact}`)}</span>
              {(range ? r.sources.map((x) => x.source) : r.source ? [r.source] : []).length > 0 && (
                <span className="text-caption nx-muted">{(range ? r.sources.map((x) => x.source) : [r.source!]).map((x) => t(`profile.history.source.${x}`, { defaultValue: x })).join(" · ")}</span>
              )}
            </dt>
            <dd className="flex flex-wrap items-center justify-end gap-2">
              <span className="text-body font-semibold tabular-nums">
                {range ?? factText(r.fact, r.value, lng)}{r.value != null && r.fact === "bldg_sqft" && !range ? ` ${t("profile.history.sqft")}` : ""}
              </span>
              {r.differs && r.fact !== "units" && <DifferButton fact={r.fact} />}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

function OnTheRecord({ data, appealsOn, showAppeals }: { data: ScorecardResponse; appealsOn: boolean; showAppeals: () => void }) {
  const { t } = useTranslation("next");
  const prop = data.context?.property;
  const f = prop?.flags;
  const appeals = prop?.appeals?.records ?? [];
  const cut = appeals.filter((a) => (a.reduction_pct ?? 0) > 0);
  const rows: Array<{ key: string; label: string; value: string; tone: "gray" | "yellow" | "red" | "green" }> = [
    { key: "cityOwned", label: t("profile.history.record.cityOwned"), value: f?.city_owned ? t("profile.history.yes") : t("profile.history.no"), tone: f?.city_owned ? "yellow" : "gray" },
    { key: "scofflaw", label: t("profile.history.record.scofflaw"), value: f?.scofflaw ? t("profile.history.yes") : t("profile.history.no"), tone: f?.scofflaw ? "red" : "gray" },
    { key: "str", label: t("profile.history.record.str"), value: f?.str_prohibited ? t("profile.history.yes") : t("profile.history.no"), tone: f?.str_prohibited ? "yellow" : "gray" },
    { key: "chrs", label: t("profile.history.record.chrs"), value: f?.chrs_rating ? t(`profile.history.record.chrsRating.${f.chrs_rating}`) : t("profile.history.record.notRated"), tone: f?.chrs_rating ? "yellow" : "gray" },
    {
      key: "taxSale", label: t("profile.history.record.taxSale"),
      value: f && (f.tax_sale_years.length || f.scavenger_sale_years.length)
        ? [...f.tax_sale_years, ...f.scavenger_sale_years].sort().join(", ") : t("profile.history.record.noneOnRecord"),
      tone: f && (f.tax_sale_years.length || f.scavenger_sale_years.length) ? "yellow" : "gray",
    },
  ];
  return (
    <div className="flex flex-col gap-3" data-testid="history-record">
      <dl className="flex flex-col divide-y divide-nx-ink/10">
        {rows.map((r) => (
          <div key={r.key} className="flex items-center justify-between gap-3 py-2.5" data-record={r.key}>
            <dt>{r.label}</dt>
            <dd><Pill tone={r.tone}>{r.value}</Pill></dd>
          </div>
        ))}
        <div className="flex flex-wrap items-center justify-between gap-3 py-2.5" data-record="appeals">
          <dt>{t("profile.history.record.appeals")}</dt>
          <dd className="flex items-center gap-2">
            <Pill tone="gray">{appeals.length ? t("profile.history.record.appealsCount", { count: appeals.length, cut: cut.length }) : t("profile.history.record.noneOnRecord")}</Pill>
            {appeals.length > 0 && !appealsOn && (
              <button type="button" onClick={showAppeals} className="text-caption underline underline-offset-2 touch-target" data-testid="show-appeals">{t("profile.history.record.showAppeals")}</button>
            )}
          </dd>
        </div>
      </dl>
      {f?.tax_sale_years.length || f?.scavenger_sale_years.length ? <p className="text-caption nx-muted">{t("profile.history.record.taxSaleNote")}</p> : null}
    </div>
  );
}
