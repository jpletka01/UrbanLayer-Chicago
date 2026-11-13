// The Profile's grounded quick chat, shared by today's MiniChatDock and the new UI's Ask drawer (decision
// Item 76: a component becomes shared on its second use). One `useChat` instance grounded on the loaded parcel
// for EVERY turn (pin + scorecard_context), questions that carry the address (a deictic "this lot" routes to
// clarification before grounding is read), and "open in full chat" in a NEW tab with the transcript handed over
// through a one-time id. Behavior is exactly the dock's; only its home moved.
import { useEffect, useMemo, useState } from "react";
import type { ScorecardResponse } from "./api";
import { buildScorecardContext, propertyStarterKeys } from "./scorecardContext";
import { useChat } from "./useChat";
import { track } from "./tracking";
import { openInNewTab, takeHandoff, writeHandoff } from "./openInNewTab";

/** `data` is null while the new Profile shows its first screen (Item 82): nothing is grounded and the page
    offers no ask until the full response arrives. */
export function useParcelChat(data: ScorecardResponse | null, language: string) {
  const [tabBlocked, setTabBlocked] = useState(false);
  const grounding = useMemo(() => buildScorecardContext(data), [data]);
  const address = data?.address ?? grounding?.address ?? null;
  const chat = useChat({ language });
  const { messages, streaming, atQuota, sendMessage, setGrounding } = chat;

  // Grounding rides every turn — the same conversation-sticky model as the workspace handoff.
  useEffect(() => {
    setGrounding(grounding);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [grounding]);

  const ask = (question: string) => {
    const q = question.trim();
    if (!q || streaming || atQuota) return;
    const text = address && !q.includes(address) ? `${q} — ${address}` : q;
    sendMessage(text, undefined, {
      parcelPin: grounding?.pin ?? null,
      scorecardContext: grounding,
    });
  };

  const starterKeys = useMemo(() => propertyStarterKeys(grounding), [grounding]);

  /** Continue in the full chat, in a new tab; a blocked tab keeps the page and says so. */
  const escalate = (cardName = "dock_escalate") => {
    track("investigate_click", { card_name: cardName });
    const id = writeHandoff(messages.filter((m) => m.content).map((m) => ({ role: m.role, content: m.content })));
    const params = new URLSearchParams(grounding?.pin ? { pin: grounding.pin } : { ask: "1" });
    if (id) params.set("handoff", id);
    const opened = openInNewTab(`/?${params}`);
    if (!opened && id) takeHandoff(id);
    setTabBlocked(!opened);
  };

  return { ...chat, grounding, address, ask, starterKeys, escalate, tabBlocked };
}
