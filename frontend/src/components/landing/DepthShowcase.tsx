import { motion, useInView } from "motion/react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { Card } from "../ui/Card";
import { Chip } from "../ui/Chip";

function PropertyCard({ t }: { t: (key: string) => string }) {
  return (
    <div className="space-y-3 text-caption">
      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        <div>
          <div className="text-text-muted text-overline uppercase">{t("depth.pin")}</div>
          <div className="font-mono text-text-primary">14-33-423-048-0000</div>
        </div>
        <div>
          <div className="text-text-muted text-overline uppercase">{t("depth.class")}</div>
          <div className="text-text-primary">{t("depth.sampleClass")}</div>
        </div>
        <div>
          <div className="text-text-muted text-overline uppercase">{t("depth.building")}</div>
          <div className="text-text-primary">{t("depth.sampleBuilding")}</div>
        </div>
        <div>
          <div className="text-text-muted text-overline uppercase">{t("depth.lot")}</div>
          <div className="text-text-primary">{t("depth.sampleLot")}</div>
        </div>
      </div>
      <div className="border-t border-dark-border pt-2 space-y-1.5">
        <div className="text-text-muted text-overline uppercase">{t("depth.assessmentHistory")}</div>
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
        <span className="text-text-muted text-overline uppercase">{t("depth.estAnnualTax")}</span>
        <span className="text-accent text-title">$8,420</span>
      </div>
    </div>
  );
}

function RegulatoryCard({ t }: { t: (key: string) => string }) {
  return (
    <div className="space-y-3 text-caption">
      <div>
        <div className="text-text-muted text-overline uppercase mb-2">{t("depth.zoning")}</div>
        <Chip tone="accent" mono size="md">B3-2</Chip>
        <span className="text-text-secondary ml-2">{t("depth.sampleZoneDesc")}</span>
      </div>
      <div className="border-t border-dark-border pt-2">
        <div className="text-text-muted text-overline uppercase mb-2">{t("depth.activeOverlays")}</div>
        <div className="flex flex-wrap gap-1.5">
          {/* §6: overlay names are categorical facts, not state → neutral (Rule A). */}
          {[t("depth.plannedDevelopment"), t("depth.pedestrianStreet"), t("depth.todEligible"), "SSA #26"].map((label) => (
            <Chip key={label} tone="neutral" size="sm">{label}</Chip>
          ))}
        </div>
      </div>
      <div className="border-t border-dark-border pt-2">
        <div className="text-text-muted text-overline uppercase mb-2">{t("depth.riskFactors")}</div>
        <div className="flex items-center gap-2">
          {/* favorable risk = genuine positive state → emerald is allowed (§6). */}
          <Chip tone="positive" size="sm">{t("depth.noFloodZone")}</Chip>
          <Chip tone="positive" size="sm">{t("depth.noBrownfield")}</Chip>
        </div>
      </div>
    </div>
  );
}

function NeighborhoodCard({ t }: { t: (key: string) => string }) {
  return (
    <div className="space-y-3 text-caption">
      <div>
        <div className="text-text-muted text-overline uppercase mb-2">{t("depth.walkability")}</div>
        <div className="space-y-1.5">
          {/* §6: a score isn't good/bad state → single accent fill, not a per-bar hue. */}
          {[
            { label: t("depth.walkScore"), value: 92 },
            { label: t("depth.transitScore"), value: 87 },
            { label: t("depth.bikeScore"), value: 82 },
          ].map((s) => (
            <div key={s.label} className="flex items-center gap-3">
              <span className="text-text-secondary w-20 shrink-0">{s.label}</span>
              <div className="flex-1 h-1.5 bg-dark-border rounded-full overflow-hidden">
                <div className="h-full bg-accent rounded-full" style={{ width: `${s.value}%` }} />
              </div>
              <span className="text-text-primary font-mono w-6 text-right">{s.value}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="border-t border-dark-border pt-2">
        <div className="text-text-muted text-overline uppercase mb-2">{t("depth.nearestTransit")}</div>
        <div className="flex items-center gap-2 text-text-secondary">
          <span className="w-2.5 h-2.5 rounded-full bg-accent shrink-0" />
          <span>Western</span>
          <span className="text-text-muted">&mdash; {t("depth.blueLine")}</span>
        </div>
      </div>
      <div className="border-t border-dark-border pt-2">
        <div className="text-text-muted text-overline uppercase mb-2">{t("depth.demographics")}</div>
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
          <h2 className="text-section text-text-primary">
            {t("depth.heading")}
          </h2>
          <p className="text-lead text-text-secondary max-w-lg mx-auto">
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
                className="h-full"
              >
                <Card title={card.title} footer={card.caption} className="h-full">
                  <ContentComponent t={t} />
                </Card>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
