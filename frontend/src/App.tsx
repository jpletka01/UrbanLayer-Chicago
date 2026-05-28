import { useEffect, useRef, useState } from "react";
import { ChatInput } from "./components/ChatInput";
import { ChatInterface } from "./components/ChatInterface";
import { HeroSlideshow } from "./components/HeroSlideshow";
import { PromptSuggestionChip } from "./components/PromptSuggestionChip";
import { SidebarPanel } from "./components/SidebarPanel";
import { chatStream } from "./lib/api";
import { clearHistory, loadHistory, saveHistory } from "./lib/history";
import type { ContextObject, Message, RetrievalPlan } from "./lib/types";

const SUGGESTIONS = [
  "🌆 What's going on near 2400 N Milwaukee Ave?",
  "🚨 Crime trends in Wicker Park last 90 days",
  "🏗️ Can I open a bar in a residential district?",
  "🐀 Top 311 complaints in Logan Square",
];

const INGESTION_STATS = [
  { label: "Municipal code sections embedded", value: "—" },
  { label: "Live datasets connected", value: "5" },
  { label: "Community areas mapped", value: "77" },
];

export function App() {
  const [messages, setMessages] = useState<Message[]>(() => loadHistory());
  const [plan, setPlan] = useState<RetrievalPlan | null>(null);
  const [context, setContext] = useState<ContextObject | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => saveHistory(messages), [messages]);

  const active = messages.length > 0 || streaming;

  async function sendMessage(text: string) {
    if (streaming) return;
    setErrorMsg(null);
    setPlan(null);
    setContext(null);
    setShowDisclaimer(false);

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
          if (chunk.context.requires_disclaimer) setShowDisclaimer(true);
        } else if (chunk.type === "token") {
          setMessages((m) => {
            const next = [...m];
            const last = next[next.length - 1];
            if (last && last.role === "assistant") {
              next[next.length - 1] = { ...last, content: last.content + chunk.text };
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

  function reset() {
    abortRef.current?.abort();
    setMessages([]);
    clearHistory();
    setPlan(null);
    setContext(null);
    setShowDisclaimer(false);
    setErrorMsg(null);
  }

  if (!active) {
    return (
      <main className="relative w-full h-screen flex flex-col justify-center items-center px-4 overflow-hidden">
        <HeroSlideshow />
        <div className="relative z-10 text-center max-w-3xl space-y-6 mb-8">
          <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight text-white">
            Chicago City Intelligence
          </h1>
          <p className="text-lg text-white/80 leading-relaxed">
            Ask about crime patterns, 311 complaints, building activity, and zoning rules —
            anywhere in the city, in plain English.
          </p>
          <ChatInput onSubmit={sendMessage} />
          <div className="flex flex-wrap gap-2 justify-center mt-4">
            {SUGGESTIONS.map((s) => (
              <PromptSuggestionChip key={s} label={s} onClick={() => sendMessage(s.replace(/^[^A-Za-z]+/, "").trim())} />
            ))}
          </div>
        </div>

        <section className="relative z-10 w-full bg-slate-50 mt-auto py-12 px-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-7xl mx-auto">
            {INGESTION_STATS.map((stat) => (
              <div key={stat.label} className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm">
                <div className="text-4xl font-extrabold text-slate-900">{stat.value}</div>
                <div className="text-xs font-medium uppercase tracking-wider text-slate-500 mt-2">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="w-full h-screen flex flex-col bg-slate-50">
      <header className="h-16 px-6 flex items-center justify-between bg-white/80 backdrop-blur border-b border-slate-200 shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-sm font-bold tracking-wide text-slate-900">Chicago City Intelligence</span>
          {context?.community_area_name && (
            <span className="text-xs text-slate-500">→ {context.community_area_name}</span>
          )}
        </div>
        <button
          onClick={reset}
          className="text-xs font-medium text-slate-500 hover:text-slate-900"
        >
          New session
        </button>
      </header>
      {errorMsg && (
        <div className="px-6 py-2 bg-rose-50 border-b border-rose-200 text-rose-700 text-sm">
          {errorMsg}
        </div>
      )}
      <div className="flex-1 flex overflow-hidden">
        <ChatInterface
          messages={messages}
          streaming={streaming}
          showDisclaimer={showDisclaimer}
          onSubmit={sendMessage}
        />
        <SidebarPanel plan={plan} context={context} loading={streaming} />
      </div>
    </main>
  );
}
