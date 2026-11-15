// The chat list's order (owner review 2026-11-12): the latest conversation first, grouped the way chat apps date them.
import type { Conversation } from "../../lib/types";

export type ChatGroupKey = "today" | "yesterday" | "week" | "month" | "older";
export interface ChatGroup { key: ChatGroupKey; chats: Conversation[] }

const DAY = 86_400_000;

/** Chats newest first under Today / Yesterday / Previous 7 days / Previous 30 days / Older, empty groups dropped;
    a search keeps only titles containing every word typed. */
export function groupChats(chats: Conversation[], now: number, query = ""): ChatGroup[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  const today = start.getTime();
  const keyOf = (t: number): ChatGroupKey =>
    t >= today ? "today" : t >= today - DAY ? "yesterday" : t >= today - 7 * DAY ? "week" : t >= today - 30 * DAY ? "month" : "older";
  const order: ChatGroupKey[] = ["today", "yesterday", "week", "month", "older"];
  const groups = new Map<ChatGroupKey, Conversation[]>();
  [...chats]
    .filter((c) => words.every((w) => (c.title ?? "").toLowerCase().includes(w)))
    .sort((a, b) => (b.updatedAt ?? 0) - (a.updatedAt ?? 0))
    .forEach((c) => {
      const k = keyOf(c.updatedAt ?? c.createdAt ?? 0);
      groups.set(k, [...(groups.get(k) ?? []), c]);
    });
  return order.filter((k) => groups.has(k)).map((k) => ({ key: k, chats: groups.get(k)! }));
}
