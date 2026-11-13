import { useTranslation } from "react-i18next";
import { useAuthContext } from "../contexts/AuthContext";
import ProviderButtons from "./auth/ProviderButtons";
import { Modal } from "./ui/Modal";

interface AuthModalProps {
  /** Kept for callers; the provider buttons sign in themselves (Item 121). */
  onSignIn?: () => void;
  onClose: () => void;
}

export default function AuthModal({ onClose }: AuthModalProps) {
  const { t } = useTranslation("common");
  const { providers, signInWith } = useAuthContext();
  return (
    <Modal onClose={onClose} size="sm">
      <div>
        <h2 className="text-subtitle text-text-primary text-center mb-2">
          {t("signInTitle")}
        </h2>
        <p className="text-body text-text-secondary text-center mb-6">
          {t("signInDescription")} {t("signInFreeNote")}.
        </p>

        <ProviderButtons providers={providers} onChoose={(p) => signInWith(p)} />

        <button
          onClick={onClose}
          className="w-full mt-3 text-caption text-text-muted hover:text-text-secondary transition-colors text-center py-2"
        >
          {t("continueBrowsing")}
        </button>
      </div>
    </Modal>
  );
}
