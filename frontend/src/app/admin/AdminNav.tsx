// The admin sections as the page's own sidebar, built like the chat's list (owner, 2026-11-17: "I might expect it to
// work a little bit like it does in the chat"): beside the main panel on a wide screen, hiding to a strip of icons in
// place; below `lg` a sheet from the left, opened from the top bar. A badge on a section counts what is waiting there.
import { Link } from "react-router-dom";
import {
  Activity, BadgeCheck, HeartPulse, LayoutDashboard, ListTree, PanelLeftClose, PanelLeftOpen, PencilLine, Scale, Ticket, Users,
  type LucideIcon,
} from "lucide-react";
import { STROKE } from "../icons";
import { ADMIN_SECTIONS, type AdminSectionId, type Badge } from "./adminModel";

export const SECTION_ICON: Record<AdminSectionId, LucideIcon> = {
  overview: LayoutDashboard, usage: Activity, visitors: Users, quality: BadgeCheck, requests: ListTree,
  data: HeartPulse, corrections: PencilLine, code: Scale, access: Ticket,
};

const BADGE_CLS = { red: "bg-nx-pill-red text-nx-page", work: "bg-nx-primary text-nx-primary-fg" } as const;

function BadgeCount({ badge, testId }: { badge: Badge; testId?: string }) {
  return (
    <span aria-hidden data-testid={testId}
      className={`grid h-[18px] min-w-[18px] place-items-center rounded-full px-1 text-[11px] font-semibold leading-none tabular-nums ${BADGE_CLS[badge.tone]}`}>
      {badge.text}
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
                className={`flex h-9 items-center gap-2.5 rounded-xl px-2.5 touch-target ${on ? "bg-nx-ink/[0.07] font-medium" : "hover:bg-nx-ink/5"}`}>
                <Icon aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />
                <span className="flex-1">{s.label}</span>
                {badge && <BadgeCount badge={badge} testId={`admin-badge-${s.id}`} />}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** The sections folded: the button that opens them again where the hide button was, then each section's icon (a dot
    where something is waiting). */
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
            <Icon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
            {badge && <span aria-hidden className={`absolute right-1 top-1 h-2 w-2 rounded-full ${badge.tone === "red" ? "bg-nx-pill-red" : "bg-nx-primary"}`} />}
          </Link>
        );
      })}
    </nav>
  );
}
