import { useRef } from "react";
import { motion, useInView } from "motion/react";
import { useTranslation } from "react-i18next";
import { Chip } from "../ui/Chip";
import { staticMapUrl, CHI_PARCEL } from "../../lib/staticMap";

// The single "show, don't tell" artifact (replaces the two capability card-grids). A realistic
// product screenshot: a real Chicago basemap with the parcel pinned, beside the full Scorecard
// it produces — verdict, zoning, incentives, tax, comps, overlays. Data is illustrative.
const ROWS: { key: string; value: string; accent?: boolean; mono?: boolean }[] = [
  { key: "showcase.zoning", value: "B3-2 · Community Shopping", mono: true },
  { key: "showcase.incentives", value: "TOD · Opportunity Zone" },
  { key: "showcase.tax", value: "$8,420", accent: true },
  { key: "showcase.comps", value: "$412 / ft² · 6 nearby" },
  { key: "showcase.overlays", value: "Pedestrian St · PD 1211" },
];

const MAP_LAYERS = ["Zoning", "Overlays", "Transit"];

export function ProductShowcase() {
  const { t } = useTranslation("landing");
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const map = staticMapUrl({ ...CHI_PARCEL, zoom: 15, width: 720, height: 820, pin: true });

  return (
    <section ref={ref} className="py-24 px-6 bg-dark-bg">
      <div className="max-w-6xl mx-auto space-y-10">
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
          className="text-section text-text-primary text-center"
        >
          {t("showcase.heading")}
        </motion.h2>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="grid lg:grid-cols-[1.05fr_1fr] rounded-bento border border-dark-border overflow-hidden shadow-card bg-dark-surface"
        >
          {/* Map half — real Chicago basemap, parcel pinned, layer chips */}
          <div className="relative min-h-[320px] lg:min-h-[520px] bg-dark-elevated">
            {map && <img src={map} alt="" className="absolute inset-0 w-full h-full object-cover" />}
            <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-black/20" />
            <div className="absolute top-4 left-4 flex flex-wrap gap-2">
              {MAP_LAYERS.map((l) => (
                <span
                  key={l}
                  className="rounded-full border border-white/15 bg-black/50 backdrop-blur px-2.5 py-1 text-micro font-medium text-white/90"
                >
                  {l}
                </span>
              ))}
            </div>
            <div className="absolute bottom-4 left-4 flex items-center gap-2 rounded-lg bg-black/60 backdrop-blur px-3 py-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-accent" />
              <span className="text-caption text-white">1601 N Milwaukee Ave</span>
            </div>
          </div>

          {/* Scorecard half — the full picture as one panel */}
          <div className="p-6 md:p-8 flex flex-col justify-center space-y-5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 text-overline uppercase text-accent">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                  Property Scorecard
                </div>
                <div className="text-subtitle text-text-primary mt-1.5">1601 N Milwaukee Ave</div>
                <div className="font-mono text-caption text-text-muted">14-33-423-048-0000</div>
              </div>
              <Chip tone="positive" size="md" className="shrink-0">{t("heroPreview.verdict")}</Chip>
            </div>

            <div className="border-y border-dark-border divide-y divide-dark-border">
              {ROWS.map((r) => (
                <div key={r.key} className="flex items-center justify-between gap-4 py-3">
                  <span className="text-caption uppercase tracking-wide text-text-muted shrink-0">{t(r.key)}</span>
                  <span
                    className={`text-body text-right ${
                      r.accent ? "text-accent font-semibold" : r.mono ? "font-mono text-text-primary" : "text-text-primary"
                    }`}
                  >
                    {r.value}
                  </span>
                </div>
              ))}
            </div>

            <div className="text-caption text-accent font-semibold">{t("heroPreview.cta")} →</div>
          </div>
        </motion.div>

        <p className="text-center text-caption text-text-muted max-w-xl mx-auto">{t("showcase.caption")}</p>
      </div>
    </section>
  );
}
