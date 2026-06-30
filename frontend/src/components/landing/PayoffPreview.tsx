import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { track } from "../../lib/tracking";

// Static, illustrative payoff preview for the empty-state Home: it shows that an
// address returns a VERDICT (a conclusion), not a data dump — mirroring the real
// VerdictBand's visual language. Subordinate to the address box (the primary
// action); this is the quiet "or see a real one" path beside it.
//
// The example mirrors the LIVE 1601 N Milwaukee result (Constrained upside, B3-2
// FAR 2.2, landmark). It reuses the actual verdict i18n strings (pages namespace)
// so the preview can never drift from what the Scorecard shows — and the labeled
// click-through lands on that real Scorecard, so the promise is verifiable, not
// just asserted (the product's "we conclude, you can verify" thesis, on Home).
const EXAMPLE_ADDRESS = "1601 N Milwaukee Ave";

const WarningGlyph = () => (
  <svg className="mt-0.5 h-3.5 w-3.5 shrink-0 text-state-warning" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
  </svg>
);

export function PayoffPreview() {
  const { t } = useTranslation(["landing", "pages"]);
  const navigate = useNavigate();

  function seeScorecard() {
    track("hero_address_submit", { source: "preview", address: EXAMPLE_ADDRESS });
    navigate(`/scorecard?address=${encodeURIComponent(EXAMPLE_ADDRESS)}`);
  }

  return (
    <div className="mx-auto max-w-sm space-y-2">
      <p className="text-center text-caption text-white/50">{t("payoff.label")}</p>
      {/* Mini verdict card — same conclusion-first shape as VerdictBand, no CTA */}
      <div className="rounded-xl border border-white/15 border-l-4 border-l-state-warning bg-dark-surface/70 p-4 text-left backdrop-blur-sm">
        <p className="text-caption text-white/60">{EXAMPLE_ADDRESS}</p>
        <p className="mt-0.5 text-lead text-white">{t("scorecard.verdict.headline.constrained", { ns: "pages" })}</p>
        <ul className="mt-2 space-y-1">
          <li className="flex items-start gap-2 text-caption text-white/70">
            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-white/40" aria-hidden />
            {t("scorecard.verdict.reason.asOfRight", { ns: "pages", zone: "B3-2", allowed: "2.2" })}
          </li>
          <li className="flex items-start gap-2 text-caption text-white/70">
            <WarningGlyph />
            {t("scorecard.verdict.reason.landmark", { ns: "pages" })}
          </li>
        </ul>
      </div>
      {/* Labeled click-through — a quiet bonus path, not a competing CTA */}
      <p className="text-center">
        <button
          type="button"
          onClick={seeScorecard}
          className="text-caption text-white/80 underline underline-offset-2 transition-colors hover:text-white"
        >
          {t("payoff.cta")} →
        </button>
      </p>
    </div>
  );
}
