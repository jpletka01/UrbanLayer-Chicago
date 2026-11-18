// The admin sections as the page's own sidebar, built like the chat's list (owner, 2026-11-17: "I might expect it to
// work a little bit like it does in the chat"): beside the main panel on a wide screen, hiding to a strip of icons in
// place; below `lg` a sheet from the left, opened from the top bar. A badge on a section's icon counts what is waiting
// there (Reddit's notification style, owner 2026-11-17).
import { Link } from "react-router-dom";
import {
  Activity, BadgeCheck, HeartPulse, LayoutDashboard, ListTree, PanelLeftClose, PanelLeftOpen, PencilLine, Scale, Ticket, Users,
  type LucideIcon,
} from "lucide-react";
import { STROKE } from "../icons";
import { ADMIN_SECTIONS, badgeText, type AdminSectionId, type Badge } from "./adminModel";

export const SECTION_ICON: Record<AdminSectionId, LucideIcon> = {
  overview: LayoutDashboard, usage: Activity, visitors: Users, quality: BadgeCheck, requests: ListTree,
  data: HeartPulse, corrections: PencilLine, code: Scale, access: Ticket,
};

const BADGE_TONE = { red: "bg-nx-pill-red text-nx-page", work: "bg-nx-primary text-nx-primary-fg" } as const;

/** Reddit-style: a small solid pill on the icon's top-right corner, ringed in the page color so it cuts out of the
    icon, bold digits; a dot when there is nothing to count. Wrap the icon in `relative`. */
export function NotificationBadge({ badge, testId }: { badge: Badge; testId?: string }) {
  const text = badgeText(badge.count);
  return text == null ? (
    <span aria-hidden data-testid={testId} data-dot="" className={`absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-nx-page ${BADGE_TONE[badge.tone]}`} />
  ) : (
    <span aria-hidden data-testid={testId}
      className={`absolute -right-[11px] -top-[9px] flex h-[15px] min-w-[15px] items-center justify-center rounded-full px-[3px] font-sans text-[10px] font-bold leading-none tabular-nums ring-2 ring-nx-page ${BADGE_TONE[badge.tone]}`}>
      {text}
    </span>
  );
}

export function AdminNav({ current, badges, onHide, onNavigate }: {
  current: AdminSectionId;
  badges: Partial<Record<AdminSectionId, Badge>>;
  /** Absent in the phone sheet, which has its own close button. */
  onHide?: () => void;
  onNavigate?: () => void;
}) {
  return (
    <nav aria-label="Admin sections" className="flex h-full w-[240px] max-w-[85vw] flex-col gap-2 px-3 py-5" data-testid="admin-nav">
      <div className="flex items-center gap-2 px-1">
        <h2 className="flex-1 font-medium">Admin</h2>
        {onHide && (
          <button type="button" onClick={onHide} aria-label="Hide sections" title="Hide sections" className="grid h-7 w-7 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon" data-testid="admin-nav-hide">
            <PanelLeftClose aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
          </button>
        )}
      </div>
      <ul className="mt-1 flex flex-col gap-0.5">
        {ADMIN_SECTIONS.map((s, i) => {
          const Icon = SECTION_ICON[s.id];
          const badge = badges[s.id];
          const on = s.id === current;
          return (
            <li key={s.id}>
              {i > 0 && ADMIN_SECTIONS[i - 1].group !== s.group && <div className="mx-2.5 my-2 border-t border-nx-ink/10" />}
              <Link to={`/admin/${s.id}`} onClick={onNavigate} aria-current={on ? "page" : undefined}
                aria-label={badge ? `${s.label}, ${badge.spoken}` : undefined}
                className={`flex h-9 items-center gap-3.5 rounded-xl px-2.5 touch-target ${on ? "bg-nx-ink/[0.07] font-medium" : "hover:bg-nx-ink/5"}`}>
                <span className="relative inline-flex shrink-0">
                  <Icon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
                  {badge && <NotificationBadge badge={badge} testId={`admin-badge-${s.id}`} />}
                </span>
                <span className="flex-1">{s.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** The sections folded: the button that opens them again where the hide button was, then each section's icon with its
    badge. */
export function AdminNavStrip({ current, badges, onShow }: {
  current: AdminSectionId;
  badges: Partial<Record<AdminSectionId, Badge>>;
  onShow: () => void;
}) {
  return (
    <nav aria-label="Admin sections" className="flex h-full w-14 flex-col items-center gap-1 py-5" data-testid="admin-nav-strip">
      <button type="button" onClick={onShow} aria-label="Show sections" title="Show sections" className="mb-2 grid h-7 w-9 place-items-center rounded-xl hover:bg-nx-ink/5 touch-icon" data-testid="admin-nav-expand">
        <PanelLeftOpen aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
      </button>
      {ADMIN_SECTIONS.map((s) => {
        const Icon = SECTION_ICON[s.id];
        const badge = badges[s.id];
        return (
          <Link key={s.id} to={`/admin/${s.id}`} aria-current={s.id === current ? "page" : undefined} title={s.label}
            aria-label={badge ? `${s.label}, ${badge.spoken}` : s.label}
            className={`relative grid h-9 w-9 place-items-center rounded-xl touch-icon ${s.id === current ? "bg-nx-ink/[0.07]" : "hover:bg-nx-ink/5"}`}>
            <span className="relative inline-flex">
              <Icon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
              {badge && <NotificationBadge badge={badge} />}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
