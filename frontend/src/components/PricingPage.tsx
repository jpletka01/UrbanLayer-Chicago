import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuthContext } from "../contexts/AuthContext";
import { createCheckoutSession } from "../lib/api";

export default function PricingPage() {
  const { t } = useTranslation("pages");
  const { user, isAuthenticated } = useAuthContext();
  const [loading, setLoading] = useState(false);

  const isPro = user?.tier === "premium" || user?.tier === "admin";

  const freeFeatures = t("pricing.freeFeatures", { returnObjects: true }) as string[];
  const reportFeatures = t("pricing.reportFeatures", { returnObjects: true }) as string[];
  const proFeatures = t("pricing.proFeatures", { returnObjects: true }) as string[];

  async function handleUpgrade() {
    if (!isAuthenticated) {
      window.location.href = "/";
      return;
    }
    setLoading(true);
    try {
      const { url } = await createCheckoutSession();
      window.location.href = url;
    } catch {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-dark-bg text-text-primary">
      <header className="border-b border-dark-border px-6 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <img src="/logo.jpg" alt="UrbanLayer" className="w-6 h-6 rounded-full" />
          <span className="font-semibold text-sm">UrbanLayer</span>
        </Link>
        <Link
          to="/"
          className="text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          {t("nav.backToApp")}
        </Link>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-16">
        <h1 className="text-3xl font-bold text-center mb-3">
          {t("pricing.title")}
        </h1>
        <p className="text-text-secondary text-center mb-12 max-w-lg mx-auto">
          {t("pricing.subtitle")}
        </p>

        <div className="grid md:grid-cols-3 gap-6">
          {/* Free tier */}
          <div className="bg-dark-surface border border-dark-border rounded-2xl p-8">
            <h2 className="text-lg font-semibold mb-1">{t("pricing.free")}</h2>
            <p className="text-text-muted text-sm mb-4">{t("pricing.forExploration")}</p>
            <div className="mb-6">
              <span className="text-3xl font-bold">$0</span>
              <span className="text-text-muted text-sm ml-1">{t("pricing.perMonth")}</span>
            </div>
            <ul className="space-y-3 mb-8">
              {freeFeatures.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-text-secondary">
                  <svg className="w-4 h-4 mt-0.5 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  {f}
                </li>
              ))}
            </ul>
            {!isPro && (
              <div className="text-center text-xs text-text-muted">{t("pricing.currentPlan")}</div>
            )}
          </div>

          {/* Development Feasibility Report — the per-parcel wedge */}
          <div className="bg-dark-surface border-2 border-accent rounded-2xl p-8 relative">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-accent text-white text-xs font-medium px-3 py-1 rounded-full">
              {t("pricing.startHere")}
            </div>
            <h2 className="text-lg font-semibold mb-1">{t("pricing.reportTier")}</h2>
            <p className="text-text-muted text-sm mb-4">{t("pricing.perParcelNoSub")}</p>
            <div className="mb-6">
              <span className="text-3xl font-bold">$25</span>
              <span className="text-text-muted text-sm ml-1">{t("pricing.perReport")}</span>
            </div>
            <ul className="space-y-3 mb-8">
              {reportFeatures.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-text-secondary">
                  <svg className="w-4 h-4 mt-0.5 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  {f}
                </li>
              ))}
            </ul>
            <Link
              to="/scorecard"
              className="block w-full py-2.5 bg-accent hover:bg-accent/90 text-white rounded-lg font-medium text-sm transition-colors text-center"
            >
              {t("pricing.getReport")}
            </Link>
            <p className="text-center text-xs text-text-muted mt-3">{t("pricing.scorecardHint")}</p>
          </div>

          {/* Pro tier */}
          <div className="bg-dark-surface border border-dark-border rounded-2xl p-8">
            <h2 className="text-lg font-semibold mb-1">{t("pricing.pro")}</h2>
            <p className="text-text-muted text-sm mb-4">{t("pricing.forProfessionals")}</p>
            <div className="mb-6">
              <span className="text-3xl font-bold">$99</span>
              <span className="text-text-muted text-sm ml-1">{t("pricing.perMonth")}</span>
            </div>
            <ul className="space-y-3 mb-8">
              {proFeatures.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-text-secondary">
                  <svg className="w-4 h-4 mt-0.5 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  {f}
                </li>
              ))}
            </ul>
            {isPro ? (
              <div className="text-center text-xs text-accent font-medium">{t("pricing.active")}</div>
            ) : (
              <>
                <button
                  onClick={handleUpgrade}
                  disabled={loading}
                  className="w-full py-2.5 bg-dark-elevated hover:bg-dark-elevated/80 border border-dark-border text-text-primary rounded-lg font-medium text-sm transition-colors disabled:opacity-50"
                >
                  {loading ? t("pricing.redirecting") : t("pricing.upgradeToPro")}
                </button>
                <p className="text-center text-xs text-text-muted mt-3">{t("pricing.proMath")}</p>
              </>
            )}
          </div>
        </div>

        <p className="text-center text-xs text-text-muted mt-8">
          {t("pricing.billingNote")}
        </p>
      </main>
    </div>
  );
}
