// The readiness registry (decision Items 75–76): the ONE answer to "is this destination ready in the new UI?".
// It drives routing (VersionedRoute renders the new page only for a `ready` entry), the side panel (an entry
// appears only when `nav` is set and its status is not `hidden`), analytics names (`analytics`, sent with
// page_view in the preview) and preview access (`ready` routes are preview-only, so they get noindex).
//
//   ready  — the new page exists and renders behind ?ui=next
//   old    — the destination exists only as today's page; the side panel links to it, the route stays old
//   hidden — not built yet; neither routed nor shown
//
// Pure data: no components, so the old bundle and the lazy preview chunk can both import it.

export type Readiness = "ready" | "old" | "hidden";

export type NavIcon = "home" | "search" | "discovery" | "saved" | "chat";

export interface ReadinessEntry {
  id: string;
  /** The router path this entry owns (today's URL; the rewrite keeps every URL). */
  path: string;
  status: Readiness;
  /** Name sent as `page_name` with page_view while the preview is on. */
  analytics: string;
  /** Side-panel destination: label key in the `next` namespace, icon, and where it goes. */
  nav?: { labelKey: string; icon: NavIcon; to: string };
}

export const READINESS: readonly ReadinessEntry[] = [
  // "/" is the landing for visitors and the home for signed-in visitors (Phase 8); its chat doors go to /chat.
  { id: "home", path: "/", status: "ready", analytics: "next_home",
    nav: { labelKey: "nav.home", icon: "home", to: "/" } },
  { id: "profile", path: "/scorecard", status: "ready", analytics: "next_profile",
    nav: { labelKey: "nav.search", icon: "search", to: "/scorecard" } },
  { id: "discovery", path: "/discovery", status: "ready", analytics: "next_discovery",
    nav: { labelKey: "nav.discovery", icon: "discovery", to: "/discovery" } },
  // Saved (Phase 9, Item 119): saved lots and Discovery searches, and what changed since.
  { id: "saved", path: "/saved", status: "ready", analytics: "next_saved",
    nav: { labelKey: "nav.saved", icon: "saved", to: "/saved" } },
  { id: "chat", path: "/chat", status: "ready", analytics: "next_chat",
    nav: { labelKey: "nav.chat", icon: "chat", to: "/chat" } },
];

export function readinessOf(id: string): ReadinessEntry | undefined {
  return READINESS.find((e) => e.id === id);
}

/** True when the new page for this id may render. */
export function isReady(id: string): boolean {
  return readinessOf(id)?.status === "ready";
}

/** The entry that owns a pathname (exact match), if any. */
export function entryForPath(pathname: string): ReadinessEntry | undefined {
  return READINESS.find((e) => e.path === pathname);
}

/** Side-panel destinations, in order: everything with a nav slot that is not hidden. */
export function navEntries(): ReadinessEntry[] {
  return READINESS.filter((e) => e.nav && e.status !== "hidden");
}
