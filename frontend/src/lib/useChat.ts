import { useRef, useState } from "react";
import { chatStream } from "./api";
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

const SOURCE_LABELS: Record<SourceTag, string> = {
  crime_api: "Searching crime records",
  "311_api": "Looking up 311 service requests",
  permits_api: "Checking building permits",
  violations_api: "Pulling building violations",
  business_api: "Searching business licenses",
  vacant_buildings_api: "Checking vacant building reports",
  food_inspections_api: "Loading food inspection records",
  vector_search: "Searching municipal code",
  regulatory_domain: "Checking zoning & regulatory overlays",
  property_domain: "Looking up property records",
  incentives_domain: "Checking TIF & incentive zones",
  neighborhood_domain: "Loading demographics, census data & transit",
};

function deriveActivitiesFromPlan(plan: RetrievalPlan): ActivityItem[] {
  const area = plan.location.resolved_community_area_name;
  const addr = plan.location.resolved_address;
  const items: ActivityItem[] = [];

  if (area) {
    items.push({ id: "location", label: `Located ${area}`, status: "done" });
  }

  for (const source of plan.sources) {
    let label = SOURCE_LABELS[source] ?? source;
    if (source === "vector_search" && plan.search_query) {
      const q =
        plan.search_query.length > 50
          ? plan.search_query.slice(0, 47) + "..."
          : plan.search_query;
      label = `Searching municipal code for "${q}"`;
    } else if (source === "property_domain" && addr) {
      label += ` for ${addr}`;
    } else if (area && source !== "vector_search") {
      label += ` in ${area}`;
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
}: UseChatOptions = {}): UseChat {
  const [messages, setMessages] = useState<Message[]>([]);
  const [plan, setPlan] = useState<RetrievalPlan | null>(null);
  const [context, setContext] = useState<ContextObject | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const pendingContextRef = useRef<ContextObject | null>(null);
  const pendingPlanRef = useRef<RetrievalPlan | null>(null);
  const pendingMapDataRef = useRef<MapData | null>(null);
  const pendingTurnSummaryRef = useRef<TurnSummary | null>(null);
  const hasTokenRef = useRef(false);

  const userMessageCount = messages.filter((m) => m.role === "user").length;
  const atMessageLimit = userMessageCount >= MESSAGE_LIMIT;

  function clearTurnState() {
    setPlan(null);
    setContext(null);
    setShowDisclaimer(false);
    setErrorMsg(null);
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
      setErrorMsg(
        "You've reached the 10-message limit for this conversation. Please start a new chat.",
      );
      return;
    }

    clearTurnState();
    pendingContextRef.current = null;
    pendingPlanRef.current = null;
    pendingMapDataRef.current = null;
    pendingTurnSummaryRef.current = null;
    hasTokenRef.current = false;

    setActivities([
      { id: "routing", label: "Analyzing your question…", status: "active" },
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

          const planActivities = deriveActivitiesFromPlan(chunk.plan);
          setActivities([
            { id: "routing", label: "Analyzed your question", status: "done" },
            ...planActivities,
          ]);
        } else if (chunk.type === "context") {
          setContext(chunk.context);
          pendingContextRef.current = chunk.context;
          if (chunk.context.requires_disclaimer) setShowDisclaimer(true);
          onContext?.(chunk.context);

          setActivities((prev) => [
            ...prev.map((a) => ({ ...a, status: "done" as const })),
            { id: "synthesis", label: "Composing response…", status: "active" },
          ]);
        } else if (chunk.type === "map_data") {
          pendingMapDataRef.current = chunk.map_data;
          onMapData?.(chunk.map_data);
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
        setErrorMsg((err as Error).message);
      }
    } finally {
      if (!receivedDone && !controller.signal.aborted) {
        setErrorMsg("Connection lost — please try again.");
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
    atMessageLimit,
    activities,
    sendMessage,
    clearTurnState,
    reset,
  };
}
