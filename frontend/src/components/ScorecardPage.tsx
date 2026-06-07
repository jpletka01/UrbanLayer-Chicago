import { useState, useCallback, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchScorecard, fetchReport, type ScorecardResponse } from "../lib/api";
import { useAuthContext } from "../contexts/AuthContext";
import UpgradePrompt from "./UpgradePrompt";
import { PropertyCard } from "./sidebar/PropertyCard";
import { RegulatoryCard } from "./sidebar/RegulatoryCard";
import { IncentivesCard } from "./sidebar/IncentivesCard";
import { NeighborhoodCard } from "./sidebar/NeighborhoodCard";
import { ViolationsCard } from "./sidebar/ViolationsCard";

const StarIcon = (
  <svg className="w-5 h-5 text-accent" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 16.8l-6.2 4.5 2.4-7.4L2 9.4h7.6z" />
  </svg>
);

function CrimeYoYCard({ data }: { data: ScorecardResponse }) {
  const crime = data.context.crime_last_90d;
  if (!crime) return null;
  const yoy = crime.yoy;
  return (
    <div className="bg-dark-surface border border-dark-border rounded-xl overflow-hidden">
      <div className="px-4 py-2.5 border-b border-dark-border flex items-center gap-2">
        <svg className="w-3.5 h-3.5 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0-10.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
        </svg>
        <span className="text-[11px] font-medium text-text-primary">Crime</span>
        <span className="ml-auto text-[10px] text-text-muted">{crime.total.toLocaleString()} incidents (90d)</span>
      </div>
      <div className="px-4 py-3 space-y-2">
        <div className="flex gap-4 text-[11px]">
          <span className="text-text-muted">Arrest rate</span>
          <span className="text-text-primary font-mono">{(crime.arrest_rate * 100).toFixed(1)}%</span>
        </div>
        {yoy && yoy.length > 0 && (
          <div>
            <div className="text-[10px] text-text-muted mb-1.5">{crime.yoy_period || "Year-over-Year"}</div>
            <div className="space-y-1">
              {yoy.slice(0, 6).map((item) => (
                <div key={item.category} className="flex items-center justify-between text-[11px]">
                  <span className="text-text-secondary truncate flex-1 mr-2">{item.category}</span>
                  <span className="font-mono text-text-primary w-8 text-right">{item.current_count}</span>
                  <span className={`font-mono w-14 text-right ${
                    item.change_pct > 0 ? "text-rose-400" : item.change_pct < 0 ? "text-emerald-400" : "text-text-muted"
                  }`}>
                    {item.change_pct > 0 ? "+" : ""}{item.change_pct}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Address311Card({ data }: { data: ScorecardResponse }) {
  const addr311 = data.context.address_311;
  if (!addr311) return null;
  return (
    <div className="bg-dark-surface border border-dark-border rounded-xl overflow-hidden">
      <div className="px-4 py-2.5 border-b border-dark-border flex items-center gap-2">
        <svg className="w-3.5 h-3.5 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
        </svg>
        <span className="text-[11px] font-medium text-text-primary">311 Complaints at Address</span>
        <span className="ml-auto text-[10px] text-text-muted">{addr311.total} (past year)</span>
      </div>
      <div className="px-4 py-3 space-y-2">
        {addr311.open_count > 0 && (
          <div className="text-[11px] text-amber-400">{addr311.open_count} open complaint{addr311.open_count !== 1 ? "s" : ""}</div>
        )}
        {addr311.high_risk_flags.length > 0 && (
          <div className="space-y-1">
            <div className="text-[10px] text-rose-400 font-medium">High-risk flags</div>
            {addr311.high_risk_flags.map((flag) => (
              <div key={flag} className="text-[11px] text-rose-300 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-400 flex-shrink-0" />
                {flag}
              </div>
            ))}
          </div>
        )}
        {Object.entries(addr311.by_type).length > 0 && (
          <div className="space-y-1">
            {Object.entries(addr311.by_type).slice(0, 5).map(([type, count]) => (
              <div key={type} className="flex items-center justify-between text-[11px]">
                <span className="text-text-secondary truncate flex-1 mr-2">{type}</span>
                <span className="font-mono text-text-primary">{count}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function InvestigateButton({ question, label }: { question: string; label: string }) {
  return (
    <Link
      to={`/?q=${encodeURIComponent(question)}`}
      className="inline-flex items-center gap-1 text-[10px] text-accent hover:text-accent-hover transition-colors"
    >
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
      </svg>
      {label}
    </Link>
  );
}

function ScorecardSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="bg-dark-surface border border-dark-border rounded-xl h-48" />
      ))}
    </div>
  );
}

export default function ScorecardPage() {
  const [searchParams] = useSearchParams();
  const { user } = useAuthContext();
  const [address, setAddress] = useState(searchParams.get("address") || "");
  const [data, setData] = useState<ScorecardResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [showUpgrade, setShowUpgrade] = useState(false);

  const isPro = user?.tier === "premium" || user?.tier === "admin";

  const handleDownloadPdf = useCallback(async () => {
    if (!data?.address) return;
    if (!isPro) {
      setShowUpgrade(true);
      return;
    }
    setDownloading(true);
    try {
      const blob = await fetchReport({ address: data.address });
      if (blob) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${data.address.replace(/[^a-z0-9]+/gi, "_").toLowerCase()}_zoning_report.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } finally {
      setDownloading(false);
    }
  }, [data, isPro]);

  const doSearch = useCallback(async (query: string) => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setSearched(true);
    const result = await fetchScorecard({ address: query.trim() });
    if (result) {
      setData(result);
    } else {
      setError("Could not find that address. Try a different format (e.g., \"2400 N Milwaukee Ave\").");
      setData(null);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    const q = searchParams.get("address");
    if (q) {
      setAddress(q);
      doSearch(q);
    }
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    doSearch(address);
  };

  const ctx = data?.context;
  const zoning = ctx?.parcel_zoning;

  return (
    <div className="min-h-screen bg-dark-bg text-text-primary">
      {/* Header */}
      <header className="border-b border-dark-border bg-dark-surface/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            {StarIcon}
            <span className="text-sm font-semibold tracking-tight">UrbanLayer</span>
          </Link>
          <nav className="flex items-center gap-4 text-[11px] text-text-muted">
            <Link to="/" className="hover:text-text-primary transition-colors">Chat</Link>
            <span className="text-accent">Scorecard</span>
            <Link to="/about" className="hover:text-text-primary transition-colors">About</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Search */}
        <div className="max-w-2xl mx-auto mb-8">
          <h1 className="text-2xl font-semibold tracking-tight mb-2">Property Scorecard</h1>
          <p className="text-sm text-text-muted mb-4">
            Instant property intelligence — no AI cost. Enter a Chicago address.
          </p>
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="2400 N Milwaukee Ave"
              className="flex-1 bg-dark-surface border border-dark-border rounded-lg px-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent transition-colors"
            />
            <button
              type="submit"
              disabled={loading || !address.trim()}
              className="px-5 py-2.5 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {loading ? "Loading..." : "Search"}
            </button>
          </form>
          {error && (
            <div className="mt-3 text-sm text-rose-400 bg-rose-400/10 border border-rose-400/20 rounded-lg px-4 py-2.5">
              {error}
            </div>
          )}
        </div>

        {loading && <ScorecardSkeleton />}

        {data && ctx && !loading && (
          <div>
            {/* Address header */}
            <div className="mb-6 pb-4 border-b border-dark-border">
              <div className="flex items-baseline gap-3 flex-wrap">
                <h2 className="text-lg font-semibold">{data.address || "Unknown Address"}</h2>
                {data.community_area_name && (
                  <span className="text-sm text-text-muted">{data.community_area_name}</span>
                )}
                {zoning && (
                  <span className="text-xs font-mono bg-dark-elevated px-2 py-0.5 rounded text-accent">
                    {zoning.zone_class}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 mt-2 text-[10px] text-text-muted">
                <span>{data.lat.toFixed(5)}, {data.lon.toFixed(5)}</span>
                {data.context.data_as_of && <span>Data as of {data.context.data_as_of}</span>}
              </div>
              {data.partial_failures.length > 0 && (
                <div className="mt-2 text-[11px] text-amber-400">
                  Some data unavailable: {data.partial_failures.join(", ")}
                </div>
              )}
              {/* Investigate buttons */}
              <div className="flex flex-wrap gap-3 mt-3 items-center">
                <InvestigateButton
                  question={`What's going on near ${data.address}?`}
                  label="Full analysis"
                />
                {zoning && (
                  <InvestigateButton
                    question={`What are the allowed uses, setbacks, and FAR for ${zoning.zone_class} zoning?`}
                    label={`${zoning.zone_class} zoning rules`}
                  />
                )}
                <button
                  onClick={handleDownloadPdf}
                  disabled={downloading}
                  className="inline-flex items-center gap-1 text-[10px] text-accent hover:text-accent-hover disabled:opacity-50 transition-colors"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                  {downloading ? "Generating..." : "Download PDF Report"}
                </button>
              </div>
            </div>

            {/* Card grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {ctx.property && <PropertyCard data={ctx.property} />}
              {ctx.regulatory && <RegulatoryCard data={ctx.regulatory} />}
              {ctx.incentives && <IncentivesCard data={ctx.incentives} />}
              {ctx.neighborhood && <NeighborhoodCard data={ctx.neighborhood} />}
              {ctx.violations && <ViolationsCard data={ctx.violations} />}
              <CrimeYoYCard data={data} />
              <Address311Card data={data} />
            </div>
          </div>
        )}

        {!loading && !data && searched && !error && (
          <div className="text-center text-text-muted py-12">No results found.</div>
        )}
      </main>
      {showUpgrade && (
        <UpgradePrompt
          feature="PDF zoning reports"
          onClose={() => setShowUpgrade(false)}
        />
      )}
    </div>
  );
}
