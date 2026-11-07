// The side panel (decision Items 73–74): the logo, one row per destination from the readiness registry
// (Saved stays hidden until its route exists), a small past-chats menu beside Chat, and the account at the
// bottom. A button inside the panel collapses it to a strip of icons; labels stay as tooltips and
// accessible names. On a phone the same content opens as a sheet from the top bar's menu button.
import { useId, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronRight, LogIn, LogOut, Monitor, Moon, PanelLeftClose, PanelLeftOpen, Plus, Settings, Sun } from "lucide-react";
import { listConversations } from "../../lib/api";
import type { Conversation } from "../../lib/types";
import { useAuthContext } from "../../contexts/AuthContext";
import { useThemeContext } from "../../contexts/ThemeContext";
import { navEntries } from "../readiness";
import { ICON, NAV_ICON, STROKE } from "../icons";

const MENU = "z-[70] min-w-[220px] rounded-2xl bg-nx-page p-1.5 text-body text-nx-ink shadow-[0_8px_32px_rgb(0_0_0/0.14)] ring-1 ring-nx-ink/10";
const MENU_ITEM = "flex cursor-pointer select-none items-center gap-2 rounded-xl px-2.5 py-1.5 outline-none data-[highlighted]:bg-nx-ink/5 data-[disabled]:cursor-default data-[disabled]:opacity-60";

export function SidePanel({
  collapsed = false,
  onToggleCollapsed,
  onNavigate,
}: {
  collapsed?: boolean;
  /** Absent on the phone sheet, which has its own close button. */
  onToggleCollapsed?: () => void;
  /** Called after a destination is chosen (the phone sheet closes itself). */
  onNavigate?: () => void;
}) {
  const { t } = useTranslation("next");
  const { pathname } = useLocation();

  return (
    <nav
      aria-label={t("frame.panel")}
      className={`flex h-full flex-col gap-1 px-3 py-5 ${collapsed ? "w-16 items-center" : "w-[212px]"}`}
      data-collapsed={collapsed || undefined}
    >
      <div className={`mb-3 flex items-center gap-2 px-2 ${collapsed ? "flex-col" : ""}`}>
        <Link to="/" onClick={onNavigate} className="flex min-w-0 items-center gap-2 rounded-lg py-1 font-medium" aria-label="UrbanLayer">
          <span aria-hidden className="h-6 w-6 shrink-0 rounded-full bg-nx-ink" />
          {!collapsed && <span className="truncate">UrbanLayer</span>}
        </Link>
        {onToggleCollapsed && (
          <button
            type="button"
            onClick={onToggleCollapsed}
            aria-label={collapsed ? t("frame.expand") : t("frame.collapse")}
            title={collapsed ? t("frame.expand") : t("frame.collapse")}
            className={`grid h-7 w-7 place-items-center rounded-lg hover:bg-nx-ink/5 ${collapsed ? "" : "ml-auto"}`}
          >
            {collapsed
              ? <PanelLeftOpen aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
              : <PanelLeftClose aria-hidden className="h-4 w-4" strokeWidth={STROKE} />}
          </button>
        )}
      </div>

      <ul className="flex flex-col gap-1" role="list">
        {navEntries().map((entry) => {
          const nav = entry.nav!;
          const Icon = NAV_ICON[nav.icon];
          const label = t(nav.labelKey);
          const active = entry.status === "ready" && pathname === entry.path;
          return (
            nav.icon === "chat" && !collapsed ? (
              <ChatFolder key={entry.id} label={label} onNavigate={onNavigate} />
            ) : (
            <li key={entry.id} className="relative flex items-center">
              <Link
                to={nav.to}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                title={collapsed ? label : undefined}
                aria-label={collapsed ? label : undefined}
                className={`relative flex h-9 flex-1 items-center gap-2 rounded-xl px-2 touch-target ${active ? "bg-nx-ink/5 font-medium" : "hover:bg-nx-ink/5"} ${collapsed ? "justify-center" : ""}`}
              >
                {active && <span aria-hidden className="absolute left-0 top-2.5 h-4 w-1 rounded-sm bg-nx-ink" />}
                <Icon aria-hidden className="h-5 w-5 shrink-0" strokeWidth={STROKE} />
                {!collapsed && <span className="truncate">{label}</span>}
              </Link>
            </li>
            )
          );
        })}
      </ul>

      <div className="mt-auto">
        <AccountMenu collapsed={collapsed} />
      </div>
    </nav>
  );
}

/** Chat as a folder (owner review 2026-11-07): the row opens and closes like a directory; inside, "New chat" first,
    then a signed-in visitor's recent conversations. Both open today's chat page (its route isn't rebuilt yet). */
