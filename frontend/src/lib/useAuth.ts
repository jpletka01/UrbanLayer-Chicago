import { useCallback, useEffect, useRef, useState } from "react";
import {
  type AuthStatus,
  type AuthUser,
  type SignInProvider,
  type SignInProviderId,
  getAuthStatus,
  getSignInProviders,
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
  /** Sign in: straight to the provider when only one is offered, else opens the chooser. */
  signIn: () => void;
  /** Go to a provider's sign-in, coming back to ``next`` (default: this page). */
  signInWith: (provider: SignInProviderId, next?: string) => void;
  /** The sign-in methods this server offers (Google, Apple, Microsoft), in order. */
  providers: SignInProvider[];
  chooserOpen: boolean;
  closeChooser: () => void;
  signOut: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

export function useAuth(): UseAuth {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authRequired, setAuthRequired] = useState(true);
  const [loading, setLoading] = useState(true);
  const [providers, setProviders] = useState<SignInProvider[]>([{ id: "google", test: false }]);
  const [chooserOpen, setChooserOpen] = useState(false);
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
      const status = await getAuthStatus();
      if (status.authenticated) {
        applyStatus(status);
      } else {
        const refreshed = status.can_refresh ? await refreshAuthToken() : null;
        if (refreshed) {
          applyStatus(refreshed);
        } else {
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
    // Which methods are set up; until it answers (or if it fails) Google alone, as before Item 121.
    getSignInProviders()
      .then((list) => { if (list.length) setProviders(list); })
      .catch(() => {});
  }, [checkAuth]);

  const signInWith = useCallback((provider: SignInProviderId, next?: string) => {
    try {
      sessionStorage.setItem("ul_signin_pending", "1");
    } catch {
      // never let tracking break auth
    }
    const here = `${window.location.pathname}${window.location.search}`;
    window.location.href = getSignInUrl(provider, next ?? here);
  }, []);

  const signIn = useCallback(() => {
    if (providers.length === 1) signInWith(providers[0].id);
    else setChooserOpen(true);
  }, [providers, signInWith]);

  const closeChooser = useCallback(() => setChooserOpen(false), []);

  const signOut = useCallback(async () => {
    await apiLogout();
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  return {
    user, isAuthenticated, authRequired, loading, signIn, signInWith, providers, chooserOpen, closeChooser,
    signOut, checkAuth,
  };
}
