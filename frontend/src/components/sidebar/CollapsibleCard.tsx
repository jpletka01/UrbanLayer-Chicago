import { useState, type ReactNode } from "react";

interface Props {
  title: string;
  icon?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}

export function CollapsibleCard({ title, icon, defaultOpen = true, children }: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-xl bg-dark-surface/80 backdrop-blur-sm border border-dark-border overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-xs font-medium text-text-muted
                   uppercase tracking-wider hover:text-text-secondary transition-colors"
      >
        <svg
          className={`w-3 h-3 shrink-0 transition-transform duration-200 ${open ? "" : "-rotate-90"}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
        {icon && <span className="shrink-0">{icon}</span>}
        {title}
      </button>
      {open && <div className="px-4 pb-3">{children}</div>}
    </div>
  );
}
