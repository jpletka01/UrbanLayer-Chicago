import { useEffect, useRef } from "react";
import type { ActivityItem, ContextObject, DataSource, Message } from "../lib/types";
import { ChatInput, type PendingAttachment } from "./ChatInput";
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
  onNewChat?: () => void;
  attachments?: PendingAttachment[];
  onAttach?: (files: File[]) => void;
  onRemoveAttachment?: (index: number) => void;
  activities?: ActivityItem[];
  readOnly?: boolean;
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
  onNewChat,
  attachments,
  onAttach,
  onRemoveAttachment,
  activities,
  readOnly,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streaming]);

  return (
    <section className="flex-1 min-w-0 h-full flex flex-col bg-dark-bg">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-3 md:px-6 py-4 md:py-8 space-y-6">
          {messages.map((m, i) => {
            const isLastAssistant = m.role === "assistant" && i === messages.length - 1;
            const isStreaming = isLastAssistant && streaming;
            const messageContext = isStreaming ? streamingContext : m.context;
            const codeChunks = messageContext?.code_chunks ?? [];
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
              />
            );
          })}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="shrink-0 bg-dark-bg">
        <div className="max-w-3xl mx-auto px-3 md:px-6 py-3 md:py-4">
          {readOnly ? (
            <div className="text-center py-3 text-text-muted text-sm">
              This is a shared conversation — read only
            </div>
          ) : atMessageLimit ? (
            <div className="text-center py-3 text-text-muted text-sm">
              You've reached the 10-message limit for this conversation.{" "}
              <button
                onClick={onNewChat}
                className="text-blue-400 hover:text-blue-300 hover:underline transition-colors"
              >
                Start a new conversation
              </button>
            </div>
          ) : (
            <ChatInput
              onSubmit={onSubmit}
              disabled={streaming}
              variant="compact"
              placeholder="Ask a follow-up..."
              attachments={attachments}
              onAttach={onAttach}
              onRemoveAttachment={onRemoveAttachment}
            />
          )}
        </div>
      </div>
    </section>
  );
}
