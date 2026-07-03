import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import type { AuthUser } from "../lib/api";
import { Chip } from "./ui/Chip";

interface UserMenuProps {
  user: AuthUser;
  onSignOut: () => Promise<void>;
}

export default function UserMenu({ user, onSignOut }: UserMenuProps) {
  const { t } = useTranslation("common");
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
          <div className="w-7 h-7 rounded-full bg-accent/80 flex items-center justify-center text-caption font-medium text-text-on-accent">
            {initial}
          </div>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-56 bg-dark-elevated border border-dark-border rounded-xl shadow-lg py-2 z-50">
          <div className="px-4 py-2 border-b border-dark-border">
            <div className="flex items-center gap-2">
              <p className="text-body font-medium text-text-primary truncate">{user.name}</p>
              {isPro && <Chip tone="accent" size="sm">Pro</Chip>}
            </div>
            <p className="text-caption text-text-muted truncate">{user.email}</p>
          </div>
          <Link
            to="/settings"
            onClick={() => setOpen(false)}
            className="block w-full text-left px-4 py-2 text-body text-text-secondary hover:bg-dark-hover hover:text-text-primary transition-colors"
          >
            {t("settings")}
          </Link>
          {user.tier === "admin" && (
            <Link
              to="/admin"
              onClick={() => setOpen(false)}
              className="block w-full text-left px-4 py-2 text-body text-text-secondary hover:bg-dark-hover hover:text-text-primary transition-colors"
            >
              {t("admin")}
            </Link>
          )}
          {!isPro && (
            <Link
              to="/pricing"
              onClick={() => setOpen(false)}
              className="block w-full text-left px-4 py-2 text-body text-accent hover:bg-dark-hover transition-colors"
            >
              {t("upgradeToPro")}
            </Link>
          )}
          <button
            onClick={async () => {
              setOpen(false);
              await onSignOut();
            }}
            className="w-full text-left px-4 py-2 text-body text-text-secondary hover:bg-dark-hover hover:text-text-primary transition-colors"
          >
            {t("signOut")}
          </button>
        </div>
      )}
    </div>
  );
}
