// KPI strip — the Property Profile's level-1 numbers row: stat tiles, each
// value + context line, deep-linking to the module that holds its evidence.
// One contained card with hairline-divided cells (the classic dashboard
// stat-row widget) — the band needs figure-ground, not free-floating figures.
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
  // Hairline cell dividers only when md+ guarantees a single row (≤4 tiles);
  // a wrapped grid would put stray borders at row starts.
  const single = tiles.length <= 4;
  const cols = single
    ? "grid-cols-2 gap-y-6 gap-x-6 md:gap-0 md:grid-cols-4 md:divide-x md:divide-dark-border"
    : "grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-x-8 gap-y-6";
  return (
    // Tiles center within their columns — left-aligned content in stretched
    // cells piled all the whitespace on the right (read as off-center).
    <div className={`grid ${cols} rounded-bento border border-dark-border bg-dark-surface shadow-card px-5 md:px-2 py-6 mb-6 text-center`}>
      {tiles.map((tile) => (
        <div key={tile.anchor + tile.label} className={`min-w-0 ${single ? "md:px-6" : ""}`}>
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
