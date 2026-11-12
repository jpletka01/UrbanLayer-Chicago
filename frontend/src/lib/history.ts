import type { Conversation, Message } from "./types";
import {
  clearAllConversations,
  deleteConversationAPI,
  importConversations,
  listConversations,
  saveMessages as apiSaveMessages,
} from "./api";

const OLD_CONVERSATIONS_KEY = "chicago.conversations.v1";
const OLD_CURRENT_KEY = "chicago.current_conversation.v1";
const MIGRATION_KEY = "chicago.migrated_to_sqlite";

function generateId(): string {
  return `conv_${crypto.randomUUID()}`;
}

export async function loadConversations(): Promise<Conversation[]> {
  return listConversations();
}

export async function appendMessages(
  conversationId: string,
  messages: Message[],
): Promise<void> {
  const stored = messages.map((m) => ({
    role: m.role,
    content: m.content,
    ...(m.context ? { context: m.context } : {}),
    ...(m.plan ? { plan: m.plan } : {}),
    ...(m.mapData ? { map_data: m.mapData } : {}),
    ...(m.mapFetchedAt ? { map_fetched_at: m.mapFetchedAt } : {}),
    ...(m.turnSummary ? { summary: m.turnSummary } : {}),
  }));
  try {
    await apiSaveMessages(conversationId, stored);
  } catch (err) {
    // The server re-checks an answer's context and plan against strict types; one that fails (422) used to be
    // dropped, so a reopened chat came back empty (owner's review, 2026-11-12). Keep the turn: store it again with
    // its text and map only. The server logs which field failed.
    if (!(err instanceof Error && err.message.includes("422"))) throw err;
    await apiSaveMessages(conversationId, stored.map(({ role, content, map_data, map_fetched_at }) => ({
      role, content,
      ...(map_data ? { map_data } : {}),
      ...(map_fetched_at ? { map_fetched_at } : {}),
    })));
  }
}

export async function deleteConversation(id: string): Promise<void> {
  return deleteConversationAPI(id);
}

export async function clearAllHistory(): Promise<void> {
  return clearAllConversations();
}

export { generateId };

// ---------------------------------------------------------------------------
// One-time migration from localStorage to SQLite
// ---------------------------------------------------------------------------

export async function migrateLocalStorageToSQLite(): Promise<void> {
  if (localStorage.getItem(MIGRATION_KEY)) return;

  const raw = localStorage.getItem(OLD_CONVERSATIONS_KEY);
  if (!raw) {
    localStorage.setItem(MIGRATION_KEY, "1");
    return;
  }

  try {
    const conversations = JSON.parse(raw);
    if (Array.isArray(conversations) && conversations.length > 0) {
      await importConversations(conversations);
    }
  } catch (err) {
    console.warn("Migration failed:", err);
  }

  localStorage.removeItem(OLD_CONVERSATIONS_KEY);
  localStorage.removeItem(OLD_CURRENT_KEY);
  localStorage.setItem(MIGRATION_KEY, "1");
}
