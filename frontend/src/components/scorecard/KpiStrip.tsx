// KPI strip — the Property Profile's level-1 numbers row. Six stat tiles, each
// value + context line, deep-linking to the module that holds its evidence.
// De-carded: no boxes; the tiles read as one row of figures over the canvas.
// (Benchmark deltas — "vs area median" — arrive with the CA-aggregate endpoint;
// the sub line is the context slot they will occupy.)
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

export interface KpiTile {
  anchor: string;
  label: string;
  value: string;
  sub?: ReactNode;
}

export function KpiStrip({ tiles, onScrollTo }: {
  tiles: KpiTile[];
  onScrollTo: (anchor: string) => void;
}) {
  const { t } = useTranslation("pages");
  if (tiles.length < 2) return null;
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-x-6 gap-y-5 py-5 border-y border-dark-border mb-6">
      {tiles.map((tile) => (
        <button
          key={tile.anchor + tile.label}
          type="button"
          onClick={() => onScrollTo(tile.anchor)}
          title={t("scorecard.verdict.jumpToEvidence")}
          className="group text-left min-w-0"
        >
          <div className="text-overline uppercase tracking-wider text-text-muted">{tile.label}</div>
          <div className="text-stat text-text-primary mt-1 truncate group-hover:text-accent transition-colors">
            {tile.value}
          </div>
          {tile.sub && (
            <div className="text-caption text-text-muted mt-0.5 leading-snug">{tile.sub}</div>
          )}
        </button>
      ))}
    </div>
  );
}
