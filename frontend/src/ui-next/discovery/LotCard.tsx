// A Discovery list card (owner's review 2026-11-10; decision Item 104): enough to decide whether to open the Profile.
// A slice of the block colored like the map (this lot outlined), the zoning as a colored tag, the neighborhood and
// what's there now, room to build as the headline with built vs allowed as a bar, then chips for only what applies.
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRight, Bookmark, FileClock, Gift, Hammer, House, Landmark, Receipt, Ruler, Shovel, TrainFront, TriangleAlert, type LucideIcon } from "lucide-react";
import type { ResultRow } from "../../discovery/types";
import { ZONING_COLORS } from "../map/mapStyle";
import { STROKE } from "../icons";
import { Pill, type PillTone } from "../ui/Blocks";
import { contextPaths, fetchLotContext } from "./discoveryData";
import { cardModel, measureSteps, type CardWarning } from "./discoveryModel";
import { lotKey } from "../home/lotMemory";
import type { SaveInput } from "../saved/savedStore";

const ROOM_COLOR: Record<string, string> = Object.fromEntries(measureSteps("room").map((s) => [s.value, s.color]));
const FAMILY_FROM_GROUP: Record<string, keyof typeof ZONING_COLORS> = {
  residential: "residential", business: "business", commercial: "business", manufacturing: "manufacturing",
  downtown: "downtown", planned_development: "planned",
};
const WARNING_ICON: Record<CardWarning["kind"], LucideIcon> = {
  demolition: Hammer, vacant_case: House, pending_rezoning: FileClock, landmark: Landmark, nominal: TriangleAlert,
};

const W = 320;
const H = 96;

/** The block around the lot: neighbors in their room color, this lot in its own with an ink outline. */
function BlockSlice({ pin10, zoneTag, family }: { pin10: string; zoneTag: string | null; family: keyof typeof ZONING_COLORS | null }) {
  const [paths, setPaths] = useState<ReturnType<typeof contextPaths> | null>(null);
  useEffect(() => {
    let live = true;
    fetchLotContext(pin10).then((fc) => { if (live) setPaths(fc ? contextPaths(fc, W, H) : []); });
    return () => { live = false; };
  }, [pin10]);
  const tag = family ? ZONING_COLORS[family] : null;
  return (
    <div className="relative h-24 overflow-hidden rounded-t-2xl bg-nx-ink/[0.04]">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className="h-full w-full" aria-hidden>
        {(paths ?? []).map((p, i) => (
          <path key={i} d={p.d}
            fill={p.r && ROOM_COLOR[p.r] ? ROOM_COLOR[p.r] : "rgb(var(--nx-ink) / 0.06)"}
            fillOpacity={p.me ? 1 : 0.55}
            stroke={p.me ? "rgb(var(--nx-lot))" : "rgb(var(--nx-page))"} strokeWidth={p.me ? 2.5 : 1} strokeLinejoin="round" />
        ))}
      </svg>
      {zoneTag && (
        <span className="absolute left-2 top-2 rounded-md px-1.5 py-0.5 text-[11px] font-semibold text-[#1c1c1c]"
          style={{ background: tag ? tag[1] : "#C9CED6" }}>
          {zoneTag}
        </span>
      )}
    </div>
  );
}

