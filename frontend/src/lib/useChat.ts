import { useRef, useState } from "react";
import { chatStream } from "./api";
import type { ContextObject, MapData, Message, RetrievalPlan, UploadMeta } from "./types";

const MESSAGE_LIMIT = 10;

interface UseChatOptions {
  onContext?: (context: ContextObject) => void;
  onPlan?: (plan: RetrievalPlan) => void;
  onMapData?: (mapData: MapData) => void;
  conversationId?: string | null;
}

interface UseChat {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  streaming: boolean;
  plan: RetrievalPlan | null;
  context: ContextObject | null;
  showDisclaimer: boolean;
  errorMsg: string | null;
  atMessageLimit: boolean;
  sendMessage: (text: string, attachments?: UploadMeta[]) => Promise<void>;
  clearTurnState: () => void;
  reset: () => void;
}

export function useChat({
  onContext,
  onPlan,
  onMapData,
  conversationId,
}: UseChatOptions = {}): UseChat {
  const [messages, setMessages] = useState<Message[]>([]);
  const [plan, setPlan] = useState<RetrievalPlan | null>(null);
  const [context, setContext] = useState<ContextObject | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const pendingContextRef = useRef<ContextObject | null>(null);
  const pendingPlanRef = useRef<RetrievalPlan | null>(null);
  const pendingMapDataRef = useRef<MapData | null>(null);

  const userMessageCount = messages.filter((m) => m.role === "user").length;
  const atMessageLimit = userMessageCount >= MESSAGE_LIMIT;

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

  async function sendMessage(text: string, attachments?: UploadMeta[]) {
    if (streaming) return;

    if (atMessageLimit) {
      setErrorMsg(
        "You've reached the 10-message limit for this conversation. Please start a new chat.",
      );
      return;
    }

    clearTurnState();
    pendingContextRef.current = null;
    pendingPlanRef.current = null;
    pendingMapDataRef.current = null;

    const userMessage: Message = {
      role: "user",
      content: text,
      attachments: attachments?.length ? attachments : undefined,
    };
    const historySnapshot = [...messages];
    setMessages((m) => [...m, userMessage, { role: "assistant", content: "" }]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    const uploadIds = attachments?.map((a) => a.id);

    try {
      for await (const chunk of chatStream(
        text,
        historySnapshot,
        controller.signal,
        conversationId,
        uploadIds,
      )) {
        if (chunk.type === "plan") {
          setPlan(chunk.plan);
          pendingPlanRef.current = chunk.plan;
          onPlan?.(chunk.plan);
        } else if (chunk.type === "context") {
          setContext(chunk.context);
          pendingContextRef.current = chunk.context;
          if (chunk.context.requires_disclaimer) setShowDisclaimer(true);
          onContext?.(chunk.context);
        } else if (chunk.type === "map_data") {
          pendingMapDataRef.current = chunk.map_data;
          onMapData?.(chunk.map_data);
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
          setMessages((m) => {
            const next = [...m];
            const last = next[next.length - 1];
            if (last?.role === "assistant") {
              next[next.length - 1] = {
                ...last,
                context: pendingContextRef.current ?? undefined,
                plan: pendingPlanRef.current ?? undefined,
                mapData: pendingMapDataRef.current ?? undefined,
                mapFetchedAt: pendingMapDataRef.current ? Date.now() : undefined,
              };
            }
            return next;
          });
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
    atMessageLimit,
    sendMessage,
    clearTurnState,
    reset,
  };
}
