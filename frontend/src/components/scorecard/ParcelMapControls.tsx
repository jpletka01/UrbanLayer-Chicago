import { useId, useRef, useState, type KeyboardEvent } from "react";
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

function ControlContents({
  sources,
  onChange,
}: {
  sources: ParcelMapControlSource[];
  onChange: (source: ParcelMapSource, state: ParcelMapLayerState) => void;
}) {
  const { t } = useTranslation("pages");
  return (
    <div className="space-y-2.5">
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
            <div className="mt-1 space-y-1">
              {source.rows.length === 0 && source.withheldCount === 0 && (
                <p className="text-micro text-text-muted">{t("scorecard.map.sourceEmpty")}</p>
              )}
              {source.rows.map((row) => (
                <div key={row.key} className="flex min-w-0 items-start gap-1.5 text-micro leading-tight text-text-secondary">
                  <span
                    className={`mt-0.5 h-2.5 w-2.5 shrink-0 rounded-[3px] border ${row.lowConfidenceCount > 0 ? "border-dashed" : "border-transparent"}`}
                    style={{ background: row.swatchCSS, borderColor: row.lowConfidenceCount > 0 ? row.swatchCSS : "transparent" }}
                    aria-hidden
                  />
                  <span className="min-w-0 flex-1 break-words">{row.label}</span>
                  <span className="shrink-0 text-text-muted">
                    {t(`scorecard.map.count.${row.countKind}`, { count: row.count })}
                  </span>
                </div>
              ))}
              {source.withheldCount > 0 && (
                <p className="text-micro text-text-muted" data-testid={`withheld-count-${source.source}`}>
                  {t("scorecard.map.withheldCount", { count: source.withheldCount })}
                </p>
              )}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}

export function ParcelMapControls({
  sources,
  onChange,
}: {
  sources: ParcelMapControlSource[];
  onChange: (source: ParcelMapSource, state: ParcelMapLayerState) => void;
}) {
  const { t } = useTranslation("pages");
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const popoverId = useId();

  const onPopoverKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    setOpen(false);
    buttonRef.current?.focus();
  };

  return (
    <>
      <aside
        aria-label={t("scorecard.map.layers")}
        data-testid="parcel-map-controls-desktop"
        className="absolute right-2 top-2 z-10 hidden max-h-[calc(100%-1rem)] w-[22rem] max-w-[65%] overflow-y-auto rounded-lg border border-dark-border bg-dark-surface/92 p-2.5 shadow-card backdrop-blur md:block"
      >
        <div className="mb-2 text-micro font-semibold uppercase tracking-wider text-text-muted">
          {t("scorecard.map.layers")}
        </div>
        <ControlContents sources={sources} onChange={onChange} />
      </aside>

      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={popoverId}
        onClick={() => setOpen((value) => !value)}
        data-testid="parcel-map-layers-button"
        className="absolute right-2 top-2 z-10 inline-flex items-center gap-1.5 rounded-md border border-dark-border bg-dark-surface/92 px-2.5 py-1.5 text-caption font-medium text-text-primary shadow-sm backdrop-blur transition-colors hover:border-dark-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent md:hidden"
      >
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6.429 9.75 2.25 12l4.179 2.25m0-4.5L12 12.75l5.571-3m-11.142 0L2.25 7.5 12 2.25l9.75 5.25-4.179 2.25m0 0L21.75 12l-4.179 2.25m0 0 4.179 2.25L12 21.75 2.25 16.5l4.179-2.25m11.142 0L12 17.25l-5.571-3" />
        </svg>
        {t("scorecard.map.layers")}
      </button>

      {open && (
        <div
          id={popoverId}
          role="dialog"
          aria-label={t("scorecard.map.layers")}
          onKeyDown={onPopoverKeyDown}
          data-testid="parcel-map-controls-mobile"
          className="absolute right-2 top-11 z-20 max-h-[calc(100%-6.5rem)] w-[calc(100%-1rem)] max-w-[18rem] overflow-y-auto rounded-xl border border-dark-border bg-dark-surface/97 p-3 shadow-modal backdrop-blur md:hidden"
        >
          <ControlContents sources={sources} onChange={onChange} />
        </div>
      )}
    </>
  );
}
