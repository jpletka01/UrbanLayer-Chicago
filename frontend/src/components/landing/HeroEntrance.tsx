import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AddressInput } from "../AddressInput";
import { PromptSuggestionChip } from "../PromptSuggestionChip";
import { buildScorecardHref } from "../sidebar/ScorecardBridgeCard";
import { track } from "../../lib/tracking";

/**
 * The homepage entry surface. The primary action asks one question — "Which
 * property?" — and opens the parcel's Scorecard. Below it, a quiet, LABELED
 * secondary door routes the other intent (code/neighborhood research, no parcel
 * yet) to the analyst — so the fork is discoverable, not a hidden side door.
 */
export function HeroEntrance() {
  const { t } = useTranslation("landing");
  const navigate = useNavigate();

  function submitAddress(address: string, source: "hero" | "chip") {
    track("hero_address_submit", { source, address });
    navigate(buildScorecardHref(null, address)!);
  }

  // The labeled chat door: opens an empty, ungrounded analyst chat (?ask=1) — no
  // parcel named here, so it carries no grounding (App.tsx clears it on open).
  function openAnalyst() {
    track("hero_librarian_click");
    navigate("/?ask=1");
  }

  const addressExamples = t("hero.addressExamples", { returnObjects: true }) as string[];

  return (
    <div className="space-y-4">
      <AddressInput
        onSubmit={(addr) => submitAddress(addr, "hero")}
        placeholder={t("hero.addressPlaceholder")}
      />
      <div className="flex flex-wrap gap-2 justify-center items-center">
        <span className="text-body text-white/50">{t("hero.try")}</span>
        {addressExamples.map((addr) => (
          <PromptSuggestionChip key={addr} label={addr} onClick={() => submitAddress(addr, "chip")} />
        ))}
      </div>
      {/* Secondary, labeled door — subordinate to the address input, names the
          fork (code/neighborhood research) so a returning user knows what it does. */}
      <p className="text-body text-white/50">
        {t("hero.askAnalystLead")}{" "}
        <button
          type="button"
          onClick={openAnalyst}
          className="text-white/80 hover:text-white underline underline-offset-2 transition-colors"
        >
          {t("hero.askAnalystCta")} →
        </button>
      </p>
    </div>
  );
}
