import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ActivityItem, ContextObject, DataSource, Message, ScorecardContext, SidebarView } from "../lib/types";
import { propertyStarterKeys } from "../lib/scorecardContext";
import { ChatInput, type PendingAttachment } from "./ChatInput";
import { ContextChipStrip } from "./ContextChipStrip";
import { MessageBubble } from "./MessageBubble";

interface Props {
  messages: Message[];
  streaming: boolean;
  showDisclaimer: boolean;
  onSubmit: (message: string) => void;
  onCitationClick?: (index: number, messageContext?: ContextObject) => void;
  onDataClick?: (source: DataSource, messageContext?: ContextObject) => void;
  streamingContext?: ContextObject | null;
  onMessageClick?: (messageIndex: number) => void;
  selectedMessageIndex?: number | null;
  atMessageLimit?: boolean;
  /** Turns left before the per-conversation cap — surfaced near the composer
   *  from 2 remaining so the limit never lands as a surprise dead-end. */
  messagesRemaining?: number;
  onNewChat?: () => void;
  attachments?: PendingAttachment[];
  onAttach?: (files: File[]) => void;
  onRemoveAttachment?: (index: number) => void;
  activities?: ActivityItem[];
  readOnly?: boolean;
  // When the workspace was entered for a held parcel, the empty state becomes a
  // grounded "Ask about this property" surface: flag-aware starters that send
  // WITH the pin + grounding (the obvious path is the grounded one). Raw typing
  // stays available but is the secondary, ungrounded fallback.
  propertyContext?: ScorecardContext | null;
  onPropertyStarterClick?: (question: string) => void;
  /** Open the side panel / mobile sheet on a tab, loading the given assistant
   *  message's turn (per-message context chips under each answer). */
  onOpenPanel?: (assistantIndex: number, tab: SidebarView) => void;
}

