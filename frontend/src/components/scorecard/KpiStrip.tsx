// KPI strip — the Property Profile's level-1 numbers row. Six stat tiles, each
// value + context line, deep-linking to the module that holds its evidence.
// De-carded: no boxes; the tiles read as one row of figures over the canvas.
// (Benchmark deltas — "vs area median" — arrive with the CA-aggregate endpoint;
// the sub line is the context slot they will occupy.)
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { InfoTooltip } from "../InfoTooltip";

export interface KpiTile {
  anchor: string;
  label: string;
  value: string;
  sub?: ReactNode;
  /** How-this-is-computed gloss, shown on hover/tap (tooltip rule). */
  tip?: string;
}

export function KpiStrip({ tiles, onScrollTo }: {
  tiles: KpiTile[];
  onScrollTo: (anchor: string) => void;
}) {
  const { t } = useTranslation("pages");
  if (tiles.length < 2) return null;
  // Columns track the tile count so the band fills its row evenly — a fixed
  // 6-col grid left dead columns when only 4 tiles had data (looked off-center).
  const cols = tiles.length <= 4
    ? "grid-cols-2 md:grid-cols-4"
    : "grid-cols-2 md:grid-cols-3 xl:grid-cols-5";
  return (
    // Tiles center within their columns — left-aligned content in stretched
    // cells piled all the whitespace on the right (read as off-center).
    <div className={`grid ${cols} gap-x-8 gap-y-5 py-5 border-y border-dark-border mb-6 text-center`}>
      {tiles.map((tile) => (
        <div key={tile.anchor + tile.label} className="min-w-0">
          <div className="text-overline uppercase tracking-wider text-text-muted">
            {tile.tip ? (
              <InfoTooltip content={{ label: tile.label, description: tile.tip, bullets: [] }}>
                {tile.label}
              </InfoTooltip>
            ) : (
              tile.label
            )}
          </div>
          <button
            type="button"
            onClick={() => onScrollTo(tile.anchor)}
            title={t("scorecard.verdict.jumpToEvidence")}
            className="group block mx-auto min-w-0 max-w-full"
          >
            <div className="text-stat text-text-primary mt-1 truncate group-hover:text-accent transition-colors">
              {tile.value}
            </div>
          </button>
          {tile.sub && (
            <div className="text-caption text-text-muted mt-0.5 leading-snug">{tile.sub}</div>
          )}
        </div>
      ))}
    </div>
  );
}
