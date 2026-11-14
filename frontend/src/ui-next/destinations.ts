// The site's destinations (decision Items 75–76; Phase 10 made the new UI the only one): each page's path, the name
// page_view sends as `page_name`, and its side-panel slot when it has one. The side panel lists the entries with a
// `nav`, in this order.

export type NavIcon = "home" | "search" | "discovery" | "saved" | "chat";

export interface Destination {
  id: string;
  /** The router path this entry owns (every URL from before the rewrite is kept). */
  path: string;
  /** Sent as `page_name` with page_view. */
  analytics: string;
  /** Side-panel destination: label key in the `next` namespace, icon, and where it goes. */
  nav?: { labelKey: string; icon: NavIcon; to: string };
}

export const DESTINATIONS: readonly Destination[] = [
  // "/" is the landing for visitors and the home for signed-in visitors (Phase 8); its chat doors go to /chat.
  { id: "home", path: "/", analytics: "home", nav: { labelKey: "nav.home", icon: "home", to: "/" } },
  { id: "profile", path: "/scorecard", analytics: "profile", nav: { labelKey: "nav.search", icon: "search", to: "/scorecard" } },
  { id: "discovery", path: "/discovery", analytics: "discovery", nav: { labelKey: "nav.discovery", icon: "discovery", to: "/discovery" } },
  { id: "saved", path: "/saved", analytics: "saved", nav: { labelKey: "nav.saved", icon: "saved", to: "/saved" } },
  { id: "chat", path: "/chat", analytics: "chat", nav: { labelKey: "nav.chat", icon: "chat", to: "/chat" } },
  { id: "settings", path: "/settings", analytics: "settings" },
  { id: "pricing", path: "/pricing", analytics: "pricing" },
  { id: "about", path: "/about", analytics: "about" },
  { id: "privacy", path: "/privacy", analytics: "privacy" },
  { id: "admin", path: "/admin", analytics: "admin" },
];

/** The page_name for a pathname: an exact path, a stored chat (/c/:id) as "chat", a shared one (/s/:token) as
    "shared_chat", a Settings section as "settings", anything else as "not_found". */
export function pageNameFor(pathname: string): string {
  const exact = DESTINATIONS.find((e) => e.path === pathname);
  if (exact) return exact.analytics;
  if (pathname.startsWith("/c/")) return "chat";
  if (pathname.startsWith("/s/")) return "shared_chat";
  if (pathname.startsWith("/settings/")) return "settings";
  if (pathname === "/explore") return "discovery";
  return "not_found";
}

/** Side-panel destinations, in order. */
export function navEntries(): Destination[] {
  return DESTINATIONS.filter((e) => e.nav);
}