export function LotCard({ row, hoodName, onOpen, moreInComplex = 0, saved, onToggleSave }: {
  row: ResultRow; hoodName: string | null; onOpen: () => void;
  /** Other lots of the same multi-parcel complex in this list, folded into this card. */
  moreInComplex?: number;
  /** Saved (Item 119): whether this lot is saved, and the bookmark's action. No bookmark without it. */
  saved?: boolean;
  onToggleSave?: (lot: SaveInput) => void;
}) {
  const { t, i18n } = useTranslation("next");
  const { t: tp } = useTranslation("pages");
  const n = (v: number) => Math.round(v).toLocaleString(i18n.language.startsWith("es") ? "es-MX" : "en-US");
  const c = cardModel(row);
  const pin10 = row.pin.replace(/-/g, "").slice(0, 10);
  const family = row.zoning_group ? FAMILY_FROM_GROUP[row.zoning_group] ?? null : null;
  const zoneTag = row.zone_class ?? (row.zoning_group ? tp(`discovery.enum.zoning_group.${row.zoning_group}`, { defaultValue: row.zoning_group }) : null);

  // What's there now, in a few words: the use, the year, the size. "Empty" is what stands on the lot (Item 110: the
  // City's footprints and the County's 2022 LiDAR), not the tax class; an index built before it falls back to the class.
  const empty = row.empty_land != null ? row.empty_land === true : row.land_use === "vacant";
  // A parking lot with no building says so (Item 112: the Assessor's 5-90/5-80 with nothing in the footprints or LiDAR).
  const emptyWords = !empty ? null : row.surface_parking ? t("discovery.card.now.surfaceParking")
    : t(`discovery.card.now.emptyKind.${row.land_kind ?? "vacant"}`, { defaultValue: t("discovery.card.now.empty") });
  const use = empty ? (row.structure === "accessory" ? `${emptyWords}, ${t("discovery.card.now.shed")}` : emptyWords)
    : row.land_use && row.land_use !== "vacant" ? t(`discovery.card.now.${row.land_use}`, { defaultValue: row.land_use.replace(/_/g, " ") })
    : null;
  // An empty lot's year built is a demolished building's record: left out.
  const now = [use, row.year_built && !empty ? t("discovery.card.now.built", { year: row.year_built }) : null,
    row.bldg_sqft && !empty ? t("profile.build.sqft", { value: n(row.bldg_sqft) }) : null].filter(Boolean).join(", ");

  // Built vs allowed: the bar behind the headline.
  const allowed = row.allowed_far != null && row.lot_sqft != null ? row.allowed_far * row.lot_sqft : null;
  const built = empty ? 0 : row.bldg_sqft ?? null;
  const used = allowed && built != null && allowed > 0 ? Math.min(1, built / allowed) : null;
  const roomBand = c.roomSqft == null ? null : c.roomSqft <= 0 ? "0" : c.roomSqft < 2500 ? "1" : c.roomSqft < 5000 ? "2" : c.roomSqft < 10000 ? "3" : "4";

  const chips: Array<{ tone: PillTone; icon: LucideIcon; text: string }> = [];
  const walk = row.transit_mi != null ? Math.max(1, Math.round(row.transit_mi * 20)) : null;
  if (walk != null && walk <= 20) chips.push({ tone: "blue", icon: TrainFront, text: t("discovery.card.walk", { minutes: walk }) });
  if (row.in_tif) chips.push({ tone: "green", icon: Gift, text: t("discovery.card.tif") });
  if (row.in_enterprise_zone) chips.push({ tone: "green", icon: Gift, text: t("discovery.card.ez") });
  if (row.is_teardown_candidate) chips.push({ tone: "purple", icon: Shovel, text: t("discovery.card.teardown") });
  if (c.narrowFt != null) chips.push({ tone: "gray", icon: Ruler, text: t("discovery.card.narrow", { ft: c.narrowFt }) });
  // The last sale is a chip like everything else on the card (owner's review); a transfer under $10,000 says so.
  if (c.sale) chips.push({ tone: "gray", icon: Receipt, text: c.sale.transfer
    ? t("discovery.card.transfer", { year: c.sale.year })
    : t("discovery.card.sold", { price: `$${n(c.sale.price)}`, year: c.sale.year }) });
  if (c.warning) chips.push({ tone: c.warning.kind === "nominal" ? "gray" : "yellow", icon: WARNING_ICON[c.warning.kind],
    text: t(`discovery.warning.${c.warning.kind}`, { date: c.warning.detail ?? "", name: c.warning.detail ?? "" }) });

  const pin = row.pin.replace(/-/g, "");
  const saveLot: SaveInput | null = onToggleSave && row.lat != null && row.lon != null ? {
    key: lotKey(pin, ""), pin, address: c.title,
    zone: row.zone_class ?? null, area: hoodName, outline: null, lat: row.lat, lon: row.lon,
  } : null;

  return (
    <li className="relative flex min-w-0">
      {saveLot && (
        <button type="button" onClick={() => onToggleSave!(saveLot)} aria-pressed={!!saved}
          aria-label={saved ? t("home.unsave", { address: saveLot.address }) : t("home.save", { address: saveLot.address })}
          title={saved ? t("home.unsaveShort") : t("home.saveShort")} data-testid="lot-bookmark"
          className={`absolute right-2 top-2 z-10 grid h-8 w-8 place-items-center rounded-lg touch-icon ${saved ? "bg-nx-ink text-nx-on-ink hover:bg-nx-ink/80" : "bg-nx-page hover:bg-nx-ink/5"}`}>
          <Bookmark aria-hidden className="h-4 w-4" strokeWidth={STROKE} fill={saved ? "currentColor" : "none"} />
        </button>
      )}
      <button type="button" onClick={onOpen} data-pin={row.pin}
        className="flex w-full flex-col overflow-hidden rounded-2xl bg-nx-block text-left hover:bg-nx-ink/5">
        <BlockSlice pin10={pin10} zoneTag={zoneTag} family={family} />
        <span className="flex flex-1 flex-col gap-3 p-4">
          <span>
            <span className="block font-semibold [overflow-wrap:anywhere]">{c.approx ? t("discovery.card.near", { address: c.title }) : c.title}</span>
            <span className="block text-caption nx-muted">{[hoodName, now].filter(Boolean).join(" · ")}</span>
          </span>

          <span className="flex flex-col gap-1.5">
            {c.roomSqft != null ? (
              <span className="flex items-baseline gap-1.5">
                <span className="text-[1.375rem] font-semibold leading-none tabular-nums">{t("profile.build.sqft", { value: n(c.roomSqft) })}</span>
                <span className="text-caption nx-muted">{t("discovery.card.roomShort")}</span>
              </span>
            ) : (
              <span className="text-body font-medium">{c.roomNamed ? t(`discovery.card.named.${c.roomNamed}`) : t("discovery.card.roomUnknown")}</span>
            )}
            {used != null && allowed != null && c.complexLots == null && (
              <>
                <span className="flex h-2 overflow-hidden rounded-full bg-nx-ink/10" role="img"
                  aria-label={t("discovery.card.barLabel", { built: n(built ?? 0), allowed: n(allowed), pct: Math.round(used * 100) })}>
                  <span className="bg-nx-ink/40" style={{ width: `${used * 100}%` }} />
                  <span style={{ width: `${(1 - used) * 100}%`, background: roomBand ? ROOM_COLOR[roomBand] : undefined }} />
                </span>
                <span className="flex justify-between text-[11px] nx-muted tabular-nums">
                  <span>{t("discovery.card.built", { value: n(built ?? 0) })}</span>
                  <span>{t("discovery.card.allowed", { value: n(allowed), pct: Math.round(used * 100) })}</span>
                </span>
              </>
            )}
            {c.complexLots != null && (
              <span className="text-caption nx-muted">
                {t("discovery.card.complex", { count: c.complexLots })}
                {moreInComplex > 0 && ` · ${t("discovery.card.moreInComplex", { count: moreInComplex })}`}
              </span>
            )}
            {c.roomBasis && c.complexLots == null && <span className="text-[11px] nx-muted">{t(`discovery.card.basis.${c.roomBasis}`)}</span>}
          </span>

          {chips.length > 0 && (
            <span className="flex flex-wrap gap-1.5">
              {chips.map((ch) => <Pill key={ch.text} tone={ch.tone} icon={ch.icon}>{ch.text}</Pill>)}
            </span>
          )}

          <span className="mt-auto inline-flex items-center gap-1 text-caption underline underline-offset-2">
            {t("discovery.card.open")}<ArrowRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
          </span>
        </span>
      </button>
    </li>
  );
}
