// The sign-in chooser and the sign-in/link result notice, mounted once in main.tsx (Phase 9, Item 121). The notice
// comes from the address the server lands on (`?signin_error` / `?signin_hint` / `?link=&provider=`) and is removed
// from it through the router.
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { type AuthNotice, parseAuthNotice, stripAuthNotice } from "../../lib/authNotice";
import AuthOverlaysNext from "./AuthOverlaysNext";

export default function AuthOverlays() {
  const location = useLocation();
  const navigate = useNavigate();
  // The server lands here with a full page load, so the first address holds the notice.
  const [notice, setNotice] = useState<AuthNotice | null>(() => parseAuthNotice(location.search));
  useEffect(() => {
    if (!parseAuthNotice(location.search)) return;
    navigate({ pathname: location.pathname, search: stripAuthNotice(location.search), hash: location.hash }, { replace: true });
  }, [location.pathname, location.search, location.hash, navigate]);
  return <AuthOverlaysNext notice={notice} onDismiss={() => setNotice(null)} />;
}
