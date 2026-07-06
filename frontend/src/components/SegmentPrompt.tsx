import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { track } from "../lib/tracking";
import { useAuthContext } from "../contexts/AuthContext";
import { Modal } from "./ui/Modal";

// One-question segment self-identification — the single highest-value datum
// for customer validation ("who is actually showing up?"). Asked ONCE, at the
// moment it belongs to: right after a sign-in completes (useAuth sets
// `ul_segment_due` on the OAuth return). Mounted globally in main.tsx — it
// renders nothing unless that flag is set and no answer is stored. An answer
// or a dismiss both silence it permanently.

const SEGMENTS = [
  "developer",
  "architect",
  "attorney",
  "broker",
  "investor",
  "homeowner",
  "curious",
] as const;

const STORAGE_KEY = "ul_segment";
const DUE_KEY = "ul_segment_due";

export function SegmentPrompt() {
  const { t } = useTranslation("pages");
  const { isAuthenticated } = useAuthContext();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;
    try {
      if (sessionStorage.getItem(DUE_KEY) && !localStorage.getItem(STORAGE_KEY)) {
        setOpen(true);
      }
    } catch {
      // storage unavailable → never prompt
    }
  }, [isAuthenticated]);

  if (!open) return null;

  const settle = (value: string) => {
    try {
      localStorage.setItem(STORAGE_KEY, value);
      sessionStorage.removeItem(DUE_KEY);
    } catch {
      // still track; just may re-ask next sign-in
    }
    track("segment_selected", { segment: value });
    setOpen(false);
  };

  return (
    <Modal
      onClose={() => settle("dismissed")}
      title={t("scorecard.segmentPrompt.question")}
      description={t("scorecard.segmentPrompt.hint")}
      size="md"
    >
      <div className="flex flex-wrap gap-2 mt-1">
        {SEGMENTS.map((s) => (
          <button
            key={s}
            onClick={() => settle(s)}
            className="rounded-md border border-dark-border px-3 py-1.5 text-caption text-text-secondary hover:border-accent hover:text-text-primary transition-colors"
          >
            {t(`scorecard.segmentPrompt.options.${s}`)}
          </button>
        ))}
      </div>
    </Modal>
  );
}
