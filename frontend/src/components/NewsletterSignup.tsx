import { useState } from "react";
import { useTranslation } from "react-i18next";
import { subscribeNewsletter } from "../lib/api";
import { track } from "../lib/tracking";

// Newsletter capture — the owned email channel. `source` records which
// surface captured the address (footer, scorecard, …).

export function NewsletterSignup({ source }: { source: string }) {
  const { t } = useTranslation("landing");
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "busy" | "done" | "error">("idle");

  const submit = async () => {
    const value = email.trim();
    if (!value || status === "busy") return;
    setStatus("busy");
    try {
      await subscribeNewsletter(value, source);
      track("newsletter_signup", { source });
      setStatus("done");
    } catch {
      setStatus("error");
    }
  };

  if (status === "done") {
    return <p className="text-text-secondary text-xs">{t("newsletter.done")}</p>;
  }

  return (
    <div className="space-y-2">
      <p className="text-text-primary font-semibold text-sm">{t("newsletter.title")}</p>
      <p className="text-text-muted text-xs">{t("newsletter.description")}</p>
      <div className="flex gap-2">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder={t("newsletter.placeholder")}
          maxLength={254}
          className="flex-1 min-w-0 rounded-lg bg-dark-elevated border border-dark-border px-3 py-1.5 text-caption text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
        />
        <button
          onClick={submit}
          disabled={status === "busy"}
          className="shrink-0 rounded-lg border border-dark-border px-3 py-1.5 text-caption text-text-secondary hover:border-accent hover:text-text-primary transition-colors disabled:opacity-50"
        >
          {t("newsletter.button")}
        </button>
      </div>
      {status === "error" && (
        <p className="text-state-negative text-xs">{t("newsletter.error")}</p>
      )}
    </div>
  );
}
