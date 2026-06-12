import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChatStreamError, chatStream } from "./api";
import type {
  ActivityItem,
  ContextObject,
  MapData,
  Message,
  RetrievalPlan,
  SourceTag,
  TurnSummary,
  UploadMeta,
} from "./types";

const MESSAGE_LIMIT = 10;

type TFn = (key: string, opts?: Record<string, unknown>) => string;

function getSourceLabel(source: SourceTag, t: TFn): string {
  return t(`chat:sourceLabels.${source}`, { defaultValue: source });
}

function deriveActivitiesFromPlan(plan: RetrievalPlan, t: TFn): ActivityItem[] {
  const area = plan.location.resolved_community_area_name;
  const addr = plan.location.resolved_address;
  const items: ActivityItem[] = [];

  if (area) {
    items.push({ id: "location", label: t("chat:located", { area }), status: "done" });
  }

  for (const source of plan.sources) {
    let label = getSourceLabel(source, t);
    if (source === "vector_search" && plan.search_query) {
      const q =
        plan.search_query.length > 50
          ? plan.search_query.slice(0, 47) + "..."
          : plan.search_query;
      label = t("chat:searchingFor", { query: q });
    } else if (source === "property_domain" && addr) {
      label = t("chat:propertyFor", { address: addr });
    } else if (area && source !== "vector_search") {
      label = t("chat:inArea", { label, area });
    }
    items.push({ id: `retrieve_${source}`, label, status: "active" });
  }

  return items;
}

interface UseChatOptions {
  onContext?: (context: ContextObject) => void;
  onPlan?: (plan: RetrievalPlan) => void;
  onMapData?: (mapData: MapData) => void;
  conversationId?: string | null;
  language?: string;
}

interface UseChat {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  streaming: boolean;
  plan: RetrievalPlan | null;
  context: ContextObject | null;
  showDisclaimer: boolean;
  errorMsg: string | null;
  rateLimited: boolean;
  atMessageLimit: boolean;
  activities: ActivityItem[];
  sendMessage: (text: string, attachments?: UploadMeta[]) => Promise<void>;
  clearTurnState: () => void;
  reset: () => void;
}

