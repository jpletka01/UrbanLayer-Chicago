import { useState, useCallback, useEffect, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { fetchScorecard, fetchReport, checkReportAccess, type ScorecardResponse } from "../lib/api";
import { useAuthContext } from "../contexts/AuthContext";
import ReportPurchasePrompt from "./ReportPurchasePrompt";
import { ReportCTACard } from "./ReportCTACard";
import { InvestigateButton } from "./InvestigateButton";
import { PropertyCard } from "./sidebar/PropertyCard";
import { ComparablesCard } from "./sidebar/ComparablesCard";
import { RegulatoryCard } from "./sidebar/RegulatoryCard";
import { IncentivesCard } from "./sidebar/IncentivesCard";
import { NeighborhoodCard } from "./sidebar/NeighborhoodCard";
import { ViolationsCard } from "./sidebar/ViolationsCard";
import { buildScorecardCSV, downloadCSV, buildFilenameSlug } from "../lib/csvExport";
import { FinancialSnapshotStrip } from "./FinancialSnapshotStrip";

const StarIcon = (
  <svg className="w-5 h-5 text-accent" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 16.8l-6.2 4.5 2.4-7.4L2 9.4h7.6z" />
  </svg>
);

function CrimeYoYCard({ data }: { data: ScorecardResponse }) {
  const { t } = useTranslation("pages");
  const crime = data.context.crime_last_90d;
  if (!crime) return null;
  const yoy = crime.yoy;
  return (
    <div className="bg-dark-surface border border-dark-border rounded-xl overflow-hidden">
      <div className="px-4 py-2.5 border-b border-dark-border flex items-center gap-2">
        <svg className="w-3.5 h-3.5 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0-10.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
        </svg>
        <span className="text-[11px] font-medium text-text-primary">{t("scorecard.crime")}</span>
        <span className="ml-auto text-[10px] text-text-muted">{t("scorecard.incidents90d", { count: crime.total })}</span>
      </div>
      <div className="px-4 py-3 space-y-2">
        <div className="flex gap-4 text-[11px]">
          <span className="text-text-muted">{t("scorecard.arrestRate")}</span>
          <span className="text-text-primary font-mono">{(crime.arrest_rate * 100).toFixed(1)}%</span>
        </div>
        {yoy && yoy.length > 0 && (
          <div>
            <div className="text-[10px] text-text-muted mb-1.5">{crime.yoy_period || t("scorecard.yearOverYear")}</div>
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
  const { t } = useTranslation("pages");
  const addr311 = data.context.address_311;
  if (!addr311) return null;
  return (
    <div className="bg-dark-surface border border-dark-border rounded-xl overflow-hidden">
      <div className="px-4 py-2.5 border-b border-dark-border flex items-center gap-2">
        <svg className="w-3.5 h-3.5 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
        </svg>
        <span className="text-[11px] font-medium text-text-primary">{t("scorecard.311atAddress")}</span>
        <span className="ml-auto text-[10px] text-text-muted">{addr311.total} {t("scorecard.pastYear")}</span>
      </div>
      <div className="px-4 py-3 space-y-2">
        {addr311.open_count > 0 && (
          <div className="text-[11px] text-amber-400">{t("scorecard.openComplaints", { count: addr311.open_count })}</div>
        )}
        {addr311.high_risk_flags.length > 0 && (
          <div className="space-y-1">
            <div className="text-[10px] text-rose-400 font-medium">{t("scorecard.highRiskFlags")}</div>
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
  const { t } = useTranslation("pages");
  const [searchParams] = useSearchParams();
  const { user } = useAuthContext();
  const [address, setAddress] = useState(searchParams.get("address") || "");
  const [data, setData] = useState<ScorecardResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [showPurchasePrompt, setShowPurchasePrompt] = useState(false);
  const [reportAccess, setReportAccess] = useState<{ has_access: boolean; reason: string } | null>(null);
  const ctaRef = useRef<HTMLDivElement>(null);
  const [ctaVisible, setCtaVisible] = useState(true);

  const isPro = user?.tier === "premium" || user?.tier === "admin";
  const hasReportAccess = isPro || reportAccess?.has_access === true;

  const triggerDownload = useCallback(async (addr: string) => {
    setDownloading(true);
    try {
      const blob = await fetchReport({ address: addr });
      if (blob) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${addr.replace(/[^a-z0-9]+/gi, "_").toLowerCase()}_zoning_report.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } finally {
      setDownloading(false);
    }
  }, []);

  const handleDownloadPdf = useCallback(async () => {
    if (!data?.address) return;
    if (hasReportAccess) {
      await triggerDownload(data.address);
    } else {
      setShowPurchasePrompt(true);
    }
  }, [data, hasReportAccess, triggerDownload]);

  const doSearch = useCallback(async (query: string) => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setSearched(true);
    const result = await fetchScorecard({ address: query.trim() });
    if (result) {
      setData(result);
    } else {
      setError(t("scorecard.addressNotFound"));
      setData(null);
    }
    setLoading(false);
  }, [t]);

  const doSearchByCoords = useCallback(async (lat: number, lon: number) => {
    setLoading(true);
    setError(null);
    setSearched(true);
    const result = await fetchScorecard({ lat, lon });
    if (result) {
      setData(result);
      if (result.address) setAddress(result.address);
    } else {
      setError(t("scorecard.locationNotFound"));
      setData(null);
    }
    setLoading(false);
  }, [t]);

  useEffect(() => {
    const q = searchParams.get("address");
    const lat = searchParams.get("lat");
    const lon = searchParams.get("lon");
    if (q) {
      setAddress(q);
      doSearch(q);
    } else if (lat && lon) {
      doSearchByCoords(parseFloat(lat), parseFloat(lon));
    }
  }, []);

  // Fetch report access when scorecard data loads (for non-pro users)
  useEffect(() => {
    if (!data || isPro) return;
    checkReportAccess({ lat: data.lat, lon: data.lon }).then(setReportAccess);
  }, [data, isPro]);

  // Handle post-purchase redirect: auto-download the report
  useEffect(() => {
    if (!data?.address) return;
    if (searchParams.get("report_purchased") !== "1") return;
    setReportAccess({ has_access: true, reason: "purchased" });
    triggerDownload(data.address);
    const url = new URL(window.location.href);
    url.searchParams.delete("report_purchased");
    window.history.replaceState({}, "", url.toString());
  }, [data, searchParams, triggerDownload]);

  useEffect(() => {
    const el = ctaRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setCtaVisible(entry.isIntersecting),
      { threshold: 0 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [data]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    doSearch(address);
  };

  const ctx = data?.context;
  const zoning = ctx?.parcel_zoning;
  const addr = data?.address || ctx?.property?.address || "";

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
            <Link to="/" className="hover:text-text-primary transition-colors">{t("nav.chat")}</Link>
            <span className="text-accent">{t("nav.scorecard")}</span>
            <Link to="/explore" className="hover:text-text-primary transition-colors">{t("nav.explore")}</Link>
            <Link to="/about" className="hover:text-text-primary transition-colors">{t("nav.about")}</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Search */}
        <div className="max-w-2xl mx-auto mb-8">
          <h1 className="text-2xl font-semibold tracking-tight mb-2">{t("scorecard.title")}</h1>
          <p className="text-sm text-text-muted mb-4">
            {t("scorecard.subtitle")}
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
              {loading ? t("scorecard.loading") : t("scorecard.search")}
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
                <h2 className="text-lg font-semibold">{data.address || ctx.property?.address || "Unknown Address"}</h2>
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
                {data.context.data_as_of && <span>{t("scorecard.dataAsOf", { date: data.context.data_as_of })}</span>}
              </div>
              {data.partial_failures.length > 0 && (
                <div className="mt-2 text-[11px] text-amber-400">
                  {t("scorecard.someDataUnavailable", { sources: data.partial_failures.join(", ") })}
                </div>
              )}
              {/* Investigate buttons */}
              <div className="flex flex-wrap gap-3 mt-3 items-center">
                <InvestigateButton
                  question={`What's going on near ${data.address}?`}
                  label={t("scorecard.fullAnalysis")}
                />
                {zoning && (
                  <InvestigateButton
                    question={`What are the allowed uses, setbacks, and FAR for ${zoning.zone_class} zoning?`}
                    label={t("scorecard.zoningRules", { zone: zoning.zone_class })}
                  />
                )}
                <button
                  onClick={() => {
                    const slug = buildFilenameSlug(data.address || "property");
                    const date = new Date().toISOString().slice(0, 10);
                    downloadCSV(buildScorecardCSV(ctx, data.address ?? "", data.comparables), `${slug}_scorecard_${date}.csv`);
                  }}
                  className="inline-flex items-center gap-1 text-[10px] text-accent hover:text-accent-hover transition-colors"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                  {t("scorecard.downloadCsv")}
                </button>
              </div>
            </div>

            {/* Report CTA */}
            <div className="mb-6" ref={ctaRef}>
              <ReportCTACard
                hasReportAccess={hasReportAccess}
                downloading={downloading}
                onDownload={handleDownloadPdf}
                onShowPurchase={() => setShowPurchasePrompt(true)}
              />
            </div>

            {/* Financial Snapshot */}
            <FinancialSnapshotStrip
              property={ctx.property}
              comparables={data.comparables}
              incentives={ctx.incentives}
            />

            {/* Card grid — ordered for developer evaluation flow */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {ctx.property && (
                <div>
                  <PropertyCard data={ctx.property} />
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    <InvestigateButton
                      question={`Tell me about the building and property characteristics at ${addr}`}
                      label={t("scorecard.investigate.buildingDetails")}
                    />
                  </div>
                </div>
              )}
              {data.comparables && data.comparables.sales.length > 0 && (
                <div>
                  <ComparablesCard data={data.comparables} />
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    <InvestigateButton
                      question={`What are the recent comparable sales near ${addr} and what do they suggest about property values?`}
                      label={t("scorecard.investigate.comparableSales")}
                    />
                  </div>
                </div>
              )}
              {ctx.incentives && (
                <div>
                  <IncentivesCard data={ctx.incentives} />
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    {ctx.incentives.in_tif_district && ctx.incentives.tif_name && (
                      <InvestigateButton
                        question={`How much TIF funding is available in ${ctx.incentives.tif_name} and what projects qualify?`}
                        label={t("scorecard.investigate.tifFunding")}
                      />
                    )}
                    <InvestigateButton
                      question={`What tax incentives and grant programs are available near ${addr}?`}
                      label={t("scorecard.investigate.incentivePrograms")}
                    />
                  </div>
                </div>
              )}
              {ctx.regulatory && (
                <div>
                  <RegulatoryCard data={ctx.regulatory} />
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    <InvestigateButton
                      question={`What are the development restrictions from regulatory overlays at ${addr}?`}
                      label={t("scorecard.investigate.overlayRestrictions")}
                    />
                    {ctx.regulatory.flood_zone && ctx.regulatory.flood_zone !== "X" && (
                      <InvestigateButton
                        question={`What are the flood insurance requirements for FEMA zone ${ctx.regulatory.flood_zone} at ${addr}?`}
                        label={t("scorecard.investigate.floodRisk")}
                      />
                    )}
                  </div>
                </div>
              )}
              {ctx.neighborhood && (
                <div>
                  <NeighborhoodCard data={ctx.neighborhood} />
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    <InvestigateButton
                      question={`What's the neighborhood like around ${addr}?`}
                      label={t("scorecard.investigate.neighborhoodOverview")}
                    />
                  </div>
                </div>
              )}
              {ctx.violations && (
                <div>
                  <ViolationsCard data={ctx.violations} />
                  {ctx.violations.total > 0 && (
                    <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                      <InvestigateButton
                        question={`Explain the building violations at ${addr} and typical remediation steps`}
                        label={t("scorecard.investigate.violationDetails")}
                      />
                    </div>
                  )}
                </div>
              )}
              <div>
                <CrimeYoYCard data={data} />
                {data.context.crime_last_90d && (
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    <InvestigateButton
                      question={`What are the crime trends and safety concerns near ${addr}?`}
                      label={t("scorecard.investigate.crimeAnalysis")}
                    />
                  </div>
                )}
              </div>
              <div>
                <Address311Card data={data} />
                {data.context.address_311 && (
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    <InvestigateButton
                      question={`What are the 311 complaint patterns at ${addr} and what do they indicate?`}
                      label={t("scorecard.investigate.complaints311")}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {!loading && !data && searched && !error && (
          <div className="text-center text-text-muted py-12">{t("scorecard.noResults")}</div>
        )}
      </main>
      {/* Sticky Report CTA — visible when main CTA scrolls out of view */}
      {!ctaVisible && data && !loading && (
        <div className="fixed bottom-0 left-0 right-0 z-40 bg-dark-surface/95 backdrop-blur-sm border-t border-dark-border animate-slide-up">
          <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <svg className="w-4 h-4 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
              <span className="text-sm font-medium text-text-primary">{t("scorecard.reportCTA.stickyTitle")}</span>
            </div>
            <button
              onClick={hasReportAccess ? handleDownloadPdf : () => setShowPurchasePrompt(true)}
              disabled={downloading}
              className="px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors shrink-0"
            >
              {downloading
                ? t("scorecard.reportCTA.generating")
                : hasReportAccess
                  ? t("scorecard.reportCTA.download")
                  : t("scorecard.reportCTA.buyReport")}
            </button>
          </div>
        </div>
      )}

      {showPurchasePrompt && data && (
        <ReportPurchasePrompt
          address={data.address || ""}
          lat={data.lat}
          lon={data.lon}
          onClose={() => setShowPurchasePrompt(false)}
        />
      )}
    </div>
  );
}
