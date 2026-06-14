import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuthContext } from "../contexts/AuthContext";
import { loadRegistry } from "../discovery/registryClient";
import LanguageSelector from "./LanguageSelector";
import UserMenu from "./UserMenu";

const NAV_ITEMS: { to: string; key: string }[] = [
  // "Analyst" opens the homepage hero directly in chat mode — the cited
  // code-research surface — not the address-first front door.
  { to: "/?analyst=1", key: "nav.chat" },
  { to: "/scorecard", key: "nav.scorecard" },
  { to: "/pricing", key: "nav.pricing" },
  { to: "/about", key: "nav.about" },
];

// Discovery is linked only once its index actually has data (coverage != "none"); while
// dormant it stays unlinked. The check rides the cached discovery registry, so it's one
// shared fetch, not per-page work. (It took Explore's old nav slot — after Scorecard —
// when /explore was retired 2026-06-14.)
const DISCOVERY_ITEM = { to: "/discovery", key: "nav.discovery" };

export function navItemsFor(discoveryLive: boolean): { to: string; key: string }[] {
  if (!discoveryLive) return NAV_ITEMS;
  return [...NAV_ITEMS.slice(0, 2), DISCOVERY_ITEM, ...NAV_ITEMS.slice(2)]; // after Scorecard
}

/**
 * Standard header for the non-chat pages (Scorecard, Discovery, Pricing, About):
 * logo, nav with active highlight, and a consistent top-right of language
 * selector + auth (UserMenu when signed in, sign-in button when the deployment
 * has auth enabled). The chat workspace and splash keep their own headers.
 */
export default function PageHeader({
  sticky = true,
  maxWidthClass = "max-w-7xl",
}: {
  sticky?: boolean;
  maxWidthClass?: string;
}) {
  const { t } = useTranslation("pages");
  const { t: tc } = useTranslation("common");
  const { user, authRequired, signIn, signOut } = useAuthContext();
  const { pathname } = useLocation();

  const [discoveryLive, setDiscoveryLive] = useState(false);
  useEffect(() => {
    let alive = true;
    loadRegistry()
      .then((r) => alive && setDiscoveryLive(!!r && r.coverage?.mode !== "none"))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);
  const navItems = navItemsFor(discoveryLive);

  return (
    <header
      className={`border-b border-dark-border bg-dark-surface/80 backdrop-blur-sm z-50 flex-shrink-0 ${
        sticky ? "sticky top-0" : ""
      }`}
    >
      {/* Three zones: brand | nav (centered) | utilities — navigation and
          account/language controls are distinct groups, not one corner pile */}
      <div className={`${maxWidthClass} mx-auto px-4 py-3 flex items-center justify-between gap-4`}>
        <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity shrink-0">
          <img src="/logo.jpg" alt="UrbanLayer" className="w-6 h-6 rounded-full" />
          <span className="text-sm font-semibold tracking-tight">UrbanLayer</span>
        </Link>
        <nav className="flex-1 flex items-center justify-center gap-5 text-xs text-text-muted overflow-x-auto min-w-0 px-2">
          {navItems.map(({ to, key }) =>
            pathname === to.split("?")[0] && !to.includes("?") ? (
              <span key={to} className="text-accent shrink-0">{t(key)}</span>
            ) : (
              <Link key={to} to={to} className="hover:text-text-primary transition-colors shrink-0">
                {t(key)}
              </Link>
            )
          )}
        </nav>
        <div className="flex items-center gap-2 shrink-0">
          <LanguageSelector />
          {user ? (
            <UserMenu user={user} onSignOut={signOut} />
          ) : authRequired ? (
            <button
              onClick={signIn}
              className="text-[11px] text-text-secondary hover:text-text-primary border border-dark-border rounded-lg px-2.5 py-1 transition-colors"
            >
              {tc("signInShort")}
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
