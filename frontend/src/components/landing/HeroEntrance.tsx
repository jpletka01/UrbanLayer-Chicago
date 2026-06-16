import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AddressInput } from "../AddressInput";
import { PromptSuggestionChip } from "../PromptSuggestionChip";
import { buildScorecardHref } from "../sidebar/ScorecardBridgeCard";
import { track } from "../../lib/tracking";

/**
 * The homepage entry surface. It asks one question — "Which property?" — and
 * opens the parcel's Scorecard. There is no chat box on the front door: code
 * research reaches the analyst elsewhere (Investigate from inside a parcel, the
 * persona cards, or the address box's failure-recovery handoff on a non-address).
 */
export function HeroEntrance() {
  const { t } = useTranslation("landing");
  const navigate = useNavigate();

  function submitAddress(address: string, source: "hero" | "chip") {
    track("hero_address_submit", { source, address });
    navigate(buildScorecardHref(null, address)!);
  }

  const addressExamples = t("hero.addressExamples", { returnObjects: true }) as string[];

  return (
    <div className="space-y-4">
      <AddressInput
        onSubmit={(addr) => submitAddress(addr, "hero")}
        placeholder={t("hero.addressPlaceholder")}
      />
      <div className="flex flex-wrap gap-2 justify-center items-center">
        <span className="text-sm text-white/50">{t("hero.try")}</span>
        {addressExamples.map((addr) => (
          <PromptSuggestionChip key={addr} label={addr} onClick={() => submitAddress(addr, "chip")} />
        ))}
      </div>
    </div>
  );
}
