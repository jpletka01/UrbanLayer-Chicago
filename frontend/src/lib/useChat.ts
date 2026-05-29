import { useRef, useState } from "react";
import { chatStream } from "./api";
import type { ContextObject, Message, RetrievalPlan } from "./types";

interface UseChatOptions {
  // Fired when the server emits the retrieved context for a turn. Lets the host
  // drive sidebar/UI reactions without the hook knowing about them.
  onContext?: (context: ContextObject) => void;
}

interface UseChat {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  streaming: boolean;
  plan: RetrievalPlan | null;
  context: ContextObject | null;
  showDisclaimer: boolean;
  errorMsg: string | null;
  sendMessage: (text: string) => Promise<void>;
  /** Clear the current turn's plan/context/error/disclaimer (keeps messages). */
  clearTurnState: () => void;
  /** Abort any in-flight stream and clear all chat state including messages. */
  reset: () => void;
}

/**
 * Owns a single chat exchange: the SSE consumption loop, streamed message
 * accumulation, and the plan/context/error/disclaimer state for the turn.
 * Sidebar and conversation-history concerns stay with the host component.
 */
export function useChat({ onContext }: UseChatOptions = {}): UseChat {
  const [messages, setMessages] = useState<Message[]>([]);
  const [plan, setPlan] = useState<RetrievalPlan | null>(null);
  const [context, setContext] = useState<ContextObject | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const pendingContextRef = useRef<ContextObject | null>(null);

  function clearTurnState() {
    setPlan(null);
    setContext(null);
    setShowDisclaimer(false);
    setErrorMsg(null);
  }

  function reset() {
    abortRef.current?.abort();
    setMessages([]);
    clearTurnState();
  }

  async function sendMessage(text: string) {
    if (streaming) return;
    clearTurnState();

    const userMessage: Message = { role: "user", content: text };
    const historySnapshot = [...messages];
    setMessages((m) => [...m, userMessage, { role: "assistant", content: "" }]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const chunk of chatStream(text, historySnapshot, controller.signal)) {
        if (chunk.type === "plan") {
          setPlan(chunk.plan);
        } else if (chunk.type === "context") {
          setContext(chunk.context);
          pendingContextRef.current = chunk.context;
          if (chunk.context.requires_disclaimer) setShowDisclaimer(true);
          onContext?.(chunk.context);
        } else if (chunk.type === "token") {
          setMessages((m) => {
            const next = [...m];
            const last = next[next.length - 1];
            if (last && last.role === "assistant") {
              next[next.length - 1] = { ...last, content: last.content + chunk.text };
            }
            return next;
          });
        } else if (chunk.type === "done") {
          // Attach context to the assistant message for per-message citation binding
          if (pendingContextRef.current) {
            setMessages((m) => {
              const next = [...m];
              const last = next[next.length - 1];
              if (last?.role === "assistant") {
                next[next.length - 1] = { ...last, context: pendingContextRef.current! };
              }
              return next;
            });
          }
        } else if (chunk.type === "error") {
          setErrorMsg(chunk.error);
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        console.error(err);
        setErrorMsg((err as Error).message);
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  return {
    messages,
    setMessages,
    streaming,
    plan,
    context,
    showDisclaimer,
    errorMsg,
    sendMessage,
    clearTurnState,
    reset,
  };
}