export function ChatInterface({
  messages,
  streaming,
  showDisclaimer,
  onSubmit,
  onCitationClick,
  onDataClick,
  streamingContext,
  onMessageClick,
  selectedMessageIndex,
  atMessageLimit,
  messagesRemaining,
  onNewChat,
  attachments,
  onAttach,
  onRemoveAttachment,
  activities,
  readOnly,
  propertyContext,
  onPropertyStarterClick,
  onOpenPanel,
}: Props) {
  const { t } = useTranslation(["common", "chat"]);
  const bottomRef = useRef<HTMLDivElement>(null);
  // Seeds the composer when an empty-state example chip is clicked (fill, no send).
  const [composerSeed, setComposerSeed] = useState<string | undefined>(undefined);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streaming]);

  // The fresh "New Chat" surface: no messages, not streaming, not a shared/read-only
  // view, and not blocked at the message limit. Reads as ready, not broken.
  const showEmptyState = messages.length === 0 && !streaming && !readOnly && !atMessageLimit;

  // Grounded variant: entered for a parcel → property-specific, flag-aware
  // starters (priority-ordered + capped in propertyStarterKeys — notable flags
  // like a CHRS demolition-review rating or heavy street traffic claim a slot
  // only when the data backs them, so we never offer a dead-end prompt).
  const grounded = showEmptyState && !!propertyContext;
  const propertyStarters: string[] = grounded
    ? propertyStarterKeys(propertyContext).map((k) => t(`chat:propertyStarters.${k}`))
    : [];

  const examples = grounded
    ? propertyStarters
    : (t("chat:emptyState.examples", { returnObjects: true }) as string[]);
  const emptyHeading = grounded ? t("chat:propertyStarters.heading") : t("chat:emptyState.heading");
  const emptySubline = grounded
    ? propertyContext?.address
      ? t("chat:propertyStarters.sublineWithAddress", { address: propertyContext.address })
      : t("chat:propertyStarters.subline")
    : t("chat:emptyState.subline");

  return (
    <section className="flex-1 min-w-0 h-full flex flex-col bg-dark-bg">
      <div className="flex-1 overflow-y-auto">
        {showEmptyState ? (
          <div className="h-full flex flex-col items-center justify-center px-6 text-center">
            <div className="w-12 h-12 rounded-xl bg-accent/15 flex items-center justify-center text-accent mb-4">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-text-primary mb-1.5">{emptyHeading}</h2>
            <p className="text-sm text-text-secondary max-w-md mb-5 leading-relaxed">{emptySubline}</p>
            <div className="flex flex-wrap gap-2 justify-center max-w-lg">
              {examples.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => (grounded ? onPropertyStarterClick?.(q) : setComposerSeed(q))}
                  className="text-xs text-text-secondary bg-dark-surface border border-dark-border rounded-lg px-3 py-1.5 hover:border-accent/40 hover:text-text-primary transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
        <div className="max-w-3xl mx-auto px-3 md:px-6 py-4 md:py-8 space-y-6">
          {messages.map((m, i) => {
            const isLastAssistant = m.role === "assistant" && i === messages.length - 1;
            const isStreaming = isLastAssistant && streaming;
            const messageContext = isStreaming ? streamingContext : m.context;
            const codeChunks = messageContext?.code_chunks ?? [];
            const showChips = m.role === "assistant" && !isStreaming && !readOnly && !!onOpenPanel;
            return (
              <MessageBubble
                key={i}
                message={m}
                streaming={isStreaming}
                showDisclaimer={
                  m.role === "assistant" && i === messages.length - 1 && showDisclaimer && !streaming
                }
                onCitationClick={(idx) => onCitationClick?.(idx, messageContext ?? undefined)}
                onDataClick={(source) => onDataClick?.(source, messageContext ?? undefined)}
                codeChunks={codeChunks}
                isSelected={m.role === "user" && selectedMessageIndex === i}
                onSelect={m.role === "user" ? () => onMessageClick?.(i) : undefined}
                activities={isStreaming ? activities : undefined}
                footer={
                  showChips ? (
                    <ContextChipStrip
                      context={m.context ?? null}
                      mapData={m.mapData ?? null}
                      onOpen={(tab) => onOpenPanel!(i, tab)}
                    />
                  ) : undefined
                }
              />
            );
          })}
          <div ref={bottomRef} />
        </div>
        )}
      </div>

      <div className="shrink-0 bg-dark-bg">
        <div className="max-w-3xl mx-auto px-3 md:px-6 py-3 md:py-4">
          {readOnly ? (
            <div className="text-center py-3 text-text-muted text-sm">
              {t("sharedConversation")}
            </div>
          ) : atMessageLimit ? (
            <div className="text-center py-3 text-text-muted text-sm">
              {t("messageLimitReached")}{" "}
              <button
                onClick={onNewChat}
                className="text-accent hover:text-accent-hover hover:underline transition-colors"
              >
                {t("startNewConversation")}
              </button>
            </div>
          ) : (
            <>
              {messagesRemaining != null && messagesRemaining <= 2 && messagesRemaining > 0 && (
                <p className="text-caption text-text-muted text-center pb-2">
                  {t("questionsLeft", { count: messagesRemaining })}{" "}
                  <button
                    onClick={onNewChat}
                    className="text-accent hover:text-accent-hover hover:underline transition-colors"
                  >
                    {t("startNewConversation")}
                  </button>
                </p>
              )}
              <ChatInput
                onSubmit={onSubmit}
                disabled={streaming}
                variant="compact"
                placeholder={
                  // A fresh conversation has nothing to "follow up" on yet.
                  messages.length === 0 ? t("chat:placeholder") : t("followUpPlaceholder")
                }
                initialValue={composerSeed}
                attachments={attachments}
                onAttach={onAttach}
                onRemoveAttachment={onRemoveAttachment}
              />
            </>
          )}
        </div>
      </div>
    </section>
  );
}
