import { useEffect, useRef } from "react";
import type { Message } from "../lib/types";
import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";

interface Props {
  messages: Message[];
  streaming: boolean;
  showDisclaimer: boolean;
  onSubmit: (message: string) => void;
}

export function ChatInterface({ messages, streaming, showDisclaimer, onSubmit }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streaming]);

  return (
    <section className="w-full md:w-3/5 h-full flex flex-col bg-slate-50">
      <div className="flex-1 overflow-y-auto px-6 py-8 space-y-5">
        {messages.map((m, i) => {
          const isLastAssistant =
            m.role === "assistant" && i === messages.length - 1;
          return (
            <MessageBubble
              key={i}
              message={m}
              streaming={isLastAssistant && streaming}
              showDisclaimer={
                m.role === "assistant" && i === messages.length - 1 && showDisclaimer && !streaming
              }
            />
          );
        })}
        <div ref={bottomRef} />
      </div>
      <div className="border-t border-slate-200 bg-white px-6 py-4">
        <ChatInput
          onSubmit={onSubmit}
          disabled={streaming}
          variant="compact"
          placeholder="Ask a follow-up..."
        />
      </div>
    </section>
  );
}
