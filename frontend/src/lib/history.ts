import type { Message } from "./types";

const KEY = "chicago.chat.history.v1";

export function loadHistory(): Message[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveHistory(messages: Message[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(messages));
  } catch (err) {
    console.warn("Could not persist chat history", err);
  }
}

export function clearHistory(): void {
  localStorage.removeItem(KEY);
}
