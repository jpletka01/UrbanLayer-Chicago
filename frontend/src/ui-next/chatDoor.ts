// The query parameters that open chat from another page (useChatSession): an autosend, a parcel, a handoff from the
// Profile's quick chat, or the bare "Ask the analyst" door. On "/" they go to /chat with the same parameters.
const CHAT_DOOR_PARAMS = ["q", "pin", "handoff", "ask"];

export function isChatDoor(search: string): boolean {
  const p = new URLSearchParams(search);
  return CHAT_DOOR_PARAMS.some((k) => p.has(k));
}
