import { useCallback, useEffect, useRef, useState } from "react";
import {
  type AuthStatus,
  type AuthUser,
  getAuthStatus,
  getSignInUrl,
  logout as apiLogout,
  refreshAuthToken,
} from "./api";
import { track } from "./tracking";

export interface UseAuth {
  user: AuthUser | null;
  isAuthenticated: boolean;
  authRequired: boolean;
  loading: boolean;
  signIn: () => void;
  signOut: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

export function useAuth(): UseAuth {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authRequired, setAuthRequired] = useState(true);
  const [loading, setLoading] = useState(true);
  const checkedRef = useRef(false);

  const applyStatus = useCallback((status: AuthStatus) => {
    setUser(status.user);
    setIsAuthenticated(status.authenticated);
    setAuthRequired(status.auth_required);
    // A sign-in initiated this session just completed (OAuth redirect returned).
    // The server attaches user_id to events, so this one stitches visitor→user.
    try {
      if (status.authenticated && sessionStorage.getItem("ul_signin_pending")) {
        sessionStorage.removeItem("ul_signin_pending");
        track("signup_completed");
        // Sign-in is the natural moment to ask "what best describes you" —
        // SegmentPrompt (global) picks this flag up. Never re-ask an answer.
        if (!localStorage.getItem("ul_segment")) {
          sessionStorage.setItem("ul_segment_due", "1");
        }
      }
    } catch {
      // never let tracking break auth
    }
  }, []);

  const checkAuth = useCallback(async () => {
    try {
      console.log("[auth] checking auth status");
      const status = await getAuthStatus();
      console.log("[auth] status:", status.authenticated, status.auth_required, status.user?.email);
      if (status.authenticated) {
        applyStatus(status);
      } else {
        console.log("[auth] not authenticated, attempting token refresh");
        const refreshed = await refreshAuthToken();
        if (refreshed) {
          console.log("[auth] refresh succeeded:", refreshed.user?.email);
          applyStatus(refreshed);
        } else {
          console.log("[auth] refresh failed, user is unauthenticated");
          setUser(null);
          setIsAuthenticated(false);
          setAuthRequired(status.auth_required);
        }
      }
    } catch (err) {
      console.error("[auth] checkAuth error:", err);
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  }, [applyStatus]);

  useEffect(() => {
    if (checkedRef.current) return;
    checkedRef.current = true;
    checkAuth();
  }, [checkAuth]);

  const signIn = useCallback(() => {
    try {
      sessionStorage.setItem("ul_signin_pending", "1");
    } catch {
      // never let tracking break auth
    }
    window.location.href = getSignInUrl();
  }, []);

  const signOut = useCallback(async () => {
    await apiLogout();
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  return { user, isAuthenticated, authRequired, loading, signIn, signOut, checkAuth };
}
