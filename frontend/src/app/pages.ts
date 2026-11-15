// The pages, each loaded on demand as its own chunk; the frame's outline shows while one downloads (FrameOutline).
import { lazy } from "react";

export const PAGES = {
  home: lazy(() => import("./home/RootNextPage")),
  profile: lazy(() => import("./profile/ProfileNextPage")),
  discovery: lazy(() => import("./discovery/DiscoveryNextPage")),
  chat: lazy(() => import("./chat/ChatNextPage")),
  saved: lazy(() => import("./saved/SavedNextPage")),
  settings: lazy(() => import("./settings/SettingsNextPage")),
  pricing: lazy(() => import("./pricing/PricingNextPage")),
  about: lazy(() => import("./about/AboutNextPage")),
  privacy: lazy(() => import("./about/PrivacyNextPage")),
  admin: lazy(() => import("./admin/AdminNextPage")),
  notFound: lazy(() => import("./notfound/NotFoundNextPage")),
};
