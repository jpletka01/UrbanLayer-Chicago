// One route, two pages: today's page unless the preview is on AND the readiness registry says the new page is
// ready. The new pages load as their own chunk (pages.ts), so visitors on today's UI never download them.
import { Suspense, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useUiVersion } from "./uiVersionContext";
import { useNoindex } from "./useNoindex";
import { isReady } from "./readiness";
import { NEXT_PAGES } from "./pages";
import { FrameOutline } from "./frame/FrameOutline";

/** The query parameters that open chat from another page (useChatSession): an autosend, a parcel, a handoff from
    the Profile's quick chat, or the bare "Ask the analyst" door. */
const CHAT_DOOR_PARAMS = ["q", "pin", "handoff", "ask"];

export function isChatDoor(search: string): boolean {
  const p = new URLSearchParams(search);
  return CHAT_DOOR_PARAMS.some((k) => p.has(k));
}

export function VersionedRoute({ id, old, door = false }: {
  id: keyof typeof NEXT_PAGES;
  old: ReactNode;
  /** "/" in the preview: only its chat doors go to the new chat page (at /chat, keeping their parameters); the rest
      of "/" stays today's page until the new landing is ready. */
  door?: boolean;
}) {
  const { version } = useUiVersion();
  const { search } = useLocation();
  const next = version === "next" && isReady(id) && (!door || isChatDoor(search));
  useNoindex(next);
  if (!next) return <>{old}</>;
  if (door) return <Navigate to={`/chat${search}`} replace />;
  const Page = NEXT_PAGES[id];
  return (
    <Suspense fallback={<FrameOutline />}>
      <Page />
    </Suspense>
  );
}
