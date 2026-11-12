// The new UI's pages, loaded on demand: one chunk, fetched only when the preview renders one of them.
import { lazy } from "react";

export const NEXT_PAGES = {
  profile: lazy(() => import("./profile/ProfileNextPage")),
  discovery: lazy(() => import("./discovery/DiscoveryNextPage")),
  chat: lazy(() => import("./chat/ChatNextPage")),
  home: lazy(() => import("./home/RootNextPage")),
};
