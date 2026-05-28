import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { ChatInput } from "./components/ChatInput";
import { ChatInterface } from "./components/ChatInterface";
import { HeroSlideshow } from "./components/HeroSlideshow";
import { PromptSuggestionChip } from "./components/PromptSuggestionChip";
import { SidebarPanel } from "./components/SidebarPanel";
import { chatStream } from "./lib/api";
import { clearHistory, loadHistory, saveHistory } from "./lib/history";
import type { ContextObject, Message, PhaseTimings, RetrievalPlan, SidebarView } from "./lib/types";

const SUGGESTIONS = [
  "What's going on near 2400 N Milwaukee Ave?",
  "Crime trends in Wicker Park last 90 days",
  "Can I open a bar in a residential district?",
  "Top 311 complaints in Logan Square",
];

export function App() {
  const [messages, setMessages] = useState<Message[]>(() => loadHistory());
  const [plan, setPlan] = useState<RetrievalPlan | null>(null);
  const [context, setContext] = useState<ContextObject | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [timings, setTimings] = useState<PhaseTimings>({});
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarView, setSidebarView] = useState<SidebarView>("data");
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => saveHistory(messages), [messages]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "b") {
        e.preventDefault();
        setSidebarOpen((prev) => !prev);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const active = messages.length > 0 || streaming;

  async function sendMessage(text: string) {
    if (streaming) return;
    setErrorMsg(null);
    setPlan(null);
    setContext(null);
    setShowDisclaimer(false);
    setTimings({});

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
          if (chunk.t_ms !== undefined) {
            setTimings((t) => ({ ...t, router_ms: chunk.t_ms }));
          }
        } else if (chunk.type === "context") {
          setContext(chunk.context);
          setSidebarOpen(true);
          if (chunk.context.requires_disclaimer) setShowDisclaimer(true);
          if (chunk.t_ms !== undefined) {
            setTimings((t) => ({ ...t, retrieval_ms: chunk.t_ms }));
          }
        } else if (chunk.type === "token") {
          if (chunk.t_ms !== undefined) {
            setTimings((t) => ({ ...t, first_token_ms: chunk.t_ms }));
          }
          setMessages((m) => {
            const next = [...m];
            const last = next[next.length - 1];
            if (last && last.role === "assistant") {
              next[next.length - 1] = { ...last, content: last.content + chunk.text };
            }
            return next;
          });
        } else if (chunk.type === "done") {
          if (chunk.t_ms !== undefined) {
            setTimings((t) => ({ ...t, total_ms: chunk.t_ms }));
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

  function reset() {
    abortRef.current?.abort();
    setMessages([]);
    clearHistory();
    setPlan(null);
    setContext(null);
    setShowDisclaimer(false);
    setErrorMsg(null);
    setSidebarOpen(false);
    setSidebarView("data");
  }

  return (
    <main className="w-full min-h-screen text-text-primary">
      <AnimatePresence mode="wait">
        {!active ? (
          <motion.div
            key="splash"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="relative w-full min-h-screen flex flex-col"
          >
            <div className="relative flex-1 flex flex-col justify-center items-center px-4 py-20">
              <HeroSlideshow />
              <div className="relative z-10 text-center max-w-2xl space-y-8">
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1, duration: 0.5 }}
                >
                  <h1 className="text-4xl md:text-5xl font-semibold tracking-tight text-white mb-4">
                    Chicago City Intelligence
                  </h1>
                  <p className="text-lg text-white/80 leading-relaxed">
                    Ask about crime patterns, 311 complaints, building activity, and zoning rules — anywhere in the city.
                  </p>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2, duration: 0.5 }}
                >
                  <ChatInput onSubmit={sendMessage} variant="hero" />
                </motion.div>

                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.4, duration: 0.5 }}
                  className="flex flex-wrap gap-2 justify-center"
                >
                  {SUGGESTIONS.map((s) => (
                    <PromptSuggestionChip
                      key={s}
                      label={s}
                      onClick={() => sendMessage(s)}
                    />
                  ))}
                </motion.div>
              </div>
            </div>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5, duration: 0.5 }}
              className="absolute bottom-12 left-0 right-0 z-10 flex justify-around px-8"
            >
              <div className="text-center">
                <div className="text-4xl font-semibold text-white">14,628</div>
                <div className="text-sm text-white/60 uppercase tracking-wider mt-2">Code sections</div>
              </div>
              <div className="text-center">
                <div className="text-4xl font-semibold text-white">5</div>
                <div className="text-sm text-white/60 uppercase tracking-wider mt-2">Live datasets</div>
              </div>
              <div className="text-center">
                <div className="text-4xl font-semibold text-white">77</div>
                <div className="text-sm text-white/60 uppercase tracking-wider mt-2">Community areas</div>
              </div>
            </motion.div>
          </motion.div>
        ) : (
          <motion.div
            key="workspace"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className="w-full h-screen flex flex-col bg-dark-bg"
          >
            <header className="h-14 px-6 flex items-center justify-between bg-dark-bg shrink-0">
              <div className="flex items-center gap-4">
                <button
                  onClick={reset}
                  className="text-sm font-medium text-text-secondary hover:text-text-primary transition-colors"
                >
                  Chicago City Intelligence
                </button>
                {context?.community_area_name && (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-text-muted">/</span>
                    <span className="text-text-primary">{context.community_area_name}</span>
                  </div>
                )}
              </div>
              <button
                onClick={reset}
                className="px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-dark-elevated rounded-lg transition-colors"
              >
                New chat
              </button>
            </header>

            {errorMsg && (
              <div className="px-6 py-3 bg-rose-500/10 border-b border-rose-500/20 text-rose-400 text-sm">
                {errorMsg}
              </div>
            )}

            <div className="flex-1 flex overflow-hidden">
              <ChatInterface
                messages={messages}
                streaming={streaming}
                showDisclaimer={showDisclaimer}
                onSubmit={sendMessage}
                isSidebarOpen={sidebarOpen}
              />
              <SidebarPanel
                plan={plan}
                context={context}
                loading={streaming}
                timings={timings}
                isOpen={sidebarOpen}
                onToggle={() => setSidebarOpen(!sidebarOpen)}
                activeView={sidebarView}
                onViewChange={setSidebarView}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
