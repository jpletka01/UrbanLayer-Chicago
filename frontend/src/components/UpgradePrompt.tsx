import { useState } from "react";
import { createCheckoutSession } from "../lib/api";

interface UpgradePromptProps {
  feature?: string;
  onClose: () => void;
}

export default function UpgradePrompt({ feature, onClose }: UpgradePromptProps) {
  const [loading, setLoading] = useState(false);

  async function handleUpgrade() {
    setLoading(true);
    try {
      const { url } = await createCheckoutSession();
      window.location.href = url;
    } catch {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-sm mx-4 bg-dark-surface border border-dark-border rounded-2xl p-8 shadow-2xl">
        <div className="w-10 h-10 mx-auto mb-4 rounded-full bg-accent/10 flex items-center justify-center">
          <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>

        <h2 className="text-lg font-semibold text-text-primary text-center mb-2">
          Upgrade to Pro
        </h2>
        <p className="text-sm text-text-secondary text-center mb-6">
          {feature
            ? `${feature} is a Pro feature. Upgrade to unlock it along with unlimited queries, PDF reports, and more.`
            : "Unlock unlimited queries, PDF zoning reports, Property Discovery, and priority support for $99/month."}
        </p>

        <button
          onClick={handleUpgrade}
          disabled={loading}
          className="w-full py-2.5 bg-accent hover:bg-accent/90 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50"
        >
          {loading ? "Redirecting to checkout..." : "Upgrade — $99/month"}
        </button>

        <button
          onClick={onClose}
          className="w-full mt-3 text-xs text-text-muted hover:text-text-secondary transition-colors text-center py-2"
        >
          Maybe later
        </button>
      </div>
    </div>
  );
}
