// Toggletip — an explanation behind an icon (decision Items 49, 54). On a mouse, hovering the icon
// previews it (Jack, 2026-11-02) and moving into the popover keeps it open, so its links can be
// clicked (WCAG 1.4.13: hoverable, persistent, dismissible); a click pins it open. On touch there is
// no hover: a tap opens it. Escape (focus returns to the trigger), a second click or a click outside
// closes it.
//
// One icon, one meaning, everywhere (see ICON). A date that changes the decision keeps its year visible
// beside the calendar (`visible`).
import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Calendar, ChevronDown, Info, Scale, SquareArrowOutUpRight, type LucideIcon } from "lucide-react";

export type ToggletipKind = "info" | "date" | "code" | "source" | "more";

// The page's tool icons (Lucide; decision Item 54), one meaning each: info = explain, date = every date
// for this item, code = the Municipal Code rule, source = the official record, more = more detail.
const ICON: Record<ToggletipKind, LucideIcon> = {
  info: Info, date: Calendar, code: Scale, source: SquareArrowOutUpRight, more: ChevronDown,
};

export function Toggletip({
  kind = "info",
  label,
  visible,
  children,
  align = "start",
}: {
  kind?: ToggletipKind;
  /** The trigger's accessible name ("Source for Assessed value", "Date for …"). */
  label: string;
  /** Text shown beside the icon (e.g. the tax year); the icon alone when omitted. */
  visible?: ReactNode;
  children: ReactNode;
  align?: "start" | "end";
}) {
  const [pinned, setPinned] = useState(false);
  const [hovering, setHovering] = useState(false);
  const open = pinned || hovering;
  const id = useId();
  const wrapRef = useRef<HTMLSpanElement | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const popRef = useRef<HTMLSpanElement | null>(null);
  // A popover that would leave the window flips to the other edge of its trigger (set on the element itself,
  // before paint, so it never shows on the wrong side).
  useLayoutEffect(() => {
    const el = popRef.current;
    if (!open || !el) return;
    const r = el.getBoundingClientRect();
    if (align !== "end" && r.right > window.innerWidth - 8) { el.style.left = "auto"; el.style.right = "0"; }
    else if (align === "end" && r.left < 8) { el.style.right = "auto"; el.style.left = "0"; }
  }, [open, align]);
  const leaveTimer = useRef<number | null>(null);

  const close = () => {
    setPinned(false);
    setHovering(false);
  };

  useEffect(() => {
    if (!open) return;
    const onDown = (event: PointerEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) close();
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open]);

  useEffect(() => () => { if (leaveTimer.current) window.clearTimeout(leaveTimer.current); }, []);

  // Hover belongs to a mouse or pen; a touch "hover" would open on the tap before the click toggles it.
  const isHoverPointer = (event: { pointerType?: string }) => event.pointerType !== "touch";
  const onEnter = (event: { pointerType?: string }) => {
    if (!isHoverPointer(event)) return;
    if (leaveTimer.current) window.clearTimeout(leaveTimer.current);
    setHovering(true);
  };
  const onLeave = (event: { pointerType?: string }) => {
    if (!isHoverPointer(event)) return;
    // A short grace period lets the pointer cross the gap into the popover.
    leaveTimer.current = window.setTimeout(() => setHovering(false), 150);
  };

  return (
    <span ref={wrapRef} className="relative inline-flex align-baseline" data-toggletip={kind} onPointerEnter={onEnter} onPointerLeave={onLeave}>
      <button
        ref={buttonRef}
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => {
          // A click pins what the hover showed; clicking a pinned popover closes it.
          if (pinned) close();
          else setPinned(true);
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape" && open) {
            event.preventDefault();
            close();
          }
        }}
        className="inline-flex items-center gap-0.5 rounded px-0.5 text-text-muted cursor-pointer transition-colors hover:text-link focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        {visible != null && <span className="text-caption text-text-secondary">{visible}</span>}
        {(() => { const Icon = ICON[kind]; return <Icon aria-hidden className="h-3.5 w-3.5" strokeWidth={2} />; })()}
      </button>
      {open && (
        <span
          ref={popRef}
          id={id}
          role="dialog"
          aria-label={label}
          onKeyDown={(event) => {
            if (event.key !== "Escape") return;
            event.preventDefault();
            close();
            buttonRef.current?.focus();
          }}
          className={`absolute top-full z-30 mt-1 w-72 max-w-[80vw] rounded-lg border border-dark-border bg-dark-surface p-3 text-left text-caption font-normal normal-case tracking-normal text-text-secondary shadow-modal ${align === "end" ? "right-0" : "left-0"}`}
        >
          {children}
        </span>
      )}
    </span>
  );
}
