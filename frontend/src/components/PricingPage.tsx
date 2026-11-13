import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuthContext } from "../contexts/AuthContext";
import PageHeader from "./PageHeader";
import { createCheckoutSession } from "../lib/api";
import { usePayments } from "../lib/usePayments";

export default function PricingPage() {
  const { t } = useTranslation("pages");
  const { user, isAuthenticated } = useAuthContext();
  const [loading, setLoading] = useState(false);
  const payments = usePayments();

  const isPro = user?.tier === "premium" || user?.tier === "admin";

  const freeFeatures = t("pricing.freeFeatures", { returnObjects: true }) as string[];
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
      <PageHeader />

      <main className="max-w-5xl mx-auto px-6 py-16">
        <h1 className="text-section text-center mb-3">
          {t("pricing.title")}
        </h1>
        <p className="text-lead text-text-secondary text-center mb-12 max-w-lg mx-auto">
          {t("pricing.subtitle")}
        </p>

        <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
          {/* Free tier */}
          <div className="bg-dark-surface border border-dark-border rounded-2xl p-8">
            <h2 className="text-subtitle font-semibold mb-1">{t("pricing.free")}</h2>
            <p className="text-text-muted text-body mb-4">{t("pricing.forExploration")}</p>
            <div className="mb-6">
              <span className="text-stat">$0</span>
              <span className="text-text-muted text-body ml-1">{t("pricing.perMonth")}</span>
            </div>
            <ul className="space-y-3 mb-8">
              {freeFeatures.map((f) => (
                <li key={f} className="flex items-start gap-2 text-body text-text-secondary">
                  <svg className="w-4 h-4 mt-0.5 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  {f}
                </li>
              ))}
            </ul>
            {!isPro && (
              <div className="text-center text-caption text-text-muted">{t("pricing.currentPlan")}</div>
            )}
          </div>

          {/* Pro tier */}
          <div className="bg-dark-surface border border-dark-border rounded-2xl p-8">
            <h2 className="text-subtitle font-semibold mb-1">{t("pricing.pro")}</h2>
            <p className="text-text-muted text-body mb-4">{t("pricing.forProfessionals")}</p>
            <div className="mb-6">
              <span className="text-stat">{t("pricing.proPrice")}</span>
              <span className="text-text-muted text-body ml-1">{t("pricing.perMonth")}</span>
              <p className="text-caption text-text-muted mt-1">{t("pricing.proYearly")}</p>
            </div>
            <ul className="space-y-3 mb-8">
              {proFeatures.map((f) => (
                <li key={f} className="flex items-start gap-2 text-body text-text-secondary">
                  <svg className="w-4 h-4 mt-0.5 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  {f}
                </li>
              ))}
            </ul>
            {isPro ? (
              <div className="text-center text-caption text-accent font-medium">{t("pricing.active")}</div>
            ) : payments?.subscriptions === false ? (
              <div className="w-full py-2.5 border border-dark-border text-text-muted rounded-lg text-title text-center">
                {t("payments.comingSoon", { ns: "common" })}
              </div>
            ) : (
              <>
                <button
                  onClick={handleUpgrade}
                  disabled={loading}
                  className="w-full py-2.5 bg-dark-elevated hover:bg-dark-hover border border-dark-border text-text-primary rounded-lg text-title transition-colors disabled:opacity-50"
                >
                  {loading ? t("pricing.redirecting") : t("pricing.upgradeToPro")}
                </button>
              </>
            )}
          </div>
        </div>

        <p className="text-center text-caption text-text-muted mt-8">
          {t("pricing.billingNote")}
        </p>
      </main>
    </div>
  );
}
