// The evidence panel's Sources tab (wireframe v2, approved 2026-11-12): one numbered list of what the answer used,
// one row open at a time, each shown as what it is: a code section opened on the highlighted passage the answer used
// (the rest quieter), a code table trimmed to the district's row, and records the way the Profile shows the same data
// (crime as figures and bars, building as permit cards, 311 as bars, the lot's facts as tiles).
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, SquareArrowOutUpRight } from "lucide-react";
import type { ContextObject, Message } from "../../lib/types";
import { formatDay, humanizeShoutyCase } from "../../lib/format";
import { streetViewUrl } from "../map/mapInfo";
import { STROKE } from "../icons";
import { sourcesFor, type SourceItem } from "./evidenceModel";
import { constructionRecord, crimeRecord, factTiles, requestsRecord, type BuildCard } from "./recordModel";
import { LENS_COLORS } from "./chatLens";
import { lotHref } from "./chatModel";

export type MapLayer = "building" | "crime";

export function EvidenceSources({ message, openN, onShowOnMap }: { message: Message; openN: number | null; onShowOnMap: (layer: MapLayer) => void }) {
  const { t, i18n } = useTranslation("next");
  const items = useMemo(() => sourcesFor(message), [message]);
  const [open, setOpen] = useState<number | null>(openN ?? (items.length === 1 ? items[0].n : null));
  const rows = useRef<Record<number, HTMLLIElement | null>>({});
  useEffect(() => {
    if (openN == null) return;
    setOpen(openN);
    rows.current[openN]?.scrollIntoView?.({ block: "nearest" });
  }, [openN]);
  const ctx = message.context;
  const locale = i18n.language.startsWith("es") ? "es-MX" : "en-US";

  return (
    <ol className="flex flex-col gap-2" data-testid="chat-sources">
      {items.map((it) => {
        const isOpen = open === it.n;
        const head = header(it, ctx, t);
        return (
          <li key={it.n} ref={(el) => { rows.current[it.n] = el; }} className={`rounded-2xl ${isOpen ? "bg-nx-block" : "ring-1 ring-nx-ink/10"}`} data-testid={`source-${it.kind}`}>
            <button type="button" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : it.n)} className="flex w-full items-center gap-3 px-3 py-2.5 text-left touch-target">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-nx-pill-purple-bg text-caption font-semibold text-nx-pill-purple">{it.n}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{head.title}</span>
                <span className="block truncate text-caption nx-muted">{head.from}</span>
              </span>
              <ChevronDown aria-hidden className={`h-4 w-4 shrink-0 transition-transform ${isOpen ? "rotate-180" : ""}`} strokeWidth={STROKE} />
            </button>
            {isOpen && (
              <div className="flex flex-col gap-3 px-3 pb-3 sm:pl-12">
                <SourceBody it={it} message={message} locale={locale} onShowOnMap={onShowOnMap} />
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function header(it: SourceItem, ctx: ContextObject | undefined, t: (k: string, o?: Record<string, unknown>) => string): { title: string; from: string } {
  const area = ctx?.community_area_name ?? t("chat.lens.theArea");
  if (it.kind === "code") {
    const c = it.chunk;
    return { title: c.section_title ? `§ ${c.section} ${c.section_title}` : `§ ${c.section}`, from: ctx?.code_vintage?.current_through ? t("chat.src.codeFromDate", { date: formatDay(ctx.code_vintage.current_through) }) : t("chat.codeSource") };
  }
  const keys: Record<string, [string, string]> = {
    lot: ["chat.src.lot", "chat.src.lotFrom"], facts: ["chat.src.facts", "chat.src.factsFrom"], crime: ["chat.src.crime", "chat.src.cityFrom"],
    construction: ["chat.src.construction", "chat.src.cityFrom"], requests: ["chat.src.requests", "chat.src.cityFrom"],
    violations: ["chat.src.violations", "chat.src.cityFrom"], vacant: ["chat.src.vacant", "chat.src.cityFrom"],
    business: ["chat.src.business", "chat.src.cityFrom"], food: ["chat.src.food", "chat.src.cityFrom"],
  };
  const [title, from] = keys[it.kind];
  return { title: it.kind === "lot" ? (ctx?.resolved_address ?? t(title)) : t(title, { area }), from: t(from, { date: ctx?.data_as_of ?? "" }) };
}

function SourceBody({ it, message, locale, onShowOnMap }: { it: SourceItem; message: Message; locale: string; onShowOnMap: (l: MapLayer) => void }) {
  const { t } = useTranslation("next");
  const ctx = message.context;
  const map = message.mapData;
  const money = new Intl.NumberFormat(locale, { style: "currency", currency: "USD", maximumFractionDigits: 0, notation: "compact" });
  const num = new Intl.NumberFormat(locale);
  const link = "inline-flex items-center gap-1 text-caption underline underline-offset-2 hover:no-underline touch-target";

  if (it.kind === "code") return <CodeBody it={it} />;

  if (it.kind === "lot") {
    const pin = ctx?.property?.pin14 ?? null;
    const zone = ctx?.parcel_zoning?.zone_class ?? null;
    const how = (ctx as unknown as { parcel_resolution?: string } | undefined)?.parcel_resolution;
    return (
      <>
        <p className="text-caption">{[pin && t("chat.src.pin", { pin: formatPin(pin) }), zone, ctx?.community_area_name].filter(Boolean).join(" · ")}</p>
        <p className="text-caption nx-muted">{how === "authoritative" ? t("chat.src.matchedExact") : t("chat.src.matchedNear")}</p>
        {ctx?.resolved_address && (
          <a href={lotHref(ctx.resolved_address, pin)} target="_blank" rel="noopener noreferrer" className={link}>
            {t("chat.src.openProfile")}<SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} /><span className="sr-only">{t("common:opensInNewTab")}</span>
          </a>
        )}
      </>
    );
  }

  if (it.kind === "facts") {
    const tiles = factTiles(ctx?.property);
    if (tiles.length === 0) return <p className="text-caption nx-muted">{t("chat.src.noFacts")}</p>;
    return (
      <div className="grid grid-cols-2 gap-2.5">
        {tiles.map((f, i) => (
          <div key={f.key} className={`flex flex-col gap-0.5 rounded-xl p-3 text-nx-card-ink ${i % 3 === 0 ? "bg-nx-stat-a" : "bg-nx-stat-b"}`} data-testid={`fact-${f.key}`}>
            <span className="text-caption font-semibold">{t(`chat.src.fact.${f.key}`)}</span>
            <span className="text-[1.25rem] font-bold">{f.key === "lot" ? t("chat.src.sqft", { n: num.format(f.value) }) : f.key === "building" ? t("chat.lens.units", { count: f.value }) : money.format(f.value)}</span>
            {f.note != null && <span className="text-caption text-nx-card-ink/70">{f.key === "building" ? t("chat.src.sqft", { n: num.format(Number(f.note)) }) : f.key === "tax" ? t("chat.src.taxYear", { year: f.note }) : formatDay(String(f.note))}</span>}
          </div>
        ))}
      </div>
    );
  }

  if (it.kind === "crime") {
    const r = crimeRecord(ctx, map);
    if (!r) return null;
    const max = Math.max(1, ...r.byType.map((x) => x.n));
    return (
      <>
        <p className="text-caption nx-muted">{r.scope === "near" ? t("chat.src.withinHalf") : t("chat.src.inArea", { area: ctx?.community_area_name ?? t("chat.lens.theArea") })}</p>
        <div className="grid grid-cols-2 gap-2.5">
          <div className="rounded-xl bg-nx-stat-a p-3 text-nx-card-ink"><span className="block text-caption font-semibold">{t("chat.src.violent")}</span><span className="text-[1.5rem] font-bold">{r.violent}</span></div>
          <div className="rounded-xl bg-nx-stat-b p-3 text-nx-card-ink"><span className="block text-caption font-semibold">{t("chat.src.property")}</span><span className="text-[1.5rem] font-bold">{r.property}</span></div>
        </div>
        <div className="flex gap-4 text-caption" aria-hidden>
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: LENS_COLORS.violent }} />{t("chat.src.violent")}</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: LENS_COLORS.property }} />{t("chat.src.property")}</span>
        </div>
        <ul className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_2.5rem] items-center gap-x-2.5 gap-y-1.5 text-caption" aria-label={t("chat.src.byType")}>
          {r.byType.map((x) => (
            <li key={x.type} className="contents">
              <span className="truncate">{humanizeShoutyCase(x.type)}</span>
              <span className="h-2.5 rounded-full" style={{ width: `${(x.n / max) * 100}%`, background: x.kind === "violent" ? LENS_COLORS.violent : x.kind === "property" ? LENS_COLORS.property : LENS_COLORS.other }} />
              <span className="text-right tabular-nums">{x.n}</span>
            </li>
          ))}
          {r.moreTypes.types > 0 && (
            <li className="contents nx-muted"><span>{t("chat.src.moreTypes", { count: r.moreTypes.types })}</span><span /><span className="text-right tabular-nums">{r.moreTypes.n}</span></li>
          )}
        </ul>
        <p className="text-caption nx-muted">
          {[r.arrests != null && t("chat.src.arrests", { n: r.arrests, total: r.total }), r.scope === "near" && r.areaTotal != null && t("chat.lens.inArea", { count: r.areaTotal, area: ctx?.community_area_name ?? t("chat.lens.theArea") })].filter(Boolean).join(" · ")}
        </p>
        {r.scope === "near" && <button type="button" onClick={() => onShowOnMap("crime")} className={`${link} self-start`} data-testid="show-crime-on-map">{t("chat.src.showViolent")}</button>}
      </>
    );
  }

  if (it.kind === "construction") {
    const r = constructionRecord(map);
    if (!r) return <p className="text-caption nx-muted">{t("chat.src.noBuilding")}</p>;
    return (
      <>
        <p className="text-caption nx-muted">{t(r.scope === "near" ? "chat.src.buildNear" : "chat.src.buildArea", { count: r.shown, left: r.leftOut })}</p>
        <ul className="flex flex-col gap-2">
          {r.cards.map((c, i) => <BuildCardView key={i} c={c} money={money} onShowOnMap={() => onShowOnMap("building")} />)}
        </ul>
      </>
    );
  }

  if (it.kind === "requests") {
    const r = requestsRecord(ctx, map);
    if (!r) return null;
    const max = Math.max(1, ...r.rows.map((x) => x.n));
    return (
      <>
        <p className="text-caption nx-muted">{r.scope === "near" ? t("chat.src.withinHalf") : t("chat.src.inArea", { area: ctx?.community_area_name ?? t("chat.lens.theArea") })} · {t("chat.src.openDark")}</p>
        <ul className="grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)_2.5rem] items-center gap-x-2.5 gap-y-1.5 text-caption">
          {r.rows.map((x) => (
            <li key={x.type} className="contents">
              <span className="truncate">{x.type}</span>
              {x.n > 0 ? (
                <span className="flex h-2.5 overflow-hidden rounded-full" style={{ width: `${(x.n / max) * 100}%` }}>
                  <span style={{ width: `${(x.open / x.n) * 100}%`, background: "rgb(var(--nx-chart-3))" }} />
                  <span className="flex-1" style={{ background: "rgb(var(--nx-chart-1))" }} />
                </span>
              ) : <span />}
              <span className="text-right tabular-nums">{x.n || ""}</span>
            </li>
          ))}
        </ul>
      </>
    );
  }

  // Violations, vacant buildings, businesses, food inspections: counts as rows.
  const rows: Array<[string, number]> =
    it.kind === "violations" ? Object.entries(ctx?.violations?.by_category ?? {})
      : it.kind === "vacant" ? (ctx?.vacant_buildings?.recent_reports ?? []).map((v) => [v.address, 1] as [string, number])
      : it.kind === "business" ? Object.entries(ctx?.businesses?.by_license_type ?? {})
      : Object.entries(ctx?.food_inspections?.by_result ?? {});
  return (
    <ul className="flex flex-col gap-1 text-caption">
      {rows.sort((a, b) => b[1] - a[1]).slice(0, 8).map(([k, v]) => (
        <li key={k} className="flex gap-2"><span className="min-w-0 flex-1 truncate">{humanizeShoutyCase(k)}</span>{it.kind !== "vacant" && <span className="tabular-nums">{v}</span>}</li>
      ))}
    </ul>
  );
}

