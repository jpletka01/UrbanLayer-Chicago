import type { Conversation, Message } from "./types";

const CONVERSATIONS_KEY = "chicago.conversations.v1";
const CURRENT_KEY = "chicago.current_conversation.v1";

function generateId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function generateTitle(messages: Message[]): string {
  const firstUser = messages.find((m) => m.role === "user");
  if (!firstUser) return "New conversation";
  const content = firstUser.content.trim();
  return content.length > 50 ? content.slice(0, 47) + "..." : content;
}

export function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(CONVERSATIONS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveConversations(conversations: Conversation[]): void {
  try {
    localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations));
  } catch (err) {
    console.warn("Could not persist conversations", err);
  }
}

export function getCurrentConversationId(): string | null {
  return localStorage.getItem(CURRENT_KEY);
}

export function setCurrentConversationId(id: string | null): void {
  if (id) {
    localStorage.setItem(CURRENT_KEY, id);
  } else {
    localStorage.removeItem(CURRENT_KEY);
  }
}

export function loadConversation(id: string): Conversation | null {
  const conversations = loadConversations();
  return conversations.find((c) => c.id === id) || null;
}

export function saveConversation(messages: Message[], existingId?: string): string {
  const conversations = loadConversations();
  const now = Date.now();

  if (existingId) {
    const idx = conversations.findIndex((c) => c.id === existingId);
    if (idx >= 0) {
      conversations[idx] = {
        ...conversations[idx],
        messages,
        title: generateTitle(messages),
        updatedAt: now,
      };
      saveConversations(conversations);
      return existingId;
    }
  }

  const newConversation: Conversation = {
    id: generateId(),
    title: generateTitle(messages),
    messages,
    createdAt: now,
    updatedAt: now,
  };
  conversations.unshift(newConversation);
  saveConversations(conversations);
  setCurrentConversationId(newConversation.id);
  return newConversation.id;
}

export function deleteConversation(id: string): void {
  const conversations = loadConversations();
  const filtered = conversations.filter((c) => c.id !== id);
  saveConversations(filtered);
  if (getCurrentConversationId() === id) {
    setCurrentConversationId(null);
  }
}

export function clearAllHistory(): void {
  localStorage.removeItem(CONVERSATIONS_KEY);
  localStorage.removeItem(CURRENT_KEY);
}

// Legacy support - migrate old single-conversation format
export function migrateOldHistory(): void {
  const OLD_KEY = "chicago.chat.history.v1";
  try {
    const raw = localStorage.getItem(OLD_KEY);
    if (raw) {
      const messages = JSON.parse(raw);
      if (Array.isArray(messages) && messages.length > 0) {
        saveConversation(messages);
      }
      localStorage.removeItem(OLD_KEY);
    }
  } catch {
    // Ignore migration errors
  }
}
