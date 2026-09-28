import { useRef } from "react";
import { motion, useInView, useReducedMotion } from "motion/react";
import { useTranslation } from "react-i18next";

// Every fact on this page is the real record for 1601 N Milwaukee Ave (the homepage's
// demo address) and the real Title 17 text, as of 2026-09-28. The section used to show
// invented numbers (a fake PIN, FAR 1.2 for B3-2) that contradicted the live profile.

const flowDots = [0, 1, 2, 3, 4];

function BureaucraticStack() {
  return (
    <div className="group relative mx-auto h-[320px] w-full max-w-sm">
      <div className="absolute left-2 top-2 w-[86%] -rotate-3 rounded-xl border border-dark-border bg-dark-elevated/60 p-4 backdrop-blur-sm blur-[0.4px] opacity-80 transition-all duration-500 group-hover:-translate-y-1 group-hover:-rotate-6">
        <div className="text-micro font-mono text-text-muted leading-relaxed">
          COOK COUNTY ASSESSOR<br />
          PIN 14-31-332-018-0000<br />
          Class 5-92 · Land AV 147,838<br />
          2024 AV 398,120 · 2023 870,128 · 2022 870,128
        </div>
      </div>

      <div className="absolute left-6 top-16 w-[88%] rotate-2 rounded-xl border border-dark-border bg-dark-elevated/70 p-4 backdrop-blur-sm opacity-90 transition-all duration-500 group-hover:translate-y-1 group-hover:rotate-3">
        <div className="text-micro font-mono text-text-muted leading-relaxed">
          DISTRICT&nbsp;&nbsp;FAR&nbsp;&nbsp;HEIGHT&nbsp;&nbsp;MIN&nbsp;LOT<br />
          RS-3&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0.9&nbsp;&nbsp;30 ft&nbsp;&nbsp;&nbsp;2,500<br />
          B3-2&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.2&nbsp;&nbsp;45–50 ft&nbsp;—<br />
          C1-2&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.2&nbsp;&nbsp;45–50 ft&nbsp;—
        </div>
      </div>

      <div className="absolute left-3 top-32 w-[92%] -rotate-1 rounded-xl border border-dark-border bg-dark-elevated/80 p-4 backdrop-blur-sm transition-all duration-500 group-hover:translate-x-1">
        <div className="text-caption font-mono text-text-muted leading-relaxed">
          <span className="text-text-secondary">§ 17-3-0403</span> Floor Area Ratio. All development in
          B and C districts is subject to the following maximum floor area ratio standards: Dash 2 … 2.2.{" "}
          <span className="text-text-secondary">§ 17-3-0404</span> No front setback is required in B or
          C districts, except on B- or C-zoned lots abutting R-zoned lots…
        </div>
      </div>
    </div>
  );
}

function Connector({ orientation }: { orientation: "horizontal" | "vertical" }) {
  const reduce = useReducedMotion();
  const horizontal = orientation === "horizontal";
  const lineClass = horizontal
    ? "h-px w-24 lg:w-32 bg-gradient-to-r from-transparent via-accent to-transparent"
    : "w-px h-16 bg-gradient-to-b from-transparent via-accent to-transparent";

  return (
    <div className={`relative flex items-center justify-center ${horizontal ? "" : "py-2"}`}>
      <div className={lineClass} />
      {!reduce &&
        flowDots.map((i) => (
          <motion.span
            key={i}
            className="absolute h-1.5 w-1.5 rounded-full bg-accent shadow-glow"
            initial={horizontal ? { left: 0, opacity: 0 } : { top: 0, opacity: 0 }}
            animate={
              horizontal
                ? { left: ["0%", "100%"], opacity: [0, 1, 0] }
                : { top: ["0%", "100%"], opacity: [0, 1, 0] }
            }
            transition={{ duration: 1.8, repeat: Infinity, delay: i * 0.36, ease: "linear" }}
          />
        ))}
    </div>
  );
}

function Verdict() {
  const { t } = useTranslation("landing");
  return (
    <div className="relative mx-auto w-full max-w-sm rounded-bento border border-dark-border bg-dark-surface p-6 shadow-glow">
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-state-warning/15 px-3 py-1 text-title font-semibold text-state-warning">
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0 3.75h.008v.008H12v-.008z" />
          </svg>
          {t("heroPreview.verdict")}
        </span>
        <span className="rounded-md bg-accent-muted px-2 py-1 font-mono text-micro font-semibold text-accent">Zoning: B3-2</span>
      </div>
      <div className="mt-5 space-y-1.5">
        <div className="text-subtitle text-text-primary">1601 N Milwaukee Ave</div>
        <div className="text-body text-text-secondary">{t("chaos.verified")}</div>
      </div>
      <div className="mt-5 border-t border-dark-border pt-4 text-caption text-accent font-semibold">
        {t("heroPreview.cta")} →
      </div>
    </div>
  );
}

export function ChaosToVerdict() {
  const { t } = useTranslation("landing");
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <section ref={ref} className="bg-dark-bg px-6 py-24 overflow-hidden">
      <div className="mx-auto max-w-6xl space-y-14">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
          className="mx-auto max-w-2xl space-y-4 text-center"
        >
          <h2 className="text-section text-text-primary">{t("chaos.heading")}</h2>
          <p className="text-lead text-text-secondary">{t("chaos.subheading")}</p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="grid items-center gap-8 lg:grid-cols-[1fr_auto_1fr] lg:gap-4"
        >
          <BureaucraticStack />
          <div className="hidden lg:block">
            <Connector orientation="horizontal" />
          </div>
          <div className="flex justify-center lg:hidden">
            <Connector orientation="vertical" />
          </div>
          <Verdict />
        </motion.div>
      </div>
    </section>
  );
}
