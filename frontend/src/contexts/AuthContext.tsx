import { createContext, useContext, type ReactNode } from "react";
import { type UseAuth, useAuth } from "../lib/useAuth";
import AuthOverlays from "../components/auth/AuthOverlays";

const AuthContext = createContext<UseAuth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const auth = useAuth();
  return (
    <AuthContext.Provider value={auth}>
      {children}
      {/* The sign-in chooser and the sign-in/link result notice, once for the whole app (Item 121). */}
      <AuthOverlays />
    </AuthContext.Provider>
  );
}

export function useAuthContext(): UseAuth {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuthContext must be used within AuthProvider");
  return ctx;
}
