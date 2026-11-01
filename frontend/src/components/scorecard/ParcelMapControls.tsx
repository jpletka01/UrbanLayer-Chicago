import type { KeyboardEvent, RefObject } from "react";
import { useTranslation } from "react-i18next";
import type {
  ParcelMapAvailability,
  ParcelMapLayerState,
  ParcelMapSource,
} from "../../lib/parcelMap";

export interface ParcelMapLegendRow {
  key: string;
  label: string;
  swatchCSS: string;
  count: number;
  lowConfidenceCount: number;
  countKind: "district" | "feature";
}

export interface ParcelMapControlSource {
  source: ParcelMapSource;
  label: string;
  availability: ParcelMapAvailability[ParcelMapSource];
  state: ParcelMapLayerState;
  visibleCount: number;
  withheldCount: number;
  rows: ParcelMapLegendRow[];
}

const OPTIONS: ParcelMapLayerState[] = ["on", "dim", "off"];

export function LayerStateControl({
  source,
  sourceLabel,
  value,
  disabled = false,
  onChange,
}: {
  source: ParcelMapSource;
  sourceLabel: string;
  value: ParcelMapLayerState;
  disabled?: boolean;
  onChange: (state: ParcelMapLayerState) => void;
}) {
  const { t } = useTranslation("pages");

  const move = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const key = event.key;
    let next: number | null = null;
    if (key === "ArrowRight" || key === "ArrowDown") next = (index + 1) % OPTIONS.length;
    if (key === "ArrowLeft" || key === "ArrowUp") next = (index + OPTIONS.length - 1) % OPTIONS.length;
    if (key === "Home") next = 0;
    if (key === "End") next = OPTIONS.length - 1;
    if (next == null) return;
    event.preventDefault();
    const option = OPTIONS[next];
    onChange(option);
    const radios = event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("[role=radio]");
    radios?.[next]?.focus();
  };

  return (
    <div
      role="radiogroup"
      aria-label={t("scorecard.map.controlAria", { source: sourceLabel })}
      aria-disabled={disabled || undefined}
      data-source={source}
      className="inline-flex shrink-0 rounded-md border border-dark-border bg-dark-bg/55 p-0.5"
    >
      {OPTIONS.map((option, index) => {
        const selected = value === option;
        return (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(option)}
            onKeyDown={(event) => move(event, index)}
            className={`rounded px-1.5 py-1 text-micro leading-none transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-dark-surface
              disabled:cursor-not-allowed disabled:opacity-45
              ${selected ? "bg-dark-elevated text-text-primary shadow-sm" : "text-text-muted hover:text-text-secondary"}`}
          >
            {t(`scorecard.map.control.${option}`)}
          </button>
        );
      })}
    </div>
  );
}

/** Rows with the parcel's own class first (decision: the key answers "what is my parcel?" before "what else is near"). */
function orderedRows(rows: ParcelMapLegendRow[], subjectKey: string | null | undefined): ParcelMapLegendRow[] {
  if (!subjectKey) return rows;
  const own = rows.filter((row) => row.key === subjectKey);
  return own.length ? [...own, ...rows.filter((row) => row.key !== subjectKey)] : rows;
}

