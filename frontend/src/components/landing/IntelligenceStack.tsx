import { motion, useInView } from "motion/react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { Card } from "../ui/Card";
import { Chip } from "../ui/Chip";

const DOMAIN_ICONS = [
  (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
    </svg>
  ),
  (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
    </svg>
  ),
  (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3H21m-3.75 3H21" />
    </svg>
  ),
  (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
    </svg>
  ),
  (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
    </svg>
  ),
];

// Fills the wide feature tile's right column with an on-theme visual accent (a mini zoning
// legend) instead of dead space. Orange tints, not a rainbow — stays on-palette.
const ZONE_SAMPLE = [
  { z: "B3-2", a: "0.9" },
  { z: "RS-3", a: "0.68" },
  { z: "C1-2", a: "0.52" },
  { z: "RT-4", a: "0.4" },
  { z: "DX-7", a: "0.3" },
  { z: "PD 1211", a: "0.22" },
];

function ZoningLegend() {
  return (
    <div className="hidden sm:block rounded-xl border border-dark-border bg-dark-bg/40 p-4">
      <div className="text-overline uppercase text-text-muted mb-3">Sample zoning classes</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2.5">
        {ZONE_SAMPLE.map(({ z, a }) => (
          <div key={z} className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: `rgb(var(--accent) / ${a})` }} />
            <span className="font-mono text-caption text-text-secondary">{z}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function IntelligenceStack() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const { t } = useTranslation("landing");

  const domains = t("intelligence.domains", { returnObjects: true }) as { title: string; badge: string; points: string[] }[];

  // Asymmetric bento spans on a 12-col grid — rows of 7/5, 5/7, 6/6 so no two rows repeat
  // the same rhythm (breaks the uniform-grid monotony). Index 0 is the feature tile.
  const SPANS = [
    "lg:col-span-7",
    "lg:col-span-5",
    "lg:col-span-5",
    "lg:col-span-7",
    "lg:col-span-6",
    "lg:col-span-6",
  ];

  return (
    <section ref={ref} className="relative py-24 px-6 overflow-hidden bg-dark-bg">
      <div className="relative z-10 max-w-6xl mx-auto space-y-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
          className="text-center space-y-4"
        >
          <h2 className="text-section text-text-primary">
            {t("intelligence.heading")}
          </h2>
          <p className="text-lead text-text-secondary max-w-2xl mx-auto">
            {t("intelligence.subheading")}
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 md:gap-5">
          {domains.map((d, i) => {
            const feature = i === 0;
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 30 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ delay: 0.1 + i * 0.08, duration: 0.5, ease: "easeOut" }}
                className={SPANS[i]}
              >
                <Card
                  surface={feature ? "elevated" : "surface"}
                  padding="lg"
                  className={`h-full ${feature ? "ring-1 ring-accent/25 shadow-glow" : ""}`}
                >
                  <div className={feature ? "space-y-6" : "space-y-4"}>
                    <div className="flex items-center justify-between">
                      <div
                        className={`rounded-xl bg-accent/15 flex items-center justify-center text-accent ${
                          feature ? "w-14 h-14" : "w-10 h-10"
                        }`}
                      >
                        {DOMAIN_ICONS[i]}
                      </div>
                      <Chip tone="accent" mono size="md" className="font-semibold">{d.badge}</Chip>
                    </div>
                    {feature ? (
                      // Two-column body so the wide tile fills: bullets left, zoning legend right.
                      <div className="grid sm:grid-cols-2 gap-6 items-center">
                        <div className="space-y-4">
                          <h3 className="text-section text-text-primary">{d.title}</h3>
                          <ul className="space-y-2">
                            {d.points.map((p) => (
                              <li key={p} className="text-body text-text-secondary flex items-start gap-2">
                                <span className="mt-1.5 shrink-0 w-1 h-1 rounded-full bg-accent/60" />
                                {p}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <ZoningLegend />
                      </div>
                    ) : (
                      <>
                        <h3 className="text-subtitle text-text-primary">{d.title}</h3>
                        <ul className="space-y-1.5">
                          {d.points.map((p) => (
                            <li key={p} className="text-body text-text-secondary flex items-start gap-2">
                              <span className="mt-1.5 shrink-0 w-1 h-1 rounded-full bg-accent/60" />
                              {p}
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                </Card>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