function BuildCardView({ c, money, onShowOnMap }: { c: BuildCard; money: Intl.NumberFormat; onShowOnMap: () => void }) {
  const { t } = useTranslation("next");
  const link = "inline-flex items-center gap-1 text-caption underline underline-offset-2 hover:no-underline touch-target";
  return (
    <li className="flex flex-col gap-1 rounded-xl bg-nx-page p-3 ring-1 ring-nx-ink/10" data-testid="build-card">
      <div className="flex items-center gap-2">
        <span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: LENS_COLORS[c.kind] }} />
        <span className="font-medium">{t(`chat.lens.kind.${c.kind}`)}{c.units ? ` · ${t("chat.lens.units", { count: c.units })}` : ""}</span>
        <span className="flex-1" />
        {c.distanceM != null && <span className="text-caption nx-muted">{t("chat.lens.away", { feet: Math.round(c.distanceM * 3.281) })}</span>}
      </div>
      <span className="text-caption nx-muted">{[c.cost ? money.format(c.cost) : null, c.date ? t("chat.src.issued", { date: formatDay(c.date) }) : null].filter(Boolean).join(" · ")}</span>
      <span className="line-clamp-2 text-caption" title={c.description}>{humanizeShoutyCase(c.description)}</span>
      <span className="flex gap-4">
        <button type="button" onClick={onShowOnMap} className={link}>{t("chat.src.showOnMap")}</button>
        <a href={streetViewUrl(c.lat, c.lon)} target="_blank" rel="noopener noreferrer" className={link}>
          {t("chat.src.streetView")}<SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} /><span className="sr-only">{t("common:opensInNewTab")}</span>
        </a>
      </span>
    </li>
  );
}