function KeyContents({
  sources,
  subjectKey,
  onChange,
}: {
  sources: ParcelMapControlSource[];
  subjectKey?: string | null;
  onChange: (source: ParcelMapSource, state: ParcelMapLayerState) => void;
}) {
  const { t } = useTranslation("pages");
  return (
    <div className="space-y-3">
      {sources.map((source) => (
        <section key={source.source} data-testid={`parcel-map-source-${source.source}`}>
          <div className="flex min-w-0 items-start justify-between gap-2">
            <h4 className="min-w-0 break-words text-caption font-semibold leading-tight text-text-primary">
              {source.label}
            </h4>
            <LayerStateControl
              source={source.source}
              sourceLabel={source.label}
              value={source.state}
              disabled={source.availability === "unavailable"}
              onChange={(state) => onChange(source.source, state)}
            />
          </div>
          {source.availability === "unavailable" ? (
            <p className="mt-1 text-micro text-state-warning">{t("scorecard.map.sourceUnavailable")}</p>
          ) : (
            <div className="mt-1.5 space-y-1">
              {source.rows.length === 0 && source.withheldCount === 0 && (
                <p className="text-micro text-text-muted">{t("scorecard.map.sourceEmpty")}</p>
              )}
              {orderedRows(source.rows, subjectKey).map((row) => {
                const own = subjectKey != null && row.key === subjectKey;
                return (
                  <div
                    key={row.key}
                    data-subject={own || undefined}
                    className={`flex min-w-0 items-start gap-1.5 text-micro leading-tight ${own ? "font-semibold text-text-primary" : "text-text-secondary"}`}
                  >
                    <span
                      className={`mt-0.5 h-2.5 w-2.5 shrink-0 rounded-[3px] border ${row.lowConfidenceCount > 0 ? "border-dashed" : "border-transparent"}`}
                      style={{ background: row.swatchCSS, borderColor: row.lowConfidenceCount > 0 ? row.swatchCSS : "transparent" }}
                      aria-hidden
                    />
                    <span className="min-w-0 flex-1 break-words">{row.label}</span>
                    {own && <span className="shrink-0 font-normal text-text-muted">{t("scorecard.map.keyParcel")}</span>}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      ))}
      {/* Counts and "not shown" lines live once, in the footer, not on every row (rule §4.8 still holds:
          a withheld feature is never drawn, and the key says how many). */}
      <footer className="space-y-0.5 border-t border-dark-border pt-2 text-micro text-text-muted" data-testid="parcel-map-key-footer">
        {sources.filter((s) => s.availability !== "unavailable" && (s.rows.length > 0 || s.withheldCount > 0)).map((source) => {
          const kind = source.rows[0]?.countKind ?? "feature";
          const count = kind === "district" ? source.rows.length : source.visibleCount;
          return (
            <p key={source.source}>
              {sources.length > 1 ? `${source.label}: ` : ""}
              {t(`scorecard.map.countInView.${kind}`, { count })}
              {source.withheldCount > 0 && (
                <span data-testid={`withheld-count-${source.source}`}>
                  {" · "}{t("scorecard.map.withheldCount", { count: source.withheldCount })}
                </span>
              )}
            </p>
          );
        })}
      </footer>
    </div>
  );
}

/** The collapsed key's one-line label: the parcel's own class (or the first row) plus how many others are in view. */
function keyChipLabel(
  sources: ParcelMapControlSource[],
  subjectKey: string | null | undefined,
  t: (key: string, opts?: Record<string, unknown>) => string,
): string {
  const rows = sources.flatMap((s) => (s.availability === "unavailable" ? [] : s.rows));
  if (rows.length === 0) return t("scorecard.map.keyChipEmpty");
  const first = rows.find((row) => row.key === subjectKey) ?? rows[0];
  const others = rows.length - 1;
  return others > 0
    ? t("scorecard.map.keyChip", { first: first.label, count: others })
    : t("scorecard.map.keyChipOnly", { first: first.label });
}

/**
 * The map key, collapsed by default on every screen size (Jack's 2026-10-31 review: the always-open key covered
 * most of the map). The chip sits on the map; the open key is a column BESIDE the map on desktop (the map narrows,
 * nothing is covered) and a bottom sheet over the map on phones.
 */
export function ParcelMapKeyChip({
  sources,
  subjectKey,
  open,
  onToggle,
  controlsIds,
  buttonRef,
}: {
  sources: ParcelMapControlSource[];
  subjectKey?: string | null;
  open: boolean;
  onToggle: () => void;
  controlsIds: string;
  buttonRef: RefObject<HTMLButtonElement | null>;
}) {
  const { t } = useTranslation("pages");
  return (
    <button
      ref={buttonRef}
      type="button"
      aria-expanded={open}
      aria-controls={controlsIds}
      onClick={onToggle}
      data-testid="parcel-map-layers-button"
      className="absolute right-2 top-2 z-10 inline-flex h-8 max-w-[calc(100%-1rem)] items-center gap-1.5 rounded-lg border border-dark-border bg-dark-surface/95 px-2.5 text-caption font-medium text-text-primary shadow-sm backdrop-blur transition-colors hover:border-dark-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
    >
      <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6.429 9.75 2.25 12l4.179 2.25m0-4.5L12 12.75l5.571-3m-11.142 0L2.25 7.5 12 2.25l9.75 5.25-4.179 2.25m0 0L21.75 12l-4.179 2.25m0 0 4.179 2.25L12 21.75 2.25 16.5l4.179-2.25m11.142 0L12 17.25l-5.571-3" />
      </svg>
      <span className="truncate">{keyChipLabel(sources, subjectKey, t)}</span>
      <span aria-hidden className={`shrink-0 text-text-muted transition-transform ${open ? "rotate-180" : ""}`}>▾</span>
    </button>
  );
}

/** Desktop: the open key as a column beside the map, or under it when the map's box is too narrow to share
 * (a half-width module map would be left a sliver). Hidden below `md`. */
export function ParcelMapKeyPanel({
  id,
  sources,
  subjectKey,
  onChange,
  onClose,
  placement = "side",
}: {
  placement?: "side" | "below";
  id: string;
  sources: ParcelMapControlSource[];
  subjectKey?: string | null;
  onChange: (source: ParcelMapSource, state: ParcelMapLayerState) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation("pages");
  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    onClose();
  };
  return (
    <aside
      id={id}
      aria-label={t("scorecard.map.key")}
      onKeyDown={onKeyDown}
      data-testid="parcel-map-controls-desktop"
      data-placement={placement}
      className={placement === "side"
        ? "relative hidden w-64 shrink-0 border-l border-dark-border bg-dark-surface md:block"
        : "relative hidden border-t border-dark-border bg-dark-surface md:block"}
    >
      <div className={placement === "side" ? "absolute inset-0 overflow-y-auto p-3" : "max-h-72 overflow-y-auto p-3"}>
        <KeyHeader onClose={onClose} />
        <KeyContents sources={sources} subjectKey={subjectKey} onChange={onChange} />
      </div>
    </aside>
  );
}

/** Phone: the open key as a bottom sheet over the map, held above the Mapbox attribution (bottom-left) and below
 * the chip. Hidden from `md` up. */
export function ParcelMapKeySheet({
  id,
  sources,
  subjectKey,
  onChange,
  onClose,
}: {
  id: string;
  sources: ParcelMapControlSource[];
  subjectKey?: string | null;
  onChange: (source: ParcelMapSource, state: ParcelMapLayerState) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation("pages");
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    onClose();
  };
  return (
    <div
      id={id}
      role="dialog"
      aria-label={t("scorecard.map.key")}
      onKeyDown={onKeyDown}
      data-testid="parcel-map-controls-mobile"
      className="absolute inset-x-1 bottom-10 z-20 max-h-[calc(100%-5rem)] overflow-y-auto rounded-xl border border-dark-border bg-dark-surface px-3 pb-3 pt-2 shadow-modal md:hidden"
    >
      <div className="mx-auto mb-2 h-1 w-10 rounded-full bg-dark-border-strong" aria-hidden />
      <KeyHeader onClose={onClose} />
      <KeyContents sources={sources} subjectKey={subjectKey} onChange={onChange} />
    </div>
  );
}

function KeyHeader({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("pages");
  return (
    <div className="mb-2 flex items-center justify-between">
      <span className="text-micro font-semibold uppercase tracking-wider text-text-muted">{t("scorecard.map.key")}</span>
      <button
        type="button"
        onClick={onClose}
        aria-label={t("scorecard.map.keyClose")}
        className="inline-flex h-7 w-7 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-dark-elevated hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <span aria-hidden>✕</span>
      </button>
    </div>
  );
}
