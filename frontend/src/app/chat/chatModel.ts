// The full chat page's pure model (Phase 8; brief "Chat"): what an answer offers as small previews (the lot, a
// map, its sources), the map's points, and the conversation's title. Answers lead with text; a preview opens only
// when the visitor asks for it.
import type { ContextObject, Message } from "../../lib/types";
import { sourcesFor } from "./evidenceModel";
import { chooseLens, lensView, type Lens } from "./chatLens";

export type PreviewKind = "lot" | "map" | "sources";

export interface LotPreview { kind: "lot"; address: string; pin: string | null; href: string }
/** The map chip names what its lens draws: the lot, or how many crimes or projects are nearby. */
export interface MapPreview { kind: "map"; lens: Lens; count: number; near: boolean }
export interface SourcesPreview { kind: "sources"; count: number }
export type Preview = LotPreview | MapPreview | SourcesPreview;

/** The Profile link for an answer's lot: by PIN when the answer resolved one, else by address. */
export function lotHref(address: string, pin: string | null): string {
  const p = new URLSearchParams(pin ? { pin, address } : { address });
  return `/scorecard?${p}`;
}

/** The previews under one finished answer, in a fixed order: the lot, the map, the sources (code and records). */
export function previewsFor(message: Message): Preview[] {
  if (message.role !== "assistant" || !message.content) return [];
  const ctx: ContextObject | undefined = message.context;
  const out: Preview[] = [];
  const pin = ctx?.property?.pin14 ?? null;
  const address = ctx?.resolved_address ?? null;
  // A lot only when the answer resolved a parcel (its PIN, or zoning at the address), as today's chat links it.
  if (address && (pin || ctx?.parcel_zoning)) out.push({ kind: "lot", address, pin, href: lotHref(address, pin) });
  const lens = chooseLens(message);
  if (lens && message.mapData) {
    const v = lens === "lot" ? null : lensView(message.mapData, lens);
    out.push({ kind: "map", lens, count: v?.counts.shown ?? 0, near: !!message.mapData.queried_address });
  }
  const count = sourcesFor(message).length;
  if (count > 0) out.push({ kind: "sources", count });
  return out;
}

/** The conversation's title: its first question, shortened like the stored title. */
export function chatTitle(messages: Message[]): string | null {
  const first = messages.find((m) => m.role === "user" && m.content.trim());
  if (!first) return null;
  const text = first.content.trim();
  return text.length > 50 ? `${text.slice(0, 47)}...` : text;
}

export type EvidenceTab = "sources" | "map";

/** The evidence panel's tabs for one answer, in a fixed order; only those the answer has. */
export function evidenceTabs(message: Message | undefined): EvidenceTab[] {
  if (!message || message.role !== "assistant") return [];
  const out: EvidenceTab[] = [];
  if (sourcesFor(message).length > 0) out.push("sources");
  if (chooseLens(message)) out.push("map");
  return out;
}
