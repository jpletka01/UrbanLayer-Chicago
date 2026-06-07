import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import type { AuthUser } from "../lib/api";
import { createBillingPortal } from "../lib/api";

interface UserMenuProps {
  user: AuthUser;
  onSignOut: () => Promise<void>;
}

export default function UserMenu({ user, onSignOut }: UserMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const initial = (user.name || user.email)[0]?.toUpperCase() ?? "?";
  const isPro = user.tier === "premium" || user.tier === "admin";

  async function handleManageSubscription() {
    setOpen(false);
    try {
      const { url } = await createBillingPortal();
      window.location.href = url;
    } catch {
      // No active subscription — send to pricing
      window.location.href = "/pricing";
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-full hover:ring-2 hover:ring-dark-border transition-all"
        title={user.name}
      >
        {user.picture_url ? (
          <img
            src={user.picture_url}
            alt=""
            className="w-7 h-7 rounded-full"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="w-7 h-7 rounded-full bg-accent/80 flex items-center justify-center text-xs font-medium text-white">
            {initial}
          </div>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-56 bg-dark-elevated border border-dark-border rounded-xl shadow-lg py-2 z-50">
          <div className="px-4 py-2 border-b border-dark-border">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium text-text-primary truncate">{user.name}</p>
              {isPro && (
                <span className="text-[10px] font-medium bg-accent/20 text-accent px-1.5 py-0.5 rounded">
                  Pro
                </span>
              )}
            </div>
            <p className="text-xs text-text-muted truncate">{user.email}</p>
          </div>
          {isPro ? (
            <button
              onClick={handleManageSubscription}
              className="w-full text-left px-4 py-2 text-sm text-text-secondary hover:bg-dark-surface hover:text-text-primary transition-colors"
            >
              Manage subscription
            </button>
          ) : (
            <Link
              to="/pricing"
              onClick={() => setOpen(false)}
              className="block w-full text-left px-4 py-2 text-sm text-accent hover:bg-dark-surface transition-colors"
            >
              Upgrade to Pro
            </Link>
          )}
          <button
            onClick={async () => {
              setOpen(false);
              await onSignOut();
            }}
            className="w-full text-left px-4 py-2 text-sm text-text-secondary hover:bg-dark-surface hover:text-text-primary transition-colors"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
