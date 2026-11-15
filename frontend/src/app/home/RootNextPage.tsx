// "/" in the new UI (Phase 8): a signed-in visitor lands on the home, anyone else on the landing (brief, "The app
// frame"). "?landing=1" shows the landing to a signed-in visitor too ("About UrbanLayer" in the side panel). Where
// sign-in is off (local development), everyone counts as signed in, like the chat's storage rule.
import { useSearchParams } from "react-router-dom";
import { useAuthContext } from "../../contexts/AuthContext";
import { FrameOutline } from "../frame/FrameOutline";
import HomeNextPage from "./HomeNextPage";
import LandingNextPage from "../landing/LandingNextPage";

export default function RootNextPage() {
  const [params] = useSearchParams();
  const { isAuthenticated, authRequired, loading } = useAuthContext();
  if (params.get("landing") === "1") return <LandingNextPage />;
  if (loading) return <FrameOutline />;
  return isAuthenticated || !authRequired ? <HomeNextPage /> : <LandingNextPage />;
}
