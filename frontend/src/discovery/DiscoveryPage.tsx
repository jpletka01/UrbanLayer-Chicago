// Property Discovery page (08/09). Owns the raw inputs (panel state, free text, sort), runs
// the search, and renders summary + chips + results FROM response.cqs (INV-4). Premium-gated
// like the Site Explorer. The page never evaluates or filters — that is the backend's job.

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthContext } from "../contexts/AuthContext";
import PageHeader from "./../components/PageHeader";
import UpgradePrompt from "./../components/UpgradePrompt";
import { Chips } from "./chips";
import { CoverageBanner } from "./CoverageBanner";
import { DiscoveryFilterPanel } from "./DiscoveryFilterPanel";
import { DiscoveryResults } from "./DiscoveryResults";
import { loadRegistry } from "./registryClient";
import { runSearch } from "./searchClient";
import { summarize } from "./summary";
import type { PanelState, Predicate, Registry, SearchResponse, SortSpec } from "./types";

export default function DiscoveryPage() {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const isPro = user?.tier === "premium" || user?.tier === "admin";

  const [registry, setRegistry] = useState<Registry | null>(null);
  const [panelState, setPanelState] = useState<PanelState>({});
  const [text, setText] = useState("");
  const [sort, setSort] = useState<SortSpec | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [showUpgrade, setShowUpgrade] = useState(false);

  useEffect(() => {
    loadRegistry().then((reg) => {
      setRegistry(reg);
      if (reg) setSort(reg.defaultSort);
    });
  }, []);

  const runWith = useCallback(
    async (state: PanelState, txt: string, srt: SortSpec | null) => {
      if (!registry) return;
      if (!isPro) {
        setShowUpgrade(true);
        return;
      }
      setLoading(true);
      const resp = await runSearch({ panelState: state, text: txt, sort: srt }, registry);
      setResponse(resp);
      setLoading(false);
    },
    [registry, isPro],
  );

  const onPanelChange = useCallback((id: string, predicate: Predicate | null) => {
    setPanelState((prev) => {
      const next = { ...prev };
      if (predicate === null) delete next[id];
      else next[id] = predicate;
      return next;
    });
  }, []);

  // One-tap re-issue (06): fold the evaluated CQS back into the panel (so text-derived
  // constraints persist + stay editable), drop the chosen filter, and re-search.
  const onRelax = useCallback(
    (filterId: string) => {
      if (!response) return;
      const next: PanelState = {};
      for (const [fid, a] of Object.entries(response.cqs.filters)) {
        if (fid !== filterId) next[fid] = a.predicate;
      }
      setPanelState(next);
      setText("");
      runWith(next, "", sort);
    },
    [response, sort, runWith],
  );

  const onOpenParcel = useCallback(
    (pin: string) => navigate(`/scorecard?pin=${pin.replace(/\D/g, "")}`),
    [navigate],
  );

  return (
    <div className="flex h-screen flex-col bg-dark-bg text-text-primary">
      <PageHeader sticky={false} maxWidthClass="max-w-[1920px]" />

      {registry && <CoverageBanner registry={registry} />}

      <div className="flex flex-1 flex-col overflow-hidden md:flex-row">
        {/* Left: inputs */}
        <div className="flex w-full flex-shrink-0 flex-col overflow-hidden border-r border-dark-border md:w-[420px] lg:w-[460px]">
          <div className="flex-shrink-0 space-y-3 border-b border-dark-border p-4">
            <div>
              <h1 className="text-lg font-semibold tracking-tight">Property Discovery</h1>
              <p className="text-[11px] text-text-muted">
                Filter Chicago parcels by use, zoning, incentives, and more.
              </p>
            </div>
            <input
              type="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") runWith(panelState, text, sort);
              }}
              placeholder='Try "vacant multifamily in a tif zone, built after 1990"'
              className="w-full rounded-lg border border-dark-border bg-dark-elevated px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
            />
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => runWith(panelState, text, sort)}
                disabled={!registry || loading}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {loading ? "Searching…" : "Search"}
              </button>
              {registry && sort && (
                <SortControl registry={registry} sort={sort} onChange={setSort} />
              )}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {registry ? (
              <DiscoveryFilterPanel registry={registry} state={panelState} onChange={onPanelChange} />
            ) : (
              <p className="text-sm text-text-muted">Loading filters…</p>
            )}
          </div>
        </div>

        {/* Right: summary + chips + results */}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {response && registry && (
            <div className="flex-shrink-0 space-y-2 border-b border-dark-border p-4">
              <p className="text-sm text-text-secondary">{summarize(response.cqs, registry)}</p>
              <Chips cqs={response.cqs} registry={registry} onRemove={onRelax} />
            </div>
          )}
          <div className="min-h-0 flex-1">
            {registry && (
              <DiscoveryResults
                response={response}
                loading={loading}
                registry={registry}
                onRelax={onRelax}
                onOpenParcel={onOpenParcel}
              />
            )}
          </div>
        </div>
      </div>

      {showUpgrade && (
        <UpgradePrompt feature="Property Discovery" onClose={() => setShowUpgrade(false)} />
      )}
    </div>
  );
}

function SortControl({
  registry,
  sort,
  onChange,
}: {
  registry: Registry;
  sort: SortSpec;
  onChange: (s: SortSpec) => void;
}) {
  return (
    <div className="flex items-center gap-1.5 text-xs">
      <select
        value={sort.key}
        onChange={(e) => onChange({ ...sort, key: e.target.value })}
        className="rounded-md border border-dark-border bg-dark-elevated px-2 py-1.5 text-text-primary focus:border-accent focus:outline-none"
      >
        {registry.sortKeys.map((sk) => (
          <option key={sk.key} value={sk.key}>
            {sk.key.replace(/_/g, " ")}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={() => onChange({ ...sort, dir: sort.dir === "asc" ? "desc" : "asc" })}
        className="rounded-md border border-dark-border px-2 py-1.5 text-text-secondary transition-colors hover:border-text-muted"
        aria-label="Toggle sort direction"
      >
        {sort.dir === "asc" ? "↑" : "↓"}
      </button>
    </div>
  );
}
