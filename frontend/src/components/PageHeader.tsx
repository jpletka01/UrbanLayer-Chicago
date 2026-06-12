import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuthContext } from "../contexts/AuthContext";
import LanguageSelector from "./LanguageSelector";
import UserMenu from "./UserMenu";

const NAV_ITEMS: { to: string; key: string }[] = [
  { to: "/", key: "nav.chat" },
  { to: "/scorecard", key: "nav.scorecard" },
  { to: "/explore", key: "nav.explore" },
  { to: "/pricing", key: "nav.pricing" },
  { to: "/about", key: "nav.about" },
];

/**
 * Standard header for the non-chat pages (Scorecard, Explore, Pricing, About):
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

  return (
    <header
      className={`border-b border-dark-border bg-dark-surface/80 backdrop-blur-sm z-50 flex-shrink-0 ${
        sticky ? "sticky top-0" : ""
      }`}
    >
      <div className={`${maxWidthClass} mx-auto px-4 py-3 flex items-center justify-between gap-4`}>
        <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity shrink-0">
          <img src="/logo.jpg" alt="UrbanLayer" className="w-6 h-6 rounded-full" />
          <span className="text-sm font-semibold tracking-tight">UrbanLayer</span>
        </Link>
        <div className="flex items-center gap-4 min-w-0">
          <nav className="flex items-center gap-4 text-[11px] text-text-muted overflow-x-auto">
            {NAV_ITEMS.map(({ to, key }) =>
              pathname === to ? (
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
      </div>
    </header>
  );
}
