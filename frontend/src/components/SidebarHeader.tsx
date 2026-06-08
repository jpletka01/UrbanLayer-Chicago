import { useTranslation } from "react-i18next";
import type { SidebarView } from "../lib/types";

interface Props {
  title: string;
  subtitle?: string;
  activeView: SidebarView;
  onViewChange: (view: SidebarView) => void;
  hasCodeChunks: boolean;
  dataCount?: number;
  sourceCount?: number;
  showDataBadge?: boolean;
  showSourcesBadge?: boolean;
}

export function SidebarHeader({
  title,
  subtitle,
  activeView,
  onViewChange,
  hasCodeChunks,
  dataCount = 0,
  sourceCount = 0,
  showDataBadge = false,
  showSourcesBadge = false,
}: Props) {
  const { t } = useTranslation("sidebar");
  return (
    <div className="flex items-center justify-between flex-1 min-w-0">
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
            className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-150 inline-flex items-center gap-1.5
              ${
                activeView === "data"
                  ? "bg-dark-surface text-text-primary shadow-sm"
                  : "text-text-muted hover:text-text-secondary"
              }`}
          >
            {t("data")}
            {showDataBadge && dataCount > 0 && (
              <span className="min-w-[1.25rem] h-5 px-1 rounded-full text-[10px] font-semibold flex items-center justify-center bg-accent/20 text-accent transition-all duration-200">
                {dataCount > 9 ? "9+" : dataCount}
              </span>
            )}
          </button>
          <button
            onClick={() => onViewChange("sources")}
            className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-150 inline-flex items-center gap-1.5
              ${
                activeView === "sources"
                  ? "bg-dark-surface text-text-primary shadow-sm"
                  : "text-text-muted hover:text-text-secondary"
              }`}
          >
            {t("sources")}
            {showSourcesBadge && sourceCount > 0 && (
              <span className="min-w-[1.25rem] h-5 px-1 rounded-full text-[10px] font-semibold flex items-center justify-center bg-accent/20 text-accent transition-all duration-200">
                {sourceCount > 9 ? "9+" : sourceCount}
              </span>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
