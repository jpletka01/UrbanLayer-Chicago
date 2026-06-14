// Results panel (PR5): result count, diagnostics affordances (broad / dropped / conflict),
// a three-way zero state sourced from the PR4 coverage/populatedFields selectors, and an
// infinite-scroll list of hydrated row-cards that hand off to the Scorecard.
//
// The list is list-ONLY: the map (PR6) fetches the full coord set separately, so this never
// owns the map's data. CSV export is deliberately NOT here — it is full-match + server-side
// + premium-gated (PR7 /search/export + PR9 gate); never assembled from this rows window.

import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { caName, NEIGHBORHOOD_PREFIX } from "./communityAreas";
import { coverageOf, isPopulated } from "./coverage";
import { summarize } from "./summary";
import type { Registry, ResultRow, SearchResponse } from "./types";

function humanize(s: string): string {
  return s.replace(/_/g, " ");
}

function filterLabel(registry: Registry, id: string): string {
  const def = registry.filters.find((f) => f.id === id);
  return def?.label ?? humanize(id);
}

function fmtMoney(n: number | null): string | null {
  return n == null ? null : `$${Math.round(n).toLocaleString()}`;
}

function fmtNum(n: number | null): string | null {
  return n == null ? null : Math.round(n).toLocaleString();
}

interface ResultsProps {
  response: SearchResponse | null;
  rows: ResultRow[]; // accumulated window (page 0 + appended), deduped by pin
  registry: Registry;
  loading: boolean; // initial search
  loadingMore: boolean; // appending a later page
  hasMore: boolean;
  onLoadMore: () => void;
  onRelax: (filterId: string) => void;
  onOpenParcel: (pin: string) => void;
  hoveredPin?: string | null; // bidirectional hover sync with the map
  onHoverPin?: (pin: string | null) => void;
  onExport?: () => void; // full-match-set CSV (server-side, premium)
  exportLocked?: boolean; // free tier — show the Export button as a Pro conversion lever
  onUpgrade?: () => void; // teaser CTA + locked-export click
}

export function DiscoveryResults({
  response,
  rows,
  registry,
  loading,
  loadingMore,
  hasMore,
  onLoadMore,
  onRelax,
  onOpenParcel,
  hoveredPin = null,
  onHoverPin,
  onExport,
  exportLocked = false,
  onUpgrade,
}: ResultsProps) {
  const { t } = useTranslation("pages");
  if (loading) {
    return <p className="p-4 text-sm text-text-muted">Searching…</p>;
  }
  if (!response) {
    return <p className="p-4 text-sm text-text-muted">Set filters and run a search.</p>;
  }

  const { result, diagnostics } = response;
  const activeSortKey = response.cqs.sort.key;
  const excludedTotal = Object.values(diagnostics.excludedUnknown).reduce((a, b) => a + b, 0);

  return (
    <div className="flex h-full flex-col">
      <div className="flex-shrink-0 space-y-2 border-b border-dark-border p-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm text-text-primary">
            <span className="font-semibold">{result.total.toLocaleString()}</span>{" "}
            {result.total === 1 ? "parcel" : "parcels"}
          </p>
          {result.total > 0 && (exportLocked ? onUpgrade : onExport) && (
            <button
              type="button"
              onClick={exportLocked ? onUpgrade : onExport}
              className="inline-flex items-center gap-1 text-[11px] text-accent transition-colors hover:text-accent/80"
            >
              {exportLocked ? (
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              ) : (
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
              )}
              {exportLocked ? t("discovery.exportPro") : t("discovery.exportCsv")}
            </button>
          )}
        </div>

        {diagnostics.droppedInvalid.length > 0 && (
          <p className="text-[11px] text-amber-400/80">
            Ignored:{" "}
            {diagnostics.droppedInvalid
              .map((d) => `${filterLabel(registry, d.filterId)} (${d.reason})`)
              .join(", ")}
          </p>
        )}

        {diagnostics.conflicts.map((c) => (
          <div key={c.filters.join("|")} className="text-[11px] text-amber-400/80">
            {c.filters.map((f) => filterLabel(registry, f)).join(" conflicts with ")} —{" "}
            {c.filters.map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => onRelax(f)}
                className="underline transition-colors hover:text-accent"
              >
                remove {filterLabel(registry, f)}
              </button>
            ))}
          </div>
        ))}

        {result.total === 0 && <ZeroState response={response} registry={registry} onRelax={onRelax} />}

        {result.total > 0 && diagnostics.broad && (
          <p className="text-[11px] text-text-muted">Broad search — add filters to narrow.</p>
        )}
        {excludedTotal > 0 && (
          <p className="text-[11px] text-text-muted">
            {excludedTotal.toLocaleString()} excluded for missing data.
          </p>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {rows.map((row) => (
          <ResultCard
            key={row.pin}
            row={row}
            activeSortKey={activeSortKey}
            hovered={hoveredPin === row.pin}
            onHoverPin={onHoverPin}
            onOpenParcel={onOpenParcel}
          />
        ))}
        <InfiniteScrollSentinel hasMore={hasMore} loadingMore={loadingMore} onLoadMore={onLoadMore} />
        {!hasMore && rows.length > 0 && result.gated && result.total > rows.length ? (
          <TeaserWall
            total={result.total}
            shown={rows.length}
            summary={summarize(response.cqs, registry)}
            onUpgrade={onUpgrade}
            t={t}
          />
        ) : (
          !hasMore &&
          rows.length > 0 && (
            <p className="px-4 py-3 text-[11px] text-text-muted">
              Showing all {rows.length.toLocaleString()}.
            </p>
          )
        )}
      </div>
    </div>
  );
}

