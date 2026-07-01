import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuthContext } from "../contexts/AuthContext";
import { loadRegistry } from "../discovery/registryClient";
import LanguageSelector from "./LanguageSelector";
import ThemeToggle from "./ThemeToggle";
import UserMenu from "./UserMenu";

// ── Nav model (single source; re-exported by PageHeader for the nav test) ───────────────
// The returning-user nav: the parcel Scorecard, the labeled analyst chat door, and price.
// "Ask the analyst" (→ ?ask=1) opens an empty, UNGROUNDED chat. About is unlinked from the
// customer nav (route still resolves by URL; provenance lives in the footer).
const NAV_ITEMS: { to: string; key: string }[] = [
  { to: "/scorecard", key: "nav.scorecard" },
  { to: "/?ask=1", key: "nav.askAnalyst" },
  { to: "/pricing", key: "nav.pricing" },
];

// Discovery is linked only once its index has data (coverage != "none"); the check rides the
// cached discovery registry (one shared fetch). It sits after Scorecard, before Pricing.
const DISCOVERY_ITEM = { to: "/discovery", key: "nav.discovery" };

export function navItemsFor(discoveryLive: boolean): { to: string; key: string }[] {
  if (!discoveryLive) return NAV_ITEMS;
  return [...NAV_ITEMS.slice(0, 1), DISCOVERY_ITEM, ...NAV_ITEMS.slice(1)];
}

type Position = "floating" | "docked" | "hero";
type Tone = "solid" | "overImage";

interface FloatingNavProps {
  /** Layout mode. floating = rounded pill sticky at top-3 (marketing/tool pages);
   *  docked = full-width blur bar sticky at top-0 (chat workspace);
   *  hero = in-flow pill over the splash image (scrolls away). */
  position?: Position;
  /** solid = token chrome; overImage = translucent white for over-photo (hero). */
  tone?: Tone;
  /** Show the centered nav links. Off for shared read-only views. */
  showNav?: boolean;
  /** Max width of the inner bar (floating/hero). */
  maxWidthClass?: string;
  /** Brand target when it's a link (default "/"). Ignored if onBrandClick is set. */
  brandTo?: string;
  /** Makes the brand a button (workspace reset / splash scroll-to-top) instead of a link. */
  onBrandClick?: () => void;
  /** Trailing brand text/breadcrumb (e.g. "— Chicago", community-area crumb). */
  brandSuffix?: ReactNode;
  /** Leading context controls (history toggle, mobile data toggle). */
  contextLeft?: ReactNode;
  /** Trailing context actions rendered before theme/lang (export/share/new-chat/admin). */
  contextRight?: ReactNode;
  /** LanguageSelector variant. */
  languageVariant?: "splash" | "workspace";
  /** Custom sign-in control when signed out (workspace "Sign in to save"). Overrides the
   *  default page sign-in button. */
  signInSlot?: ReactNode;
  /** Hide the theme/lang/auth cluster entirely (shared view supplies its own CTA via contextRight). */
  hideUtilities?: boolean;
}

/**
 * The one nav for the whole app — a floating pill on marketing/tool pages and the splash
 * hero, a docked blur bar in the chat workspace. Owns the brand mark, centered nav links,
 * and the theme/language/account cluster; page- or workspace-specific controls come in via
 * the contextLeft / contextRight / signInSlot slots so their handlers stay with their owner.
 */
export default function FloatingNav({
  position = "floating",
  tone = "solid",
  showNav = true,
  maxWidthClass = "max-w-6xl",
  brandTo = "/",
  onBrandClick,
  brandSuffix,
  contextLeft,
  contextRight,
  languageVariant = "splash",
  signInSlot,
  hideUtilities = false,
}: FloatingNavProps) {
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

  const over = tone === "overImage";

  // Outer positioning + inner-bar chrome per mode.
  const outer =
    position === "docked"
      ? "sticky top-0 z-40 shrink-0"
      : position === "hero"
        ? "relative z-40 px-3 pt-3"
        : "sticky top-3 z-40 px-3 shrink-0"; // floating
  const bar =
    position === "docked"
      ? `w-full h-14 px-3 md:px-6 flex items-center justify-between gap-3 border-b backdrop-blur-md ${
          over ? "border-white/10 bg-black/30" : "border-dark-border bg-dark-surface/80"
        }`
      : `${maxWidthClass} mx-auto h-14 px-3 md:px-5 flex items-center justify-between gap-3 md:grid md:grid-cols-[1fr_auto_1fr] rounded-full border backdrop-blur-md shadow-glow ${
          over ? "border-white/15 bg-black/25" : "border-dark-border bg-dark-surface/70"
        }`;

  const brandText = over ? "text-white/90 group-hover:text-white" : "text-text-primary";
  const linkBase = "shrink-0 text-body transition-colors pb-0.5 border-b-2";
  const linkActive = over ? "border-white/70 text-white" : "border-accent text-text-primary";
  const linkIdle = over
    ? "border-transparent text-white/80 hover:text-white"
    : "border-transparent text-text-secondary hover:text-text-primary";

  const brandInner = (
    <>
      <img src="/logo.jpg" alt="" className="w-7 h-7 rounded-full group-hover:scale-105 transition-transform" />
      <span className={`font-display text-base font-semibold tracking-tight transition-colors ${brandText}`}>
        UrbanLayer
      </span>
      {brandSuffix}
    </>
  );

  return (
    <div className={outer}>
      <div className={bar}>
        {/* Left zone: context controls + brand */}
        <div className="flex items-center gap-4 min-w-0 md:justify-self-start">
          {contextLeft}
          {onBrandClick ? (
            <button onClick={onBrandClick} className="flex items-center gap-2 group shrink-0 min-w-0">
              {brandInner}
            </button>
          ) : (
            <Link to={brandTo} className="flex items-center gap-2 group shrink-0">
              {brandInner}
            </Link>
          )}
        </div>

        {/* Center zone: nav links, truly centered (equal-width side columns). A placeholder
            keeps the 3-column grid intact when nav is hidden so the right zone stays pinned. */}
        {showNav ? (
          <nav className="hidden md:flex items-center gap-7 md:justify-self-center">
            {navItems.map(({ to, key }) => {
              const active = pathname === to.split("?")[0] && !to.includes("?");
              return (
                <Link
                  key={to}
                  to={to}
                  aria-current={active ? "page" : undefined}
                  className={`${linkBase} ${active ? linkActive : linkIdle}`}
                >
                  {t(key)}
                </Link>
              );
            })}
          </nav>
        ) : (
          <span className="hidden md:block" aria-hidden="true" />
        )}

        {/* Right zone: page/workspace actions, then the shared utilities cluster */}
        <div className="flex items-center gap-2 shrink-0 md:justify-self-end">
          {contextRight}
          {!hideUtilities && (
            <>
              <ThemeToggle overImage={over} />
              <LanguageSelector variant={languageVariant} />
              {user ? (
                <UserMenu user={user} onSignOut={signOut} />
              ) : signInSlot ? (
                signInSlot
              ) : authRequired ? (
                <button
                  onClick={signIn}
                  className={`text-caption rounded-full px-3 py-1 border transition-colors ${
                    over
                      ? "text-white/80 hover:text-white border-white/20"
                      : "text-text-secondary hover:text-text-primary border-dark-border"
                  }`}
                >
                  {tc("signInShort")}
                </button>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