export function useChat({
  onContext,
  onPlan,
  onMapData,
  conversationId,
  language,
}: UseChatOptions = {}): UseChat {
  const { t } = useTranslation(["chat", "common"]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [plan, setPlan] = useState<RetrievalPlan | null>(null);
  const [context, setContext] = useState<ContextObject | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [rateLimited, setRateLimited] = useState(false);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const pendingContextRef = useRef<ContextObject | null>(null);
  const pendingPlanRef = useRef<RetrievalPlan | null>(null);
  const pendingMapDataRef = useRef<MapData | null>(null);
  const pendingTurnSummaryRef = useRef<TurnSummary | null>(null);
  const hasTokenRef = useRef(false);
  const cachedMapRef = useRef<{ communityArea: number; mapData: MapData } | null>(null);

  const userMessageCount = messages.filter((m) => m.role === "user").length;
  const atMessageLimit = userMessageCount >= MESSAGE_LIMIT;

  function clearTurnState() {
    setPlan(null);
    setContext(null);
    setShowDisclaimer(false);
    setErrorMsg(null);
    setRateLimited(false);
    setActivities([]);
  }

  function reset() {
    abortRef.current?.abort();
    setMessages([]);
    clearTurnState();
  }

  async function sendMessage(text: string, attachments?: UploadMeta[]) {
    if (streaming) return;

    if (atMessageLimit) {
      setErrorMsg(t("common:messageLimit"));
      return;
    }

    clearTurnState();
    pendingContextRef.current = null;
    pendingPlanRef.current = null;
    pendingMapDataRef.current = null;
    pendingTurnSummaryRef.current = null;
    hasTokenRef.current = false;

    setActivities([
      { id: "routing", label: t("chat:analyzing"), status: "active" },
    ]);

    const userMessage: Message = {
      role: "user",
      content: text,
      attachments: attachments?.length ? attachments : undefined,
    };
    const historySnapshot = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, userMessage, { role: "assistant", content: "" }]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    const uploadIds = attachments?.map((a) => a.id);

    let receivedDone = false;
    let streamErrored = false;

    try {
      for await (const chunk of chatStream(
        text,
        historySnapshot,
        controller.signal,
        conversationId,
        uploadIds,
        cachedMapRef.current?.communityArea ?? null,
        language,
      )) {
        if (chunk.type === "plan") {
          setPlan(chunk.plan);
          pendingPlanRef.current = chunk.plan;
          onPlan?.(chunk.plan);

          const planActivities = deriveActivitiesFromPlan(chunk.plan, t);
          setActivities([
            { id: "routing", label: t("chat:analyzed"), status: "done" },
            ...planActivities,
          ]);
        } else if (chunk.type === "context") {
          setContext(chunk.context);
          pendingContextRef.current = chunk.context;
          if (chunk.context.requires_disclaimer) setShowDisclaimer(true);
          onContext?.(chunk.context);

          setActivities((prev) => [
            ...prev.map((a) => ({ ...a, status: "done" as const })),
            { id: "synthesis", label: t("chat:composing"), status: "active" },
          ]);
        } else if (chunk.type === "map_data") {
          let mapData = chunk.map_data;
          if (mapData) {
            const cached = cachedMapRef.current;
            if (cached && !mapData.zoning && cached.mapData.zoning) {
              mapData = { ...mapData, zoning: cached.mapData.zoning };
            }
            if (cached && !mapData.overlay_districts && cached.mapData.overlay_districts) {
              mapData = { ...mapData, overlay_districts: cached.mapData.overlay_districts };
            }
            if (cached && !mapData.incentive_zones && cached.mapData.incentive_zones) {
              mapData = { ...mapData, incentive_zones: cached.mapData.incentive_zones };
            }
          }
          pendingMapDataRef.current = mapData;
          onMapData?.(mapData!);
        } else if (chunk.type === "token") {
          if (!hasTokenRef.current) {
            hasTokenRef.current = true;
            setActivities((prev) =>
              prev.map((a) => ({ ...a, status: "done" as const })),
            );
          }
          setMessages((m) => {
            const next = [...m];
            const last = next[next.length - 1];
            if (last && last.role === "assistant") {
              next[next.length - 1] = { ...last, content: last.content + chunk.text };
            }
            return next;
          });
        } else if (chunk.type === "turn_summary") {
          pendingTurnSummaryRef.current = chunk.turn_summary;
        } else if (chunk.type === "done") {
          receivedDone = true;
          if (chunk.timings) {
            console.log("[perf] pipeline timings (ms):", chunk.timings);
          }
          const md = pendingMapDataRef.current;
          const ca = pendingPlanRef.current?.location?.resolved_community_area;
          if (md && ca != null) {
            cachedMapRef.current = { communityArea: ca, mapData: md };
          }
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
                turnSummary: pendingTurnSummaryRef.current ?? undefined,
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
        streamErrored = true;
        if (err instanceof ChatStreamError) {
          setErrorMsg(err.detail ?? t("common:connectionLost"));
          setRateLimited(err.status === 429);
        } else {
          setErrorMsg((err as Error).message);
        }
        // The request failed before any token arrived: drop the optimistic
        // empty assistant bubble so the error banner sits under the question.
        if (!hasTokenRef.current) {
          setMessages((m) =>
            m[m.length - 1]?.role === "assistant" && m[m.length - 1].content === ""
              ? m.slice(0, -1)
              : m,
          );
        }
      }
    } finally {
      if (!receivedDone && !controller.signal.aborted && !streamErrored) {
        setErrorMsg(t("common:connectionLost"));
      }
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
    rateLimited,
    atMessageLimit,
    activities,
    sendMessage,
    clearTurnState,
    reset,
  };
}
