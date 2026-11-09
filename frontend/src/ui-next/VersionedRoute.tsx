// One route, two pages: today's page unless the preview is on AND the readiness registry says the new page is
// ready. The new pages load as their own chunk (pages.ts), so visitors on today's UI never download them.
import { Suspense, type ReactNode } from "react";
import { useUiVersion } from "./uiVersionContext";
import { useNoindex } from "./useNoindex";
import { isReady } from "./readiness";
import { NEXT_PAGES } from "./pages";
import { FrameOutline } from "./frame/FrameOutline";

export function VersionedRoute({ id, old }: { id: keyof typeof NEXT_PAGES; old: ReactNode }) {
  const { version } = useUiVersion();
  const next = version === "next" && isReady(id);
  useNoindex(next);
  if (!next) return <>{old}</>;
  const Page = NEXT_PAGES[id];
  return (
    <Suspense fallback={<FrameOutline />}>
      <Page />
    </Suspense>
  );
}
