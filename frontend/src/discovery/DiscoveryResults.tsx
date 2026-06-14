// Results panel (08): result count, diagnostics affordances (broad / dropped / conflict /
// zero-result mostRestrictive — all driving one-tap re-issue, 06), and a capped list of
// result PINs that hand off to the Scorecard. The frozen contract returns PINs only, so
// this is list-first; map markers are a deferred follow-up.

import type { Registry, SearchResponse } from "./types";

const RENDER_CAP = 100;

function humanize(s: string): string {
  return s.replace(/_/g, " ");
}

interface ResultsProps {
  response: SearchResponse | null;
  loading: boolean;
  registry: Registry;
  onRelax: (filterId: string) => void;
  onOpenParcel: (pin: string) => void;
}

export function DiscoveryResults({ response, loading, onRelax, onOpenParcel }: ResultsProps) {
  if (loading) {
    return <p className="p-4 text-sm text-text-muted">Searching…</p>;
  }
  if (!response) {
    return <p className="p-4 text-sm text-text-muted">Set filters and run a search.</p>;
  }

  const { result, diagnostics } = response;
  const shown = result.pins.slice(0, RENDER_CAP);
  const excludedTotal = Object.values(diagnostics.excludedUnknown).reduce((a, b) => a + b, 0);

  return (
    <div className="flex h-full flex-col">
      <div className="flex-shrink-0 space-y-2 border-b border-dark-border p-4">
        <p className="text-sm text-text-primary">
          <span className="font-semibold">{result.total.toLocaleString()}</span>{" "}
          {result.total === 1 ? "parcel" : "parcels"}
        </p>

        {diagnostics.droppedInvalid.length > 0 && (
          <p className="text-[11px] text-amber-400/80">
            Ignored:{" "}
            {diagnostics.droppedInvalid.map((d) => `${humanize(d.filterId)} (${d.reason})`).join(", ")}
          </p>
        )}

        {diagnostics.conflicts.map((c) => (
          <div key={c.filters.join("|")} className="text-[11px] text-amber-400/80">
            {c.filters.map(humanize).join(" conflicts with ")} —{" "}
            {c.filters.map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => onRelax(f)}
                className="underline transition-colors hover:text-accent"
              >
                remove {humanize(f)}
              </button>
            ))}
          </div>
        ))}

        {result.total === 0 && diagnostics.mostRestrictive.length > 0 && (
          <div className="space-y-1">
            <p className="text-[11px] text-text-muted">No matches. Try removing:</p>
            <div className="flex flex-wrap gap-1.5">
              {diagnostics.mostRestrictive
                .filter((m) => m.countWithoutIt > 0)
                .map((m) => (
                  <button
                    key={m.filterId}
                    type="button"
                    onClick={() => onRelax(m.filterId)}
                    className="rounded-md border border-dark-border px-2 py-0.5 text-[11px] text-text-secondary transition-colors hover:border-accent hover:text-accent"
                  >
                    {humanize(m.filterId)} (+{m.countWithoutIt.toLocaleString()})
                  </button>
                ))}
            </div>
          </div>
        )}

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
        {shown.map((pin) => (
          <button
            key={pin}
            type="button"
            onClick={() => onOpenParcel(pin)}
            className="flex w-full items-center justify-between border-b border-dark-border px-4 py-2 text-left text-sm transition-colors hover:bg-dark-elevated"
          >
            <span className="font-mono text-text-primary">{pin}</span>
            <span className="text-[11px] text-accent">View Scorecard →</span>
          </button>
        ))}
        {result.total > shown.length && (
          <p className="px-4 py-3 text-[11px] text-text-muted">
            Showing {shown.length} of {result.total.toLocaleString()}.
          </p>
        )}
      </div>
    </div>
  );
}
