// The pages, each loaded on demand as its own chunk; the frame's outline shows while one downloads (FrameOutline).
// A chunk that can't be downloaded (a tab open across a deploy) reloads the page once (loadPage).
import { lazy } from "react";
import { loadPage } from "./loadPage";

export const PAGES = {
  home: lazy(loadPage(() => import("./home/RootNextPage"))),
  profile: lazy(loadPage(() => import("./profile/ProfileNextPage"))),
  discovery: lazy(loadPage(() => import("./discovery/DiscoveryNextPage"))),
  chat: lazy(loadPage(() => import("./chat/ChatNextPage"))),
  saved: lazy(loadPage(() => import("./saved/SavedNextPage"))),
  settings: lazy(loadPage(() => import("./settings/SettingsNextPage"))),
  pricing: lazy(loadPage(() => import("./pricing/PricingNextPage"))),
  about: lazy(loadPage(() => import("./about/AboutNextPage"))),
  privacy: lazy(loadPage(() => import("./about/PrivacyNextPage"))),
  admin: lazy(loadPage(() => import("./admin/AdminNextPage"))),
  notFound: lazy(loadPage(() => import("./notfound/NotFoundNextPage"))),
};
