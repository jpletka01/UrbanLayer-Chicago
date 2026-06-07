import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuthContext } from "../contexts/AuthContext";
import { createCheckoutSession } from "../lib/api";

const FREE_FEATURES = [
  "25 AI queries per day",
  "Property scorecard lookups",
  "Interactive map with data layers",
  "Crime, 311, permits, violations data",
  "Municipal code search (RAG)",
  "Conversation history",
  "Shareable conversation links",
];

const PRO_FEATURES = [
  "Unlimited AI queries",
  "PDF zoning reports",
  "Site Explorer (coming soon)",
  "Priority support",
  "All Free features included",
];

export default function PricingPage() {
  const { user, isAuthenticated } = useAuthContext();
  const [loading, setLoading] = useState(false);

  const isPro = user?.tier === "premium" || user?.tier === "admin";

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
          <img src="/favicon.svg" alt="" className="w-6 h-6" />
          <span className="font-semibold text-sm">UrbanLayer</span>
        </Link>
        <Link
          to="/"
          className="text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          Back to app
        </Link>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-16">
        <h1 className="text-3xl font-bold text-center mb-3">
          Plans & Pricing
        </h1>
        <p className="text-text-secondary text-center mb-12 max-w-lg mx-auto">
          AI-powered urban intelligence for Chicago real estate professionals.
          Get instant answers about zoning, property, and regulatory data.
        </p>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Free tier */}
          <div className="bg-dark-surface border border-dark-border rounded-2xl p-8">
            <h2 className="text-lg font-semibold mb-1">Free</h2>
            <p className="text-text-muted text-sm mb-4">For exploration</p>
            <div className="mb-6">
              <span className="text-3xl font-bold">$0</span>
              <span className="text-text-muted text-sm ml-1">/month</span>
            </div>
            <ul className="space-y-3 mb-8">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-text-secondary">
                  <svg className="w-4 h-4 mt-0.5 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  {f}
                </li>
              ))}
            </ul>
            {!isPro && (
              <div className="text-center text-xs text-text-muted">Current plan</div>
            )}
          </div>

          {/* Pro tier */}
          <div className="bg-dark-surface border-2 border-accent rounded-2xl p-8 relative">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-accent text-white text-xs font-medium px-3 py-1 rounded-full">
              Recommended
            </div>
            <h2 className="text-lg font-semibold mb-1">Pro</h2>
            <p className="text-text-muted text-sm mb-4">For professionals</p>
            <div className="mb-6">
              <span className="text-3xl font-bold">$99</span>
              <span className="text-text-muted text-sm ml-1">/month</span>
            </div>
            <ul className="space-y-3 mb-8">
              {PRO_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-text-secondary">
                  <svg className="w-4 h-4 mt-0.5 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  {f}
                </li>
              ))}
            </ul>
            {isPro ? (
              <div className="text-center text-xs text-accent font-medium">Active</div>
            ) : (
              <button
                onClick={handleUpgrade}
                disabled={loading}
                className="w-full py-2.5 bg-accent hover:bg-accent/90 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50"
              >
                {loading ? "Redirecting..." : "Upgrade to Pro"}
              </button>
            )}
          </div>
        </div>

        <p className="text-center text-xs text-text-muted mt-8">
          Subscriptions are billed monthly via Stripe. Cancel anytime.
        </p>
      </main>
    </div>
  );
}