/** A code section: the passage the answer used lit up in the full text, the rest quieter; a table trimmed to the
    district's row with the whole table one click away. */
function CodeBody({ it }: { it: Extract<SourceItem, { kind: "code" }> }) {
  const { t, i18n } = useTranslation("next");
  const mark = useRef<HTMLElement | null>(null);
  const [wholeTable, setWholeTable] = useState(false);
  useEffect(() => { mark.current?.scrollIntoView?.({ block: "center" }); }, []);
  const c = it.chunk;
  const date = new Intl.DateTimeFormat(i18n.language.startsWith("es") ? "es-MX" : "en-US", { month: "short", day: "numeric", year: "numeric" });
  return (
    <>
      {it.table ? (
        <div className="flex flex-col gap-2">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-caption" data-testid="code-table">
              <thead><tr>{it.table.header.map((h, i) => <th key={i} className="px-2 py-1 text-left font-medium nx-muted">{h}</th>)}</tr></thead>
              <tbody>
                {it.table.rows.map((r, i) => (wholeTable || it.table!.hit === null || i === it.table!.hit) && (
                  <tr key={i} className={i === it.table!.hit ? "bg-nx-pill-purple-bg font-semibold" : ""}>{r.map((cell, j) => <td key={j} className="px-2 py-1">{cell}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
          {it.table.hit !== null && (
            <button type="button" onClick={() => setWholeTable((w) => !w)} className="self-start text-caption underline underline-offset-2 touch-target">
              {wholeTable ? t("chat.src.tableRow") : t("chat.src.tableAll", { count: it.table.rows.length })}
            </button>
          )}
        </div>
      ) : (
        <div className="max-h-80 overflow-y-auto whitespace-pre-line rounded-lg text-caption leading-relaxed" data-testid="code-text">
          {it.passage ? (
            <>
              <span className="nx-muted">{c.text.slice(0, it.passage[0])}</span>
              <mark ref={mark} className="rounded bg-nx-pill-yellow-bg px-0.5 text-nx-ink" data-testid="code-passage">{c.text.slice(it.passage[0], it.passage[1])}</mark>
              <span className="nx-muted">{c.text.slice(it.passage[1])}</span>
            </>
          ) : c.text}
        </div>
      )}
      <p className="text-caption nx-muted">{it.passage ? t("chat.src.passageUsed") : it.table ? "" : t("chat.src.noPassage")}</p>
      {(c.amended_since?.length ?? 0) > 0 && (
        <p className="rounded-lg bg-nx-pill-yellow-bg px-2 py-1 text-caption text-nx-pill-yellow">
          {t("chat.amendedSince", { count: c.amended_since!.length, date: date.format(new Date(`${c.amended_since![0].passed_on}T12:00:00`)) })}
        </p>
      )}
    </>
  );
}

function formatPin(pin: string): string {
  const d = pin.replace(/\D/g, "");
  return d.length === 14 ? `${d.slice(0, 2)}-${d.slice(2, 4)}-${d.slice(4, 7)}-${d.slice(7, 10)}-${d.slice(10)}` : pin;
}