/**
 * Three distinct zero states (PR4-aware), in priority order:
 *  1. A filter is set whose field has no data in this dataset yet (NULL-backed).
 *  2. The query is scoped to community areas that aren't indexed yet (non-live).
 *  3. Otherwise the filters are simply too tight → offer the most-restrictive removals.
 */
function ZeroState({
  response,
  registry,
  onRelax,
}: {
  response: SearchResponse;
  registry: Registry;
  onRelax: (filterId: string) => void;
}) {
  const filterIds = Object.keys(response.cqs.filters);

  // (1) NULL-backed: filters set on fields the index hasn't populated.
  const nullBacked = filterIds.filter((id) => !isPopulated(registry, id));
  if (nullBacked.length > 0) {
    return (
      <div className="space-y-1 text-[11px] text-text-muted">
        <p>
          No matches — {nullBacked.length === 1 ? "the" : ""}{" "}
          <span className="text-text-secondary">
            {nullBacked.map((id) => filterLabel(registry, id)).join(", ")}
          </span>{" "}
          {nullBacked.length === 1 ? "filter has" : "filters have"} no data in this dataset yet.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {nullBacked.map((id) => (
            <RelaxChip key={id} label={filterLabel(registry, id)} onClick={() => onRelax(id)} />
          ))}
        </div>
      </div>
    );
  }

  // (2) Non-live area: a neighborhood filter selecting only un-indexed community areas.
  const coverage = coverageOf(registry);
  const nb = response.cqs.filters["neighborhood"]?.predicate;
  if (coverage.mode === "partial" && nb?.kind === "region") {
    const selected = nb.regions
      .filter((r) => r.startsWith(NEIGHBORHOOD_PREFIX))
      .map((r) => Number(r.replace(NEIGHBORHOOD_PREFIX, "")));
    const live = new Set(coverage.liveAreas);
    const offCoverage = selected.filter((id) => !live.has(id));
    if (selected.length > 0 && offCoverage.length === selected.length) {
      const names = offCoverage.map((id) => caName(`${NEIGHBORHOOD_PREFIX}${id}`)).join(", ");
      return (
        <p className="text-[11px] text-text-muted">
          No matches — <span className="text-text-secondary">{names}</span>{" "}
          {offCoverage.length === 1 ? "isn't" : "aren't"} indexed yet. Indexed area:{" "}
          {coverage.liveAreas.map((id) => caName(`${NEIGHBORHOOD_PREFIX}${id}`)).join(", ")}.
        </p>
      );
    }
  }

  // (3) Too tight: offer the most-restrictive removals (06 diagnostics).
  const removable = response.diagnostics.mostRestrictive.filter((m) => m.countWithoutIt > 0);
  return (
    <div className="space-y-1">
      <p className="text-[11px] text-text-muted">No matches. Try removing:</p>
      {removable.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {removable.map((m) => (
            <RelaxChip
              key={m.filterId}
              label={`${filterLabel(registry, m.filterId)} (+${m.countWithoutIt.toLocaleString()})`}
              onClick={() => onRelax(m.filterId)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function RelaxChip({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md border border-dark-border px-2 py-0.5 text-[11px] text-text-secondary transition-colors hover:border-accent hover:text-accent"
    >
      {label}
    </button>
  );
}

function InfiniteScrollSentinel({
  hasMore,
  loadingMore,
  onLoadMore,
}: {
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = ref.current;
    // Guard typeof for jsdom (no IntersectionObserver); only observe when more to fetch.
    if (!el || !hasMore || typeof IntersectionObserver === "undefined") return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loadingMore) onLoadMore();
      },
      { rootMargin: "200px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [hasMore, loadingMore, onLoadMore]);

  if (!hasMore) return null;
  return (
    <div ref={ref} className="px-4 py-3 text-[11px] text-text-muted">
      {loadingMore ? "Loading more…" : "Scroll for more"}
    </div>
  );
}

// Free-tier teaser (PR9): the query-aware conversion wall over the "N more match" region.
// The 10 shown rows above are real (with scores); this gates the full ranked list + map
// intelligence + refine + export. Copy is built from the canonical CQS via summarize().
function TeaserWall({
  total,
  shown,
  summary,
  onUpgrade,
  t,
}: {
  total: number;
  shown: number;
  summary: string;
  onUpgrade?: () => void;
  t: (key: string, opts?: Record<string, unknown>) => string;
}) {
  return (
    <div className="border-t border-dark-border bg-dark-elevated/40 px-4 py-4 text-center backdrop-blur-[1px]">
      <p className="text-sm font-medium text-text-primary">
        {t("discovery.teaserCount", { total: total.toLocaleString(), shown })}
      </p>
      <p className="mx-auto mt-1 max-w-xs text-[11px] text-text-muted">{summary}</p>
      <p className="mx-auto mt-1 max-w-xs text-[11px] text-text-secondary">
        {t("discovery.teaserUnlock")}
      </p>
      {onUpgrade && (
        <button
          type="button"
          onClick={onUpgrade}
          className="mt-3 rounded-lg bg-accent px-4 py-2 text-xs font-medium text-white transition-opacity hover:opacity-90"
        >
          {t("discovery.unlockCta")}
        </button>
      )}
    </div>
  );
}

function ResultCard({
  row,
  activeSortKey,
  hovered,
  onHoverPin,
  onOpenParcel,
}: {
  row: ResultRow;
  activeSortKey: string;
  hovered: boolean;
  onHoverPin?: (pin: string | null) => void;
  onOpenParcel: (pin: string) => void;
}) {
  const title = row.address ?? row.pin;
  const useLine = [
    row.land_use ? humanize(row.land_use) : null,
    row.class,
    row.units != null ? `${row.units} units` : null,
  ].filter(Boolean);
  const sizeLine = [
    row.lot_sqft != null ? `Lot ${fmtNum(row.lot_sqft)}` : null,
    row.bldg_sqft != null ? `Bldg ${fmtNum(row.bldg_sqft)} sf` : null,
    row.year_built != null ? String(row.year_built) : null,
  ].filter(Boolean);

  // Surface "what you sorted by": bold assessed value when sorting by it, else $/sqft.
  const sortIsAssessed = activeSortKey === "assessed_value";
  const assessed = fmtMoney(row.assessed_value);
  const ppsf = row.price_per_sf != null ? `${fmtMoney(row.price_per_sf)}/sqft` : null;

  return (
    <button
      type="button"
      onClick={() => onOpenParcel(row.pin)}
      onMouseEnter={() => onHoverPin?.(row.pin)}
      onMouseLeave={() => onHoverPin?.(null)}
      className={`block w-full border-b border-dark-border px-4 py-2.5 text-left transition-colors ${
        hovered ? "bg-dark-elevated" : "hover:bg-dark-elevated"
      }`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="truncate text-sm text-text-primary">{title}</span>
        {row.upside_score != null && (
          <span className="flex-shrink-0 text-[11px] text-accent">
            ● Upside {Math.round(row.upside_score)}
          </span>
        )}
      </div>
      {/* PIN demoted to a mono subtitle (shown when an address is the title). */}
      {row.address && <div className="font-mono text-[10px] text-text-muted">{row.pin}</div>}
      {useLine.length > 0 && (
        <div className="mt-0.5 text-[11px] text-text-secondary">{useLine.join(" · ")}</div>
      )}
      {sizeLine.length > 0 && (
        <div className="text-[11px] text-text-muted">{sizeLine.join(" · ")}</div>
      )}
      {(assessed || ppsf) && (
        <div className="text-[11px] text-text-muted">
          {assessed && (
            <span className={sortIsAssessed ? "font-semibold text-text-secondary" : undefined}>
              AV {assessed}
            </span>
          )}
          {assessed && ppsf ? " · " : null}
          {ppsf && (
            <span className={!sortIsAssessed ? "font-semibold text-text-secondary" : undefined}>
              {ppsf}
            </span>
          )}
        </div>
      )}
    </button>
  );
}
