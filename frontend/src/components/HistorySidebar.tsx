import { AnimatePresence, motion } from "motion/react";
import { useTranslation } from "react-i18next";
import type { Conversation } from "../lib/types";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  conversations: Conversation[];
  onSelect: (conversation: Conversation) => void;
  onDelete: (id: string) => void;
  onClearAll: () => void;
  onNewChat: () => void;
}

function formatDate(timestamp: number, t: (key: string, opts?: Record<string, unknown>) => string, lng: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return t("common:today");
  if (diffDays === 1) return t("common:yesterday");
  if (diffDays < 7) return t("common:daysAgo", { count: diffDays });
  return date.toLocaleDateString(lng === "es" ? "es-US" : "en-US", { month: "short", day: "numeric" });
}

export function HistorySidebar({ isOpen, onClose, conversations, onSelect, onDelete, onClearAll, onNewChat }: Props) {
  const { t, i18n } = useTranslation("common");
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40"
            onClick={onClose}
          />

          {/* Sidebar */}
          <motion.div
            initial={{ x: -320, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -320, opacity: 0 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="fixed left-0 top-0 bottom-0 z-50 w-80 bg-dark-surface/80 backdrop-blur-xl border-r border-dark-border flex flex-col"
          >
            {/* Header */}
            <div className="p-4 border-b border-dark-border flex items-center justify-between">
              <h2 className="text-lg font-medium text-white">{t("history")}</h2>
              <button
                onClick={onClose}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-text-secondary hover:text-text-primary hover:bg-dark-hover transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* New chat — pinned above the list so "start new / browse / delete" live together */}
            <div className="p-2 border-b border-dark-border">
              <button
                onClick={onNewChat}
                className="w-full flex items-center gap-2 px-3 py-2.5 text-body font-medium text-text-primary hover:text-text-primary hover:bg-dark-hover rounded-lg transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                {t("newChat")}
              </button>
            </div>

            {/* Conversations list */}
            <div className="flex-1 overflow-y-auto p-2">
              {conversations.length === 0 ? (
                <div className="text-center text-text-muted text-body py-8">
                  {t("noConversations")}
                </div>
              ) : (
                <div className="space-y-1">
                  {conversations.map((conv) => (
                    <div
                      key={conv.id}
                      className="group relative rounded-lg hover:bg-dark-hover transition-colors"
                    >
                      <button
                        onClick={() => onSelect(conv)}
                        className="w-full text-left p-3 pr-10"
                      >
                        <div className="text-body text-text-primary truncate">{conv.title}</div>
                        <div className="text-caption text-text-muted mt-1">{formatDate(conv.updatedAt, t, i18n.language)}</div>
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDelete(conv.id);
                        }}
                        className="absolute right-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-md flex items-center justify-center text-text-muted hover:text-rose-400 hover:bg-rose-500/10 opacity-0 group-hover:opacity-100 transition-all"
                        title={t("deleteConversation")}
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            {conversations.length > 0 && (
              <div className="p-3 border-t border-dark-border">
                <button
                  onClick={onClearAll}
                  className="w-full px-3 py-2 text-body text-text-secondary hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
                >
                  {t("deleteAll")}
                </button>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
