import { useState } from "react";
import { useTranslation } from "react-i18next";
import { createCheckoutSession } from "../lib/api";
import { Modal } from "./ui/Modal";

interface UpgradePromptProps {
  feature?: string;
  onClose: () => void;
}

export default function UpgradePrompt({ feature, onClose }: UpgradePromptProps) {
  const { t } = useTranslation("common");
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
    <Modal onClose={onClose} size="sm">
      <div>
        <div className="w-10 h-10 mx-auto mb-4 rounded-full bg-accent/10 flex items-center justify-center">
          <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>

        <h2 className="text-subtitle text-text-primary text-center mb-2">
          {t("upgradeToPro")}
        </h2>
        <p className="text-body text-text-secondary text-center mb-6">
          {feature
            ? t("upgradePrompt.featureBody", { feature })
            : t("upgradePrompt.genericBody")}
        </p>

        <button
          onClick={handleUpgrade}
          disabled={loading}
          className="w-full py-2.5 bg-highlight-fill hover:opacity-90 text-highlight-fg rounded-lg text-title transition-colors disabled:opacity-50"
        >
          {loading ? t("upgradePrompt.redirecting") : t("upgradePrompt.cta")}
        </button>

        <button
          onClick={onClose}
          className="w-full mt-3 text-caption text-text-muted hover:text-text-secondary transition-colors text-center py-2"
        >
          {t("maybeLater")}
        </button>
      </div>
    </Modal>
  );
}
