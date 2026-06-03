import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuthContext } from "../contexts/AuthContext";

interface ProtectedRouteProps {
  tier?: "admin";
  children: ReactNode;
}

export default function ProtectedRoute({ tier, children }: ProtectedRouteProps) {
  const { isAuthenticated, authRequired, user, loading } = useAuthContext();

  if (loading) {
    return <div className="w-full min-h-screen bg-[#0d0d0d]" />;
  }

  if (authRequired && !isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  if (tier === "admin" && user?.tier !== "admin") {
    return (
      <div className="w-full min-h-screen bg-[#0d0d0d] flex items-center justify-center">
        <p className="text-text-secondary text-sm">Admin access required</p>
      </div>
    );
  }

  return <>{children}</>;
}
