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
      const status = await getAuthStatus();
      if (status.authenticated) {
        applyStatus(status);
      } else {
        const refreshed = await refreshAuthToken();
        if (refreshed) {
          applyStatus(refreshed);
        } else {
          setUser(null);
          setIsAuthenticated(false);
          setAuthRequired(status.auth_required);
        }
      }
    } catch {
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
