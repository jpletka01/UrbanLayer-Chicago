// "Continue with Google / Apple / Microsoft" (Phase 9, Item 121). The one place outside Lucide: each provider's
// own mark, as their button rules require (owner's call, 2026-11-13). Order Google, Apple, Microsoft; only the
// methods this server offers. Shared by the old UI's AuthModal, Settings and the new UI's sign-in cards.
import { useTranslation } from "react-i18next";
import type { SignInProvider, SignInProviderId } from "../../lib/api";
import { PROVIDER_NAMES } from "../../lib/authNotice";

export function ProviderMark({ provider, className = "h-5 w-5" }: { provider: SignInProviderId; className?: string }) {
  if (provider === "google") {
    return (
      <svg aria-hidden className={className} viewBox="0 0 24 24">
        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
      </svg>
    );
  }
  if (provider === "microsoft") {
    return (
      <svg aria-hidden className={className} viewBox="0 0 23 23">
        <rect x="1" y="1" width="10" height="10" fill="#F25022" />
        <rect x="12" y="1" width="10" height="10" fill="#7FBA00" />
        <rect x="1" y="12" width="10" height="10" fill="#00A4EF" />
        <rect x="12" y="12" width="10" height="10" fill="#FFB900" />
      </svg>
    );
  }
  // Apple's mark takes the text color: black on light buttons, white on dark ones.
  return (
    <svg aria-hidden className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M16.37 1.43c0 1.14-.49 2.27-1.18 3.08-.74.9-1.99 1.57-2.99 1.57-.12 0-.23-.02-.3-.03-.01-.06-.04-.22-.04-.39 0-1.15.57-2.27 1.21-2.98.8-.94 2.14-1.64 3.25-1.68.03.13.05.28.05.43zm4.56 15.71c-.03.07-.46 1.58-1.52 3.12-.94 1.34-1.94 2.71-3.43 2.71-1.52 0-1.9-.88-3.63-.88-1.7 0-2.3.91-3.67.91-1.38 0-2.33-1.26-3.43-2.8C4 18.38 2.96 15.57 2.96 12.92c0-4.28 2.8-6.55 5.55-6.55 1.45 0 2.68.95 3.6.95.87 0 2.22-1.01 3.9-1.01.61 0 2.89.06 4.37 2.19-.13.09-2.38 1.37-2.38 4.19 0 3.26 2.85 4.42 2.95 4.45z" />
    </svg>
  );
}

interface Props {
  providers: SignInProvider[];
  onChoose: (provider: SignInProviderId) => void;
  /** The button look: each UI passes its own tokens (the new UI's live only in src/ui-next). */
  buttonClassName?: string;
  /** Focus the first button (a dialog that opens on it). */
  autoFocus?: boolean;
}

const OLD_LOOK = "bg-white text-gray-900 ring-1 ring-gray-300 hover:bg-gray-100";

export default function ProviderButtons({ providers, onChoose, buttonClassName = OLD_LOOK, autoFocus }: Props) {
  const { t } = useTranslation("common");
  const base =
    "flex w-full items-center justify-center gap-3 rounded-xl px-4 py-2.5 font-medium transition-colors touch-target";
  return (
    <div className="flex flex-col gap-2" data-testid="signin-providers">
      {providers.map((p, i) => (
        <button
          key={p.id}
          type="button"
          autoFocus={autoFocus && i === 0}
          onClick={() => onChoose(p.id)}
          className={`${base} ${buttonClassName}`}
          data-provider={p.id}
        >
          <ProviderMark provider={p.id} />
          <span>{t("auth.continueWith", { provider: PROVIDER_NAMES[p.id] })}</span>
        </button>
      ))}
      {providers.some((p) => p.test) && (
        <p className="text-center text-caption opacity-70" data-testid="signin-test-note">{t("auth.testNote")}</p>
      )}
    </div>
  );
}
