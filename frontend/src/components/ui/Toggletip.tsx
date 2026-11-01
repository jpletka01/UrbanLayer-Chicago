// Toggletip — a click-to-open explanation (decision Item 49). Hover tooltips are not available on
// touch and may not hold links, so everything that explains a figure (a date, a code section, a
// method) opens on click or tap from a real button, stays open while read, and closes with Escape
// (focus returns to the trigger), a second click, or a click outside.
//
// One icon, one meaning, everywhere: ⓘ = a source or code reference, ⏱ = a date, ▾ = more.
// A date that changes the decision keeps its year visible beside the icon (`visible`).
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

export type ToggletipKind = "info" | "date" | "more";

const ICON: Record<ToggletipKind, string> = { info: "ⓘ", date: "⏱", more: "▾" };

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
  const [open, setOpen] = useState(false);
  const id = useId();
  const wrapRef = useRef<HTMLSpanElement | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: PointerEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open]);

  return (
    <span ref={wrapRef} className="relative inline-flex align-baseline" data-toggletip={kind}>
      <button
        ref={buttonRef}
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(event) => {
          if (event.key === "Escape" && open) {
            event.preventDefault();
            setOpen(false);
          }
        }}
        className="inline-flex items-center gap-0.5 rounded px-0.5 text-text-muted cursor-pointer transition-colors hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        {visible != null && <span className="text-caption text-text-secondary">{visible}</span>}
        <span aria-hidden className="text-caption leading-none">{ICON[kind]}</span>
      </button>
      {open && (
        <span
          id={id}
          role="dialog"
          aria-label={label}
          onKeyDown={(event) => {
            if (event.key !== "Escape") return;
            event.preventDefault();
            setOpen(false);
            buttonRef.current?.focus();
          }}
          className={`absolute top-full z-30 mt-1 w-64 max-w-[80vw] rounded-lg border border-dark-border bg-dark-surface p-3 text-left text-caption font-normal normal-case tracking-normal text-text-secondary shadow-modal ${align === "end" ? "right-0" : "left-0"}`}
        >
          {children}
        </span>
      )}
    </span>
  );
}
