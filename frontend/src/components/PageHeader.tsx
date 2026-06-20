import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuthContext } from "../contexts/AuthContext";
import { loadRegistry } from "../discovery/registryClient";
import LanguageSelector from "./LanguageSelector";
import UserMenu from "./UserMenu";

const NAV_ITEMS: { to: string; key: string }[] = [
  // The nav carries only verbs on a parcel + its price. Chat ("Analyst") was
  // removed — it's reached contextually (Investigate, persona cards, the address
  // box's failure-recovery handoff), never as a co-equal top-level destination.
  // About is unlinked from the customer UI (the /about route still resolves by
  // direct URL); provenance lives in the homepage footer.
  { to: "/scorecard", key: "nav.scorecard" },
  { to: "/pricing", key: "nav.pricing" },
];

// Discovery is linked only once its index actually has data (coverage != "none"); while
// dormant it stays unlinked. The check rides the cached discovery registry, so it's one
// shared fetch, not per-page work. (It took Explore's old nav slot — after Scorecard —
// when /explore was retired 2026-06-14.)
const DISCOVERY_ITEM = { to: "/discovery", key: "nav.discovery" };

export function navItemsFor(discoveryLive: boolean): { to: string; key: string }[] {
  if (!discoveryLive) return NAV_ITEMS;
  return [...NAV_ITEMS.slice(0, 1), DISCOVERY_ITEM, ...NAV_ITEMS.slice(1)]; // after Scorecard, before Pricing
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
      <div className={`${maxWidthClass} mx-auto px-4 h-14 flex items-center justify-between gap-4`}>
        {/* Left group: brand + nav read as one anchored unit (not a centered float) */}
        <div className="flex items-center gap-6 min-w-0">
          <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity shrink-0">
            <img src="/logo.jpg" alt="" className="w-7 h-7 rounded-full" />
            <span className="font-display text-base font-semibold tracking-tight">UrbanLayer</span>
          </Link>
          <nav className="flex items-center gap-5 text-body overflow-x-auto min-w-0">
            {navItems.map(({ to, key }) => {
              const active = pathname === to.split("?")[0] && !to.includes("?");
              return (
                <Link
                  key={to}
                  to={to}
                  aria-current={active ? "page" : undefined}
                  className={`shrink-0 border-b-2 pb-0.5 transition-colors ${
                    active
                      ? "border-accent text-text-primary"
                      : "border-transparent text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {t(key)}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <LanguageSelector />
          {user ? (
            <UserMenu user={user} onSignOut={signOut} />
          ) : authRequired ? (
            <button
              onClick={signIn}
              className="text-caption text-text-secondary hover:text-text-primary border border-dark-border rounded-lg px-2.5 py-1 transition-colors"
            >
              {tc("signInShort")}
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
