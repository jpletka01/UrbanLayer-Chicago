import type { SidebarView } from "../lib/types";

interface Props {
  title: string;
  subtitle?: string;
  activeView: SidebarView;
  onViewChange: (view: SidebarView) => void;
  hasCodeChunks: boolean;
}

export function SidebarHeader({
  title,
  subtitle,
  activeView,
  onViewChange,
  hasCodeChunks,
}: Props) {
  return (
    <header className="px-4 py-3 border-b border-dark-border shrink-0">
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-text-primary truncate">{title}</h2>
          {subtitle && (
            <p className="text-xs text-text-muted mt-0.5">{subtitle}</p>
          )}
        </div>

        {hasCodeChunks && (
          <div className="flex items-center gap-0.5 bg-dark-bg rounded-lg p-0.5 shrink-0 ml-3">
            <button
              onClick={() => onViewChange("data")}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-150
                ${
                  activeView === "data"
                    ? "bg-dark-surface text-text-primary shadow-sm"
                    : "text-text-muted hover:text-text-secondary"
                }`}
            >
              Data
            </button>
            <button
              onClick={() => onViewChange("sources")}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-150
                ${
                  activeView === "sources"
                    ? "bg-dark-surface text-text-primary shadow-sm"
                    : "text-text-muted hover:text-text-secondary"
                }`}
            >
              Sources
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