function ChatFolder({ label, onNavigate }: { label: string; onNavigate?: () => void }) {
  const { t } = useTranslation("next");
  const { isAuthenticated, authRequired, signIn } = useAuthContext();
  const canList = isAuthenticated || !authRequired;
  const [open, setOpen] = useState(false);
  const [chats, setChats] = useState<Conversation[] | null>(null);
  const listId = useId();
  const Icon = NAV_ICON.chat;

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && canList && chats === null) {
      listConversations().then((c) => setChats(c.slice(0, 8))).catch(() => setChats([]));
    }
  };

  const child = "flex h-8 items-center gap-2 rounded-lg pl-9 pr-2 text-caption hover:bg-nx-ink/5 touch-target";
  return (
    <li className="flex flex-col">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={listId}
        className="flex h-9 items-center gap-2 rounded-xl px-2 text-left hover:bg-nx-ink/5 touch-target"
      >
        <Icon aria-hidden className="h-5 w-5 shrink-0" strokeWidth={STROKE} />
        <span className="flex-1 truncate">{label}</span>
        <ChevronRight aria-hidden className={`h-4 w-4 shrink-0 transition-transform ${open ? "rotate-90" : ""}`} strokeWidth={STROKE} />
      </button>
      {open && (
        <ul id={listId} role="list" className="mt-0.5 flex flex-col gap-0.5" data-testid="chat-folder">
          <li>
            <Link to="/?ask=1" onClick={onNavigate} className={`${child} font-medium`}>
              <Plus aria-hidden className="h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} />
              {t("frame.newChat")}
            </Link>
          </li>
          {!canList ? (
            <li>
              <button type="button" onClick={signIn} className={`${child} w-full text-left nx-muted`}>
                <LogIn aria-hidden className="h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} />
                {t("frame.signInForChats")}
              </button>
            </li>
          ) : chats === null ? (
            <li className="pl-9 text-caption nx-muted" role="status">{t("frame.loading")}</li>
          ) : chats.length === 0 ? (
            <li className="pl-9 text-caption nx-muted">{t("frame.noChats")}</li>
          ) : (
            chats.map((c) => (
              <li key={c.id}>
                <Link to={`/c/${c.id}`} onClick={onNavigate} className={child} title={c.title || undefined}>
                  <span className="truncate">{c.title || t("frame.untitledChat")}</span>
                </Link>
              </li>
            ))
          )}
        </ul>
      )}
    </li>
  );
}

/** The account at the bottom of the panel: theme, language, settings, sign in or out. */
function AccountMenu({ collapsed }: { collapsed: boolean }) {
  const { t, i18n } = useTranslation("next");
  const { user, isAuthenticated, authRequired, signIn, signOut } = useAuthContext();
  const { theme, setTheme } = useThemeContext();
  const navigate = useNavigate();
  const AccountIcon = ICON.account;
  const name = user?.name || t("frame.account");
  const setLanguage = (lng: "en" | "es") => {
    i18n.changeLanguage(lng);
    try { localStorage.setItem("urbanlayer-language", lng); } catch { /* the choice still holds for this page */ }
  };

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger
        aria-label={collapsed ? name : undefined}
        title={collapsed ? name : undefined}
        className={`flex h-10 w-full items-center gap-2 rounded-xl px-2 hover:bg-nx-ink/5 touch-target ${collapsed ? "justify-center" : ""}`}
      >
        {user?.picture_url
          ? <img src={user.picture_url} alt="" className="h-6 w-6 shrink-0 rounded-full" referrerPolicy="no-referrer" />
          : <AccountIcon aria-hidden className="h-6 w-6 shrink-0" strokeWidth={STROKE} />}
        {!collapsed && <span className="truncate">{name}</span>}
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <div className="ui-next">
          <DropdownMenu.Content side="top" align="start" sideOffset={6} className={MENU}>
            <DropdownMenu.Label className="px-2.5 py-1 text-caption nx-muted">{t("frame.theme")}</DropdownMenu.Label>
            <DropdownMenu.RadioGroup value={theme} onValueChange={(v) => setTheme(v as "light" | "dark" | "system")}>
              {([["light", Sun], ["dark", Moon], ["system", Monitor]] as const).map(([value, Icon]) => (
                <DropdownMenu.RadioItem key={value} value={value} className={`${MENU_ITEM} data-[state=checked]:font-semibold`}>
                  <Icon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
                  {t(`frame.themes.${value}`)}
                </DropdownMenu.RadioItem>
              ))}
            </DropdownMenu.RadioGroup>
            <DropdownMenu.Separator className="my-1 h-px bg-nx-ink/10" />
            <DropdownMenu.Label className="px-2.5 py-1 text-caption nx-muted">{t("frame.language")}</DropdownMenu.Label>
            <DropdownMenu.RadioGroup value={i18n.language.startsWith("es") ? "es" : "en"} onValueChange={(v) => setLanguage(v as "en" | "es")}>
              <DropdownMenu.RadioItem value="en" className={`${MENU_ITEM} data-[state=checked]:font-semibold`} lang="en">English</DropdownMenu.RadioItem>
              <DropdownMenu.RadioItem value="es" className={`${MENU_ITEM} data-[state=checked]:font-semibold`} lang="es">Español</DropdownMenu.RadioItem>
            </DropdownMenu.RadioGroup>
            {authRequired && (
              <>
                <DropdownMenu.Separator className="my-1 h-px bg-nx-ink/10" />
                {isAuthenticated ? (
                  <>
                    <DropdownMenu.Item className={MENU_ITEM} onSelect={() => navigate("/settings")}>
                      <Settings aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
                      {t("frame.settings")}
                    </DropdownMenu.Item>
                    <DropdownMenu.Item className={MENU_ITEM} onSelect={() => { void signOut(); }}>
                      <LogOut aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
                      {t("frame.signOut")}
                    </DropdownMenu.Item>
                  </>
                ) : (
                  <DropdownMenu.Item className={MENU_ITEM} onSelect={signIn}>
                    <LogIn aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
                    {t("frame.signIn")}
                  </DropdownMenu.Item>
                )}
              </>
            )}
          </DropdownMenu.Content>
        </div>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
