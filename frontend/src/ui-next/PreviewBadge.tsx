// The "Preview" badge (decision Item 76): visible on every page while the preview is on, today's pages
// included (a route that isn't ready falls back to today's page), with one-click exit. Its own small
// `.ui-next` island, so it is styled the same everywhere without touching the page around it.
import { useTranslation } from "react-i18next";
import { FlaskConical, X } from "lucide-react";
import { useUiVersion } from "./uiVersionContext";

export function PreviewBadge() {
  const { version, setVersion } = useUiVersion();
  const { t } = useTranslation("next");
  if (version !== "next") return null;
  return (
    <div
      className="ui-next fixed bottom-3 left-1/2 -translate-x-1/2 z-[60] flex items-center gap-1 rounded-full bg-nx-ink text-nx-on-ink py-1 pl-3 pr-1 text-caption shadow-lg"
      data-testid="preview-badge"
      role="status"
    >
      <FlaskConical aria-hidden className="h-3.5 w-3.5" strokeWidth={1.5} />
      <span className="font-medium">{t("preview.badge")}</span>
      <button
        type="button"
        onClick={() => setVersion("old")}
        className="ml-1 inline-flex items-center gap-1 rounded-full px-2 py-1 hover:bg-nx-on-ink/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nx-on-ink touch-target"
      >
        <X aria-hidden className="h-3.5 w-3.5" strokeWidth={1.5} />
        {t("preview.exit")}
      </button>
    </div>
  );
}
