// What a map shows in its place when the browser can't draw it (no WebGL; see useMapboxOverlay). The rest of the
// page keeps working, so the note says so.
import { MapPinOff } from "lucide-react";
import { useTranslation } from "react-i18next";

export function MapUnavailable() {
  const { t } = useTranslation("map");
  return (
    <div className="absolute inset-0 z-10 flex items-center justify-center p-5" role="status" data-testid="map-unavailable">
      <p className="flex max-w-sm items-start gap-2 rounded-lg border border-dark-border bg-dark-surface/95 px-4 py-3 text-body text-text-secondary shadow-card">
        <MapPinOff className="mt-0.5 h-4 w-4 flex-shrink-0 text-text-muted" aria-hidden="true" />
        <span>{t("unavailableNoWebgl")}</span>
      </p>
    </div>
  );
}
