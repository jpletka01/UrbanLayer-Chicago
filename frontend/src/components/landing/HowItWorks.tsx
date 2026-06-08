import { motion, useInView } from "motion/react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";

function StepVisual({ index, query, t }: { index: number; query?: string; t: (key: string, opts?: Record<string, unknown>) => string }) {
  if (index === 0) {
    return (
      <div className="bg-dark-bg rounded-lg px-4 py-3 border border-white/10">
        <div className="flex items-center gap-2">
          <div className="flex-1 text-sm text-white/60 truncate">
            {query}
          </div>
          <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center shrink-0">
            <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" />
            </svg>
          </div>
        </div>
      </div>
    );
  }

  if (index === 1) {
    const tags = t("howItWorks.sourceTags", { returnObjects: true }) as unknown as string[];
    return (
      <div className="flex flex-wrap justify-center gap-1.5">
        {tags.map((s, i) => (
          <motion.span
            key={s}
            initial={{ opacity: 0, scale: 0.8 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.4 + i * 0.06, duration: 0.3 }}
            className="text-[11px] font-mono text-accent/80 bg-accent/10 px-2 py-0.5 rounded"
          >
            {s}
          </motion.span>
        ))}
      </div>
    );
  }

  return (
    <div className="bg-dark-bg rounded-lg px-4 py-3 border border-white/10 space-y-2">
      <div className="text-xs text-text-secondary leading-relaxed">
        {t("howItWorks.sampleResponse")}{" "}
        <span className="font-mono text-accent bg-accent/10 px-1 rounded">RM-5</span>
        {t("howItWorks.sampleResponseTail")}
      </div>
      <div className="flex gap-1.5">
        <span className="text-[10px] font-mono bg-dark-elevated text-text-muted px-1.5 py-0.5 rounded">
          § 17-2-0300
        </span>
        <span className="text-[10px] bg-blue-500/15 text-blue-400 px-1.5 py-0.5 rounded">
          data:zoning
        </span>
      </div>
    </div>
  );
}

export function HowItWorks() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const { t } = useTranslation("landing");

  const steps = t("howItWorks.steps", { returnObjects: true }) as {
    title: string; description: string; query?: string;
  }[];

  return (
    <section ref={ref} className="py-24 px-6">
      <div className="max-w-5xl mx-auto space-y-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
          className="text-center space-y-4"
        >
          <h2 className="text-2xl md:text-3xl font-semibold text-text-primary tracking-tight">
            {t("howItWorks.heading")}
          </h2>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-6 relative">
          <div className="hidden md:block absolute top-12 left-[calc(33.333%+0.75rem)] right-[calc(33.333%+0.75rem)] h-px border-t border-dashed border-dark-border" />

          {steps.map((step, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 30 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 0.1 + i * 0.15, duration: 0.5, ease: "easeOut" }}
              className="text-center space-y-5"
            >
              <div className="flex justify-center">
                <div className="w-10 h-10 rounded-full bg-accent/15 border border-accent/30 flex items-center justify-center text-accent font-semibold text-sm relative z-10">
                  {i + 1}
                </div>
              </div>

              <h3 className="text-lg font-semibold text-text-primary">{step.title}</h3>

              <div className="max-w-[280px] mx-auto">
                <StepVisual index={i} query={step.query} t={t} />
              </div>

              <p className="text-sm text-text-secondary leading-relaxed max-w-[280px] mx-auto">
                {step.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
