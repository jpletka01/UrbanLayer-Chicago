// DotPreview — what a Discovery map dot is (redesign plan §6e, decision Item 57; Q1: the full preview for
// everyone). Address, land use, zoning, lot, the figure the list is sorted by, and "Open profile". Desktop:
// a popover at the dot (hover previews, click pins). Phone: a peek sheet across the bottom of the map.
// It reads the row the list already has, else one row by PIN; until that arrives it shows what the dot
// carries (the land use), never a made-up figure.
import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRight, X } from "lucide-react";
import { Button } from "../components/ui/Button";
import { StatusLabel } from "../components/ui/StatusLabel";
import { rowFigures, rowTitle } from "./rowFigures";
import type { PinPoint, ResultRow } from "./types";

export interface DotPreviewProps {
  point: PinPoint;
  /** The full row, when the list has it or the one-row read returned; null while loading or when it failed. */
  row: ResultRow | null;
  loading: boolean;
  /** A lot outline whose PIN10 has no row (Item 68): "missing" = not in our index, "failed" = the read failed. */
  missing?: "missing" | "failed" | null;
  sortKey: string;
  pinned: boolean;
  onOpen: (pin: string) => void;
  /** Opens the Profile at the point when there is no row to open by PIN. */
  onOpenPoint?: (lat: number, lon: number) => void;
  onClose: () => void;
  variant: "popover" | "sheet";
  style?: CSSProperties;
  onPointerEnter?: () => void;
}

export function DotPreview({
  point, row, loading, missing = null, sortKey, pinned, onOpen, onOpenPoint, onClose, variant, style, onPointerEnter,
}: DotPreviewProps) {
  const { t } = useTranslation("pages");
  const nf = (n: number) => Math.round(n).toLocaleString();
  const { title, approx } = row ? rowTitle(row) : { title: t("discovery.preview.parcel"), approx: false };
  const landUse = row?.land_use ?? point.landUse;
  // The exact district once the index carries it (Item 59), else the zoning family.
  const district = row?.zone_class
    ?? (row?.zoning_group ? t(`discovery.enum.zoning_group.${row.zoning_group}`, { defaultValue: row.zoning_group }) : null);
  const zoning = district
    ? row?.allowed_far != null ? t("discovery.preview.zoningFar", { group: district, far: row.allowed_far }) : district
    : null;
  const figures = row ? rowFigures(row, sortKey, t) : null;
  const lot = row?.lot_sqft != null && figures?.sortKeyShown !== "lot_size" ? t("discovery.lot", { n: nf(row.lot_sqft) }) : null;

  const frame = variant === "sheet"
    ? "absolute inset-x-0 bottom-0 z-30 rounded-t-bento-sm border-t border-dark-border bg-dark-surface px-4 pb-4 pt-2 shadow-modal"
    : "absolute z-30 w-72 rounded-lg border border-dark-border bg-dark-surface p-3 shadow-modal";

  return (
    <div
      role={pinned ? "dialog" : "tooltip"}
      aria-label={title}
      className={frame}
      style={variant === "sheet" ? { paddingBottom: "max(1rem, env(safe-area-inset-bottom))" } : style}
      data-testid="dot-preview"
      data-pin={point.pin}
      onPointerEnter={onPointerEnter}
    >
      {variant === "sheet" && <div aria-hidden className="mx-auto mb-2 h-1 w-10 rounded-full bg-dark-border" />}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            <span className="text-body font-medium text-text-primary">{title}</span>
            {approx && <span title={t("discovery.approxTip")}><StatusLabel tone="neutral" glyph={null}>{t("discovery.approx")}</StatusLabel></span>}
          </div>
          <p className="font-mono text-micro text-text-muted">{t("discovery.pinTitle", { pin: row?.pin ?? point.pin })}</p>
        </div>
        {pinned && (
          <button
            type="button"
            onClick={onClose}
            aria-label={t("discovery.preview.close")}
            className="touch-target -mr-1 -mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-text-muted transition-colors hover:text-link focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <X aria-hidden className="h-4 w-4" strokeWidth={2} />
          </button>
        )}
      </div>
      <p className="mt-1 text-caption text-text-secondary">
        {[landUse ? t(`discovery.enum.land_use.${landUse}`, { defaultValue: landUse.replace(/_/g, " ") }) : null, zoning].filter(Boolean).join(" · ")}
      </p>
      {loading && !row && <p className="mt-2 text-caption text-text-muted">{t("discovery.preview.loading")}</p>}
      {missing && (
        <p className="mt-2 text-caption text-text-secondary" data-testid="dot-preview-missing">
          {t(missing === "missing" ? "discovery.preview.notInData" : "discovery.preview.readFailed")}
        </p>
      )}
      {figures && (
        <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
          {figures.primary && (
            <div>
              <dt className="text-micro text-text-muted">{figures.primaryLabel}</dt>
              <dd className="text-body font-semibold tabular-nums text-text-primary">{figures.primary}</dd>
            </div>
          )}
          {lot && (
            <div>
              <dt className="text-micro text-text-muted">{t("discovery.preview.lot")}</dt>
              <dd className="text-body tabular-nums text-text-primary">{lot}</dd>
            </div>
          )}
          {figures.secondary && (
            <div>
              <dt className="text-micro text-text-muted">{t("discovery.preview.also")}</dt>
              <dd className="text-body tabular-nums text-text-secondary">{figures.secondary}</dd>
            </div>
          )}
        </dl>
      )}
      <Button
        variant="secondary"
        className="mt-3"
        icon={<ArrowRight className="h-4 w-4" strokeWidth={2} />}
        // A row opens by its own PIN (an outline's point holds only the PIN10); no row opens the Profile at the point.
        onClick={() => {
          if (row) onOpen(row.pin);
          else if (missing && onOpenPoint && point.lat != null && point.lon != null) onOpenPoint(point.lat, point.lon);
          else onOpen(point.pin);
        }}
        data-testid="dot-preview-open"
      >
        {t("discovery.preview.open")}
      </Button>
    </div>
  );
}
