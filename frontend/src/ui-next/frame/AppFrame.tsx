// The new UI's frame (decision Items 73–74, 76): the `.ui-next` root, the side panel on the left (left is for
// getting around), the top bar with a breadcrumb and the page's tools, and an optional drawer slot on the
// right (right is for the analyst). Below `lg` the panel opens as a sheet from the top bar's menu button.
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { Menu, X } from "lucide-react";
import { SidePanel } from "./SidePanel";
import { STROKE } from "../icons";

const COLLAPSE_KEY = "urbanlayer-next-panel";

function readCollapsed(): boolean {
  try { return localStorage.getItem(COLLAPSE_KEY) === "collapsed"; } catch { return false; }
}

export function AppFrame({
  crumbs,
  tools,
  drawer,
  bar,
  children,
}: {
  /** The breadcrumb, first to last; the last one is the current page. */
  crumbs: ReactNode[];
  /** The page's tool icons, right of the top bar (the Profile: Ask, Sources, Export). */
  tools?: ReactNode;
  /** The right-hand drawer (the analyst), rendered beside the content when open. */
  drawer?: ReactNode;
  /** The page's own controls in place of the breadcrumb (Discovery's search and filters, Item 104); the breadcrumb
      stays for screen readers. */
  bar?: ReactNode;
  children: ReactNode;
}) {
  const { t } = useTranslation("next");
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [menuOpen, setMenuOpen] = useState(false);
  const toggle = () => {
    setCollapsed((c) => {
      try { localStorage.setItem(COLLAPSE_KEY, c ? "open" : "collapsed"); } catch { /* per-viewer convenience only */ }
      return !c;
    });
  };

  return (
    <div
      className="ui-next flex min-h-dvh bg-nx-page font-sans text-body text-nx-ink"
      data-ui-version="next"
    >
      <aside className="sticky top-0 hidden h-dvh shrink-0 border-r border-nx-ink/10 lg:block">
        <SidePanel collapsed={collapsed} onToggleCollapsed={toggle} />
      </aside>

      <div className="flex min-w-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-[68px] items-center gap-2 border-b border-nx-ink/10 px-4 sm:px-7">
            <Dialog.Root open={menuOpen} onOpenChange={setMenuOpen}>
              <Dialog.Trigger
                className="-ml-1 grid h-9 w-9 shrink-0 place-items-center rounded-lg hover:bg-nx-ink/5 lg:hidden touch-target"
                aria-label={t("frame.openMenu")}
              >
                <Menu aria-hidden className="h-5 w-5" strokeWidth={STROKE} />
              </Dialog.Trigger>
              <Dialog.Portal>
                <div className="ui-next">
                  <Dialog.Overlay className="fixed inset-0 z-[65] bg-black/30" />
                  <Dialog.Content className="fixed inset-y-0 left-0 z-[66] bg-nx-page text-body text-nx-ink shadow-[0_8px_32px_rgb(0_0_0/0.2)] focus:outline-none">
                    <Dialog.Title className="sr-only">{t("frame.panel")}</Dialog.Title>
                    <Dialog.Description className="sr-only">{t("frame.panelHint")}</Dialog.Description>
                    <Dialog.Close
                      className="absolute right-2 top-5 grid h-8 w-8 place-items-center rounded-lg hover:bg-nx-ink/5 touch-target"
                      aria-label={t("frame.closeMenu")}
                    >
                      <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
                    </Dialog.Close>
                    <SidePanel onNavigate={() => setMenuOpen(false)} />
                  </Dialog.Content>
                </div>
              </Dialog.Portal>
            </Dialog.Root>

            {bar && <div className="min-w-0 flex-1">{bar}</div>}
            <nav aria-label={t("frame.breadcrumb")} className={bar ? "sr-only" : "min-w-0 flex-1"}>
              <ol className="flex min-w-0 items-center gap-2">
                {crumbs.map((c, i) => {
                  const last = i === crumbs.length - 1;
                  return (
                    <li key={i} className={`flex min-w-0 items-center gap-2 ${last ? "" : "hidden shrink-0 sm:flex"}`}>
                      {i > 0 && <span aria-hidden className="nx-muted hidden sm:inline">/</span>}
                      <span className={`truncate ${last ? "" : "nx-muted"}`} aria-current={last ? "page" : undefined}>{c}</span>
                    </li>
                  );
                })}
              </ol>
            </nav>
            {tools && <div className="flex shrink-0 items-center gap-1">{tools}</div>}
          </header>

          <main className="min-w-0 flex-1">{children}</main>
        </div>
        {drawer}
      </div>
    </div>
  );
}

/** An icon-only tool button for the top bar (Ask, Sources, Export only; Item 75). */
export function ToolButton({
  label,
  icon: Icon,
  onClick,
  pressed,
  controls,
  testId,
  disabled,
}: {
  label: string;
  icon: React.ComponentType<{ className?: string; strokeWidth?: number; "aria-hidden"?: boolean }>;
  onClick: () => void;
  pressed?: boolean;
  controls?: string;
  testId?: string;
  /** Held in place but not usable yet (the Profile's first screen, before the full response). */
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      aria-controls={controls}
      data-testid={testId}
      className={`grid h-9 w-9 place-items-center rounded-lg touch-target disabled:cursor-not-allowed disabled:opacity-40 ${pressed ? "bg-nx-ink/5" : "hover:bg-nx-ink/5"}`}
    >
      <Icon aria-hidden className="h-5 w-5" strokeWidth={STROKE} />
    </button>
  );
}
