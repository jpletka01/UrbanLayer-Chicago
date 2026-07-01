import { useRef } from "react";
import { motion, useInView, useReducedMotion } from "motion/react";

const flowDots = [0, 1, 2, 3, 4];

function BureaucraticStack() {
  return (
    <div className="group relative mx-auto h-[320px] w-full max-w-sm">
      <div className="absolute left-2 top-2 w-[86%] -rotate-3 rounded-xl border border-dark-border bg-dark-elevated/60 p-4 backdrop-blur-sm blur-[0.4px] opacity-80 transition-all duration-500 group-hover:-translate-y-1 group-hover:-rotate-6">
        <div className="text-micro font-mono text-text-muted leading-relaxed">
          COOK COUNTY ASSESSOR<br />
          PIN 14-33-423-048-0000<br />
          Class 2-11 · Land $38,240<br />
          2024 AV 34,100 · 2023 31,890 · 2022 30,110
        </div>
      </div>

      <div className="absolute left-6 top-16 w-[88%] rotate-2 rounded-xl border border-dark-border bg-dark-elevated/70 p-4 backdrop-blur-sm opacity-90 transition-all duration-500 group-hover:translate-y-1 group-hover:rotate-3">
        <div className="text-micro font-mono text-text-muted leading-relaxed">
          DISTRICT&nbsp;&nbsp;FAR&nbsp;&nbsp;HEIGHT&nbsp;&nbsp;MIN&nbsp;LOT<br />
          RS-3&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0.9&nbsp;&nbsp;30 ft&nbsp;&nbsp;&nbsp;2,500<br />
          B3-2&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;1.2&nbsp;&nbsp;38 ft&nbsp;&nbsp;&nbsp;—<br />
          C1-2&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;1.2&nbsp;&nbsp;47 ft&nbsp;&nbsp;&nbsp;—
        </div>
      </div>

      <div className="absolute left-3 top-32 w-[92%] -rotate-1 rounded-xl border border-dark-border bg-dark-elevated/80 p-4 backdrop-blur-sm transition-all duration-500 group-hover:translate-x-1">
        <div className="text-caption font-mono text-text-muted leading-relaxed">
          <span className="text-text-secondary">§ 17-2-0300</span> Bulk and Density Standards.
          Maximum floor area ratio shall not exceed 1.2 in the B3 district. Setbacks: front 0 ft,
          rear 30 ft; transitional yards apply where a lot abuts an R district…
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
  return (
    <div className="relative mx-auto w-full max-w-sm rounded-bento border border-dark-border bg-dark-surface p-6 shadow-glow">
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-state-positive/15 px-3 py-1 text-title font-semibold text-state-positive">
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          Buildable
        </span>
        <span className="rounded-md bg-accent-muted px-2 py-1 font-mono text-micro font-semibold text-accent">Zoning: B3-2</span>
      </div>
      <div className="mt-5 space-y-1.5">
        <div className="text-subtitle text-text-primary">1601 N Milwaukee Ave</div>
        <div className="text-body text-text-secondary">Every rule verified. 0 active overlays.</div>
      </div>
      <div className="mt-5 border-t border-dark-border pt-4 text-caption text-accent font-semibold">
        View the full Scorecard →
      </div>
    </div>
  );
}

export function ChaosToVerdict() {
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
          <h2 className="text-section text-text-primary">Every rule in Chicago, resolved to one verdict.</h2>
          <p className="text-lead text-text-secondary">
            Zoning code, overlays, incentives, and assessments — read, cross-checked, and answered in seconds.
          </p>
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
