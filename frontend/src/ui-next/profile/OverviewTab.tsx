// Overview tab (brief "Property Profile", Approved; decision Item 76): the answer in one sentence, then one tile
// per tab with its key figure, a small visual and at most one warning. Tiles alternate SnowUI's two pale stat
// colors and reflow from four to two to one.
import { useTranslation } from "react-i18next";
import { ArrowRight, SquareParking, Sprout, TriangleAlert } from "lucide-react";
import type { ScorecardResponse } from "../../lib/api";
import type { ScorecardVerdict } from "../../lib/scorecardVerdict";
import { answerSentence } from "../../lib/answerSentence";
import { ScoreRing } from "../ui/ScoreRing";
import { ConfidenceState } from "../../components/ui/ConfidenceState";
import { ICON, STROKE } from "../icons";
import { Pill } from "../ui/Blocks";
import { overviewTiles, type LotInUse, type Tile, type TileTab } from "./profileModel";
import { Term } from "../ui/Term";

const TILE_ICON = { units: ICON.units, tax: ICON.tax, walk: ICON.walk, lastSale: ICON.sale } as const;

export function OverviewTab({
  data,
  verdict,
  identity,
  checkingCityLists = false,
  buildingPending = false,
  lotInUse = null,
  address = "",
  onOpenTab,
}: {
  data: ScorecardResponse;
  verdict: ScorecardVerdict;
  identity: "exact" | "approximate";
  /** The History part (the City's lists) hasn't answered: the verdict can still gain a caveat (Item 89). */
  checkingCityLists?: boolean;
  /** The City's building records (the `building` part) haven't answered. */
  buildingPending?: boolean;
  /** Surface parking or empty land, measured from what stands on the lot (Item 112); null shows nothing. */
  lotInUse?: LotInUse | null;
  address?: string;
  onOpenTab: (tab: TileTab) => void;
}) {
  const { t, i18n } = useTranslation("next");
  const { t: tp } = useTranslation("pages");
  const tiles = overviewTiles(data, verdict, t, i18n.language, { buildingPending });
  return (
    <div className="flex flex-col gap-7">
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
        <p className="text-nx-answer" data-testid="answer-sentence">{answerSentence(data, verdict, tp)}</p>
        {identity === "approximate" && <Pill tone="yellow" icon={TriangleAlert}>{t("profile.approximate")}</Pill>}
        {lotInUse && identity === "exact" && (
          // What stands on the lot today, in the Discovery card's words; how we know is behind the Info tool.
          <p className="flex w-full items-center gap-2 text-caption" data-testid="lot-in-use">
            {lotInUse.kind === "parking"
              ? <SquareParking aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />
              : <Sprout aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />}
            <Term label={lotInUse.words} definition={t(`profile.lotInUse.define.${lotInUse.kind}`)}
              question={t(`profile.lotInUse.ask.${lotInUse.kind}`, { address })} />
          </p>
        )}
        {checkingCityLists && (
          <p className="w-full text-caption nx-muted" role="status" data-testid="checking-city-lists">{t("profile.parts.cityLists")}</p>
        )}
      </div>
      <ul className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:grid-cols-[repeat(auto-fit,minmax(190px,1fr))] sm:gap-7" data-testid="overview-tiles">
        {tiles.map((tile, i) => <TileCard key={tile.key} tile={tile} alt={i % 2 === 1} onOpenTab={onOpenTab} />)}
      </ul>
    </div>
  );
}

export function TileCard({ tile, alt, onOpenTab }: { tile: Tile; alt: boolean; onOpenTab: (tab: TileTab) => void }) {
  const { t } = useTranslation("next");
  const Icon = TILE_ICON[tile.key];
  const body = (
    <>
      <span className="text-caption nx-card-muted">{t(`profile.tabs.${tile.tabOf}`)}</span>
      <span className="flex items-center gap-2 font-semibold">
        <Icon aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />
        {tile.label}
      </span>
      {tile.score != null ? (
        // A score as a ring on the right, its words on the left (owner's review, Item 102).
        <span className="flex items-center justify-between gap-3">
          <span className="flex min-w-0 flex-col gap-0.5 text-caption">
            <span className="font-semibold">{tile.figure} {tile.unit}</span>
            <span className="nx-card-muted">{tile.note}</span>
          </span>
          <ScoreRing value={tile.score} label={`${tile.label}: ${tile.figure} ${tile.unit ?? ""}`.trim()} testId={`ring-${tile.key}`} />
        </span>
      ) : tile.checking ? (
        // Same height as a figure line, so the tile doesn't grow when the figure arrives.
        <span aria-hidden className="flex items-center text-nx-figure"><span className="block h-[0.8em] w-20 animate-pulse rounded bg-nx-card-ink/10" />&#8203;</span>
      ) : (
        <span className="flex flex-wrap items-baseline gap-x-1.5">
          <span className="text-nx-figure tabular-nums [overflow-wrap:anywhere]">{tile.figure}</span>
          {tile.unit && <span className="text-caption nx-card-muted">{tile.unit}</span>}
        </span>
      )}
      {tile.share != null && (
        <span aria-hidden className="block h-1.5 overflow-hidden rounded bg-nx-card-ink/10">
          <span className="block h-full rounded bg-nx-card-ink" style={{ width: `${tile.share * 100}%` }} />
        </span>
      )}
      {tile.note && tile.score == null && <span className="text-caption nx-card-muted">{tile.note}</span>}
      {tile.warning && (
        <span className="flex items-center gap-1 text-caption font-medium">
          <TriangleAlert aria-hidden className="h-3.5 w-3.5 shrink-0" strokeWidth={2} />
          {tile.warning}
        </span>
      )}
      {/* The state label and, on a tile that opens its tab, the "Open …" link share one row (owner, 2026-11-08):
          the link on its own line made every tile in the row taller. */}
      {(tile.state || tile.tab) && (
        <span className="mt-auto flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          {tile.state ? (
            <span className="nx-on-card inline-flex">
              <ConfidenceState kind={tile.state.kind} low={tile.state.low} />
            </span>
          ) : <span />}
          {tile.tab && (
            <span id={`tile-go-${tile.key}`} className="inline-flex items-center gap-1 text-caption underline underline-offset-2">
              {t("profile.tiles.open", { tab: t(`profile.tabs.${tile.tab}`) })}
              <ArrowRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
            </span>
          )}
        </span>
      )}
    </>
  );
  const cls = `flex h-full w-full flex-col gap-2 rounded-2xl p-4 text-left text-nx-card-ink sm:p-6 ${alt ? "bg-nx-stat-b" : "bg-nx-stat-a"}`;
  return (
    <li className="flex min-w-0 flex-col" data-tile={tile.key}>
      {tile.tab ? (
        <button type="button" onClick={() => onOpenTab(tile.tab!)} className={`${cls} group hover:brightness-[0.97]`} aria-describedby={`tile-go-${tile.key}`}>
          {body}
        </button>
      ) : (
        <div className={cls}>{body}</div>
      )}
    </li>
  );
}
