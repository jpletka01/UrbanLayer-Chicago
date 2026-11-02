// PlaceMapStrip — the phone's place map (redesign plan §6g, decision Item 56). A 160 px still strip between the
// answer and the panels, so the first screen shows where the parcel is without a full map pushing the panels
// down. The whole strip is one button; a tap opens the full place map (satellite⇄streets, comps, transit, key)
// in a full-screen dialog. Escape or Close returns focus to the strip.
import { useEffect, useRef, useState, type ComponentProps } from "react";
import { useTranslation } from "react-i18next";
import { Maximize2, X } from "lucide-react";
import { ParcelMap } from "./ParcelMap";

type PlaceProps = Omit<ComponentProps<typeof ParcelMap>, "variant" | "bare" | "className" | "lazy">;

export function PlaceMapStrip(props: PlaceProps) {
  const { t } = useTranslation("pages");
  const [open, setOpen] = useState(false);
  const stripRef = useRef<HTMLButtonElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const strip = stripRef.current;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      strip?.focus();
    };
  }, [open]);

  return (
    <>
      <div className="relative h-40 overflow-hidden rounded-lg" data-testid="place-map-strip">
        {/* One GL context at a time: the strip's map unmounts while the full map is open. */}
        {!open && <ParcelMap {...props} variant="place" bare className="h-full" />}
        <button
          ref={stripRef}
          type="button"
          onClick={() => setOpen(true)}
          aria-label={t("scorecard.map.expand")}
          className="absolute inset-0 flex items-start justify-end p-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded-lg"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-md border border-dark-border bg-dark-surface/90 text-text-secondary backdrop-blur">
            <Maximize2 aria-hidden className="h-4 w-4" strokeWidth={2} />
          </span>
        </button>
      </div>
      {open && (
        <div role="dialog" aria-modal="true" aria-label={t("scorecard.map.placeTitle")} className="fixed inset-0 z-50 flex flex-col bg-dark-bg" data-testid="place-map-full">
          <div className="flex items-center justify-between gap-3 border-b border-dark-border px-4 py-2">
            <h2 className="text-title text-text-primary">{t("scorecard.map.placeTitle")}</h2>
            <button
              ref={closeRef}
              type="button"
              onClick={() => setOpen(false)}
              aria-label={t("scorecard.map.close")}
              className="touch-target flex h-9 w-9 items-center justify-center rounded-lg text-text-secondary hover:text-link focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <X aria-hidden className="h-5 w-5" strokeWidth={2} />
            </button>
          </div>
          <div className="min-h-0 flex-1 p-2" style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}>
            <ParcelMap {...props} variant="place" className="h-full" />
          </div>
        </div>
      )}
    </>
  );
}
