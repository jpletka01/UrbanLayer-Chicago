import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChatStreamError, chatStream } from "./api";
import type {
  ActivityItem,
  ContextObject,
  MapData,
  Message,
  RetrievalPlan,
  ScorecardContext,
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
  /** Turns left before the per-conversation cap (MESSAGE_LIMIT - sent). */
  messagesRemaining: number;
  activities: ActivityItem[];
  sendMessage: (
    text: string,
    attachments?: UploadMeta[],
    opts?: { parcelPin?: string | null; scorecardContext?: ScorecardContext | null },
  ) => Promise<void>;
  clearTurnState: () => void;
  reset: () => void;
  /** True when the last turn failed in a way a resend can fix (not a rate or message limit). */
  canRetry: boolean;
  /** Resend the failed turn's question: its bubble and any partial answer are replaced, not duplicated. */
  retry: () => void;
  // Set the conversation's active parcel grounding (attached to every turn).
  setGrounding: (ctx: ScorecardContext | null) => void;
}

type SendOpts = { parcelPin?: string | null; scorecardContext?: ScorecardContext | null };

/** The words for a failed turn: the step that failed, or that chat itself is out (decision Item 72). An older
 *  backend sends no step, so its own text stands. */
export function turnErrorText(
  chunk: { error: string; error_step?: string; error_kind?: string },
  t: (key: string) => string,
): string {
  if (chunk.error === "MESSAGE_LIMIT_REACHED") return t("common:messageLimit");
  if (chunk.error_kind === "unavailable") return t("chat:turnError.unavailable");
  if (chunk.error_step) return t(`chat:turnError.step.${chunk.error_step}`);
  return chunk.error;
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
  // The failed turn, kept so "Try again" resends the same question (decision Item 72).
  type FailedTurn = { text: string; attachments?: UploadMeta[]; opts?: SendOpts };
  const [failedTurn, setFailedTurn] = useState<FailedTurn | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const pendingContextRef = useRef<ContextObject | null>(null);
  const pendingPlanRef = useRef<RetrievalPlan | null>(null);
  const pendingMapDataRef = useRef<MapData | null>(null);
  const pendingTurnSummaryRef = useRef<TurnSummary | null>(null);
  const hasTokenRef = useRef(false);
  const cachedMapRef = useRef<{ communityArea: number; mapData: MapData } | null>(null);
  // Active parcel grounding for the conversation: set once on a Scorecard
  // handoff, then attached to EVERY turn (typed follow-ups included) so grounding
  // survives past the first message. The backend decides per-turn whether it
  // applies (pin/point match + property-scoped) and steps aside on a pivot, so
  // attaching it on an off-parcel turn is harmless. Cleared on reset (New Chat).
  const activeGroundingRef = useRef<ScorecardContext | null>(null);
  const setGrounding = (ctx: ScorecardContext | null) => { activeGroundingRef.current = ctx; };

  const userMessageCount = messages.filter((m) => m.role === "user").length;
  const atMessageLimit = userMessageCount >= MESSAGE_LIMIT;

  function clearTurnState() {
    setPlan(null);
    setContext(null);
    setShowDisclaimer(false);
    setErrorMsg(null);
    setRateLimited(false);
    setActivities([]);
    setFailedTurn(null);
  }

  function reset() {
    abortRef.current?.abort();
    setMessages([]);
    clearTurnState();
    activeGroundingRef.current = null; // New Chat drops the parcel grounding
  }

  async function sendMessage(text: string, attachments?: UploadMeta[], opts?: SendOpts) {
    return send(text, attachments, opts);
  }

  function retry() {
    if (!failedTurn || streaming) return;
    // Drop the failed turn (its partial or empty answer, then its question) and send the question again.
    let base = messages;
    if (base[base.length - 1]?.role === "assistant") base = base.slice(0, -1);
    if (base[base.length - 1]?.role === "user" && base[base.length - 1].content === failedTurn.text) base = base.slice(0, -1);
    void send(failedTurn.text, failedTurn.attachments, failedTurn.opts, base);
  }

  // `base`: the transcript to send on top of (a retry drops the failed turn first). Without it the new turn is
  // appended to whatever the transcript is when React applies the update, as before.
  async function send(text: string, attachments: UploadMeta[] | undefined, opts: SendOpts | undefined, base?: Message[]) {
    if (streaming) return;

    if (base ? base.filter((m) => m.role === "user").length >= MESSAGE_LIMIT : atMessageLimit) {
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
    const historySnapshot = (base ?? messages).map((m) => ({ role: m.role, content: m.content }));
    if (base) setMessages([...base, userMessage, { role: "assistant", content: "" }]);
    else setMessages((m) => [...m, userMessage, { role: "assistant", content: "" }]);
    const thisTurn: FailedTurn = { text, attachments, opts };
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
        opts?.parcelPin ?? activeGroundingRef.current?.pin ?? null,
        opts?.scorecardContext ?? activeGroundingRef.current ?? null,
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
          if (chunk.timings && import.meta.env.DEV) {
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
          setErrorMsg(turnErrorText(chunk, t));
          if (chunk.error !== "MESSAGE_LIMIT_REACHED") setFailedTurn(thisTurn);
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        console.error(err);
        streamErrored = true;
        if (err instanceof ChatStreamError) {
          setErrorMsg(err.detail ?? t("common:connectionLost"));
          setRateLimited(err.status === 429);
          if (err.status !== 429) setFailedTurn(thisTurn);
        } else {
          setErrorMsg((err as Error).message);
          setFailedTurn(thisTurn);
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
        setFailedTurn(thisTurn);
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
    messagesRemaining: MESSAGE_LIMIT - userMessageCount,
    activities,
    sendMessage,
    clearTurnState,
    canRetry: failedTurn != null && !streaming,
    retry,
    reset,
    setGrounding,
  };
}
