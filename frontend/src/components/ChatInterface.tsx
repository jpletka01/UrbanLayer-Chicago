import { motion } from "motion/react";
import { useEffect, useRef, type ReactNode } from "react";
import type { CodeChunk, ContextObject, Message } from "../lib/types";
import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";

interface Props {
  messages: Message[];
  streaming: boolean;
  showDisclaimer: boolean;
  onSubmit: (message: string) => void;
  isSidebarOpen: boolean;
  onCitationClick?: (index: number, messageContext?: ContextObject) => void;
  streamingContext?: ContextObject | null;
  children?: ReactNode;
}

export function ChatInterface({
  messages,
  streaming,
  showDisclaimer,
  onSubmit,
  isSidebarOpen,
  onCitationClick,
  streamingContext,
  children,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streaming]);

  return (
    <motion.section
      initial={false}
      animate={{
        width: isSidebarOpen ? "60%" : "100%",
      }}
      transition={{ duration: 0.3, ease: "easeInOut" }}
      className="h-full flex flex-col bg-dark-bg relative"
    >
      {children}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
          {messages.map((m, i) => {
            const isLastAssistant = m.role === "assistant" && i === messages.length - 1;
            const isStreaming = isLastAssistant && streaming;
            // Use message's own context, or streaming context for the currently streaming message
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
                codeChunks={codeChunks}
              />
            );
          })}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="shrink-0 bg-dark-bg">
        <div className="max-w-3xl mx-auto px-6 py-4">
          <ChatInput
            onSubmit={onSubmit}
            disabled={streaming}
            variant="compact"
            placeholder="Ask a follow-up..."
          />
        </div>
      </div>
    </motion.section>
  );
}
