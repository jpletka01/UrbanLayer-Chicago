import { motion, useInView } from "motion/react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";

function PropertyCard({ t }: { t: (key: string) => string }) {
  return (
    <div className="space-y-3 text-xs">
      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        <div>
          <div className="text-text-muted uppercase tracking-wider text-[10px]">{t("depth.pin")}</div>
          <div className="font-mono text-text-primary">14-33-423-048-0000</div>
        </div>
        <div>
          <div className="text-text-muted uppercase tracking-wider text-[10px]">{t("depth.class")}</div>
          <div className="text-text-primary">2-11 Two-Story Residence</div>
        </div>
        <div>
          <div className="text-text-muted uppercase tracking-wider text-[10px]">{t("depth.building")}</div>
          <div className="text-text-primary">2,450 sq ft &middot; 2 stories</div>
        </div>
        <div>
          <div className="text-text-muted uppercase tracking-wider text-[10px]">{t("depth.lot")}</div>
          <div className="text-text-primary">3,125 sq ft</div>
        </div>
      </div>
      <div className="border-t border-dark-border pt-2 space-y-1.5">
        <div className="text-text-muted uppercase tracking-wider text-[10px]">{t("depth.assessmentHistory")}</div>
        <div className="space-y-1">
          {[
            { year: "2025", value: "$38,240" },
            { year: "2024", value: "$34,100" },
            { year: "2023", value: "$31,890" },
          ].map((r) => (
            <div key={r.year} className="flex justify-between text-text-secondary">
              <span className="font-mono">{r.year}</span>
              <span className="text-text-primary">{r.value}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="border-t border-dark-border pt-2 flex justify-between items-center">
        <span className="text-text-muted uppercase tracking-wider text-[10px]">{t("depth.estAnnualTax")}</span>
        <span className="text-accent font-semibold text-sm">$8,420</span>
      </div>
    </div>
  );
}

function RegulatoryCard({ t }: { t: (key: string) => string }) {
  return (
    <div className="space-y-3 text-xs">
      <div>
        <div className="text-text-muted uppercase tracking-wider text-[10px] mb-2">{t("depth.zoning")}</div>
        <div className="inline-flex items-center gap-1.5 bg-amber-500/15 text-amber-400 px-2.5 py-1 rounded-md font-mono text-sm font-medium">
          B3-2
        </div>
        <span className="text-text-secondary ml-2">Community Shopping District</span>
      </div>
      <div className="border-t border-dark-border pt-2">
        <div className="text-text-muted uppercase tracking-wider text-[10px] mb-2">{t("depth.activeOverlays")}</div>
        <div className="flex flex-wrap gap-1.5">
          {[
            { label: t("depth.plannedDevelopment"), color: "bg-blue-500/15 text-blue-400" },
            { label: t("depth.pedestrianStreet"), color: "bg-purple-500/15 text-purple-400" },
            { label: t("depth.todEligible"), color: "bg-emerald-500/15 text-emerald-400" },
            { label: "SSA #26", color: "bg-cyan-500/15 text-cyan-400" },
          ].map((o) => (
            <span key={o.label} className={`${o.color} px-2 py-0.5 rounded text-[11px] font-medium`}>
              {o.label}
            </span>
          ))}
        </div>
      </div>
      <div className="border-t border-dark-border pt-2">
        <div className="text-text-muted uppercase tracking-wider text-[10px] mb-2">{t("depth.riskFactors")}</div>
        <div className="flex items-center gap-2">
          <span className="bg-emerald-500/15 text-emerald-400 px-2 py-0.5 rounded text-[11px] font-medium">
            {t("depth.noFloodZone")}
          </span>
          <span className="bg-emerald-500/15 text-emerald-400 px-2 py-0.5 rounded text-[11px] font-medium">
            {t("depth.noBrownfield")}
          </span>
        </div>
      </div>
    </div>
  );
}

function NeighborhoodCard({ t }: { t: (key: string) => string }) {
  return (
    <div className="space-y-3 text-xs">
      <div>
        <div className="text-text-muted uppercase tracking-wider text-[10px] mb-2">{t("depth.walkability")}</div>
        <div className="space-y-1.5">
          {[
            { label: t("depth.walkScore"), value: 92, color: "bg-emerald-500" },
            { label: t("depth.transitScore"), value: 87, color: "bg-blue-500" },
            { label: t("depth.bikeScore"), value: 82, color: "bg-cyan-500" },
          ].map((s) => (
            <div key={s.label} className="flex items-center gap-3">
              <span className="text-text-secondary w-20 shrink-0">{s.label}</span>
              <div className="flex-1 h-1.5 bg-dark-border rounded-full overflow-hidden">
                <div className={`h-full ${s.color} rounded-full`} style={{ width: `${s.value}%` }} />
              </div>
              <span className="text-text-primary font-mono w-6 text-right">{s.value}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="border-t border-dark-border pt-2">
        <div className="text-text-muted uppercase tracking-wider text-[10px] mb-2">{t("depth.nearestTransit")}</div>
        <div className="flex items-center gap-2 text-text-secondary">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-500 shrink-0" />
          <span>Western</span>
          <span className="text-text-muted">&mdash; {t("depth.blueLine")}</span>
        </div>
      </div>
      <div className="border-t border-dark-border pt-2">
        <div className="text-text-muted uppercase tracking-wider text-[10px] mb-2">{t("depth.demographics")}</div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
          <div className="flex justify-between">
            <span className="text-text-muted">{t("depth.population")}</span>
            <span className="text-text-primary font-mono">64,116</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">{t("depth.medIncome")}</span>
            <span className="text-text-primary font-mono">$71,400</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">{t("depth.ownerOcc")}</span>
            <span className="text-text-primary font-mono">42%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">{t("depth.medAge")}</span>
            <span className="text-text-primary font-mono">33.4</span>
          </div>
        </div>
      </div>
    </div>
  );
}

const CARD_CONTENT = [PropertyCard, RegulatoryCard, NeighborhoodCard];

export function DepthShowcase() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const { t } = useTranslation("landing");

  const cards = t("depth.cards", { returnObjects: true }) as { title: string; caption: string }[];

  return (
    <section ref={ref} className="py-24 px-6 bg-dark-bg">
      <div className="max-w-6xl mx-auto space-y-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
          className="text-center space-y-4"
        >
          <h2 className="text-2xl md:text-3xl font-semibold text-text-primary tracking-tight">
            {t("depth.heading")}
          </h2>
          <p className="text-sm md:text-base text-text-secondary max-w-lg mx-auto leading-relaxed">
            {t("depth.subheading")}
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {cards.map((card, i) => {
            const ContentComponent = CARD_CONTENT[i];
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 30, scale: 0.97 }}
                animate={inView ? { opacity: 1, y: 0, scale: 1 } : {}}
                transition={{ delay: 0.15 + i * 0.12, duration: 0.5, ease: "easeOut" }}
                className="bg-dark-elevated border border-dark-border rounded-xl overflow-hidden"
              >
                <div className="px-5 pt-5 pb-3">
                  <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">{card.title}</h3>
                </div>
                <div className="px-5 pb-4">
                  <ContentComponent t={t} />
                </div>
                <div className="px-5 py-3 bg-dark-surface/50 border-t border-dark-border">
                  <p className="text-xs text-text-muted leading-relaxed">{card.caption}</p>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
