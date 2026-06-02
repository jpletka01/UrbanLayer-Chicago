import type { Conversation, Message } from "./types";
import {
  clearAllConversations,
  createConversation,
  deleteConversationAPI,
  importConversations,
  listConversations,
  saveMessages as apiSaveMessages,
} from "./api";

const OLD_CONVERSATIONS_KEY = "chicago.conversations.v1";
const OLD_CURRENT_KEY = "chicago.current_conversation.v1";
const MIGRATION_KEY = "chicago.migrated_to_sqlite";

function generateId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function generateTitle(messages: Message[]): string {
  const firstUser = messages.find((m) => m.role === "user");
  if (!firstUser) return "New conversation";
  const content = firstUser.content.trim();
  return content.length > 50 ? content.slice(0, 47) + "..." : content;
}

export async function loadConversations(): Promise<Conversation[]> {
  return listConversations();
}

export async function saveConversation(
  messages: Message[],
  existingId?: string,
): Promise<string> {
  const id = existingId || generateId();

  if (!existingId) {
    const title = generateTitle(messages);
    await createConversation(id, title);
  }

  const stored = messages.map((m) => ({
    role: m.role,
    content: m.content,
    ...(m.context ? { context: m.context } : {}),
    ...(m.plan ? { plan: m.plan } : {}),
    ...(m.mapData ? { map_data: m.mapData } : {}),
    ...(m.mapFetchedAt ? { map_fetched_at: m.mapFetchedAt } : {}),
    ...(m.turnSummary ? { summary: m.turnSummary } : {}),
  }));

  await apiSaveMessages(id, stored);
  return id;
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
  await apiSaveMessages(conversationId, stored);
}

export async function deleteConversation(id: string): Promise<void> {
  return deleteConversationAPI(id);
}

export async function clearAllHistory(): Promise<void> {
  return clearAllConversations();
}

export { generateId, generateTitle };

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
