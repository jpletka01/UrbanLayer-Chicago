import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AddressInput } from "../AddressInput";
import { ChatInput } from "../ChatInput";
import { PromptSuggestionChip } from "../PromptSuggestionChip";
import { buildScorecardHref } from "../sidebar/ScorecardBridgeCard";
import { track } from "../../lib/tracking";

interface Props {
  onChatSubmit: (text: string) => void;
  chatPrefill?: string | null;
}

/**
 * The homepage entry surface. Default mode asks one question — "Which
 * property?" — and opens the parcel's Scorecard. The code-research chat
 * (the librarian) is a clearly secondary entrance behind a quiet link.
 */
export function HeroEntrance({ onChatSubmit, chatPrefill }: Props) {
  const { t } = useTranslation("landing");
  const navigate = useNavigate();
  const [mode, setMode] = useState<"address" | "chat">("address");

  // Persona cards prefill a code-research question into the hero chat.
  useEffect(() => {
    if (chatPrefill) setMode("chat");
  }, [chatPrefill]);

  function submitAddress(address: string, source: "hero" | "chip") {
    track("hero_address_submit", { source, address });
    navigate(buildScorecardHref(null, address)!);
  }

  const addressExamples = t("hero.addressExamples", { returnObjects: true }) as string[];
  const librarianSuggestions = t("hero.librarianSuggestions", { returnObjects: true }) as string[];

  if (mode === "chat") {
    return (
      <div className="space-y-4">
        <ChatInput
          onSubmit={onChatSubmit}
          variant="hero"
          placeholder={t("hero.chatPlaceholder")}
          initialValue={chatPrefill ?? undefined}
        />
        <div className="flex flex-wrap gap-2 justify-center">
          {librarianSuggestions.map((q) => (
            <PromptSuggestionChip key={q} label={q} onClick={() => onChatSubmit(q)} />
          ))}
        </div>
        <button
          type="button"
          onClick={() => setMode("address")}
          className="text-sm text-white/60 hover:text-white transition-colors"
        >
          {t("hero.backToAddress")}
        </button>
      </div>
    );
  }

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
      <button
        type="button"
        onClick={() => {
          track("hero_librarian_click", { source: "hero" });
          setMode("chat");
        }}
        className="text-sm text-white/60 hover:text-white transition-colors"
      >
        {t("hero.librarianLink")}
      </button>
    </div>
  );
}
