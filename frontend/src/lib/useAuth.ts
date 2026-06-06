import { useCallback, useEffect, useRef, useState } from "react";
import {
  type AuthStatus,
  type AuthUser,
  getAuthStatus,
  getSignInUrl,
  logout as apiLogout,
  refreshAuthToken,
} from "./api";

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
    window.location.href = getSignInUrl();
  }, []);

  const signOut = useCallback(async () => {
    await apiLogout();
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  return { user, isAuthenticated, authRequired, loading, signIn, signOut, checkAuth };
}
