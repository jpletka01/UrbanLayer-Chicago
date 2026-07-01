import { useRef } from "react";
import { motion, useInView, useReducedMotion } from "motion/react";

// The problem, visualized (not a product screenshot): a mind crowded with fragmented sources
// — the stress of manual site-feasibility research — pivoting to one calm, single source (us).
// Copy is hardcoded while the concept settles; i18n follows once it's locked.

// Source bubbles clogging the "before" mind. Hand-placed for a cluttered, overlapping arc.
const SOURCES: { label: string; top: string; left: string; rot: number; dim?: boolean }[] = [
  { label: "Zoning Map Server", top: "2%", left: "18%", rot: -6 },
  { label: "Cook County Assessor", top: "0%", left: "52%", rot: 4 },
  { label: "FEMA Flood", top: "16%", left: "2%", rot: -3, dim: true },
  { label: "Census / ACS", top: "12%", left: "70%", rot: 7 },
  { label: "TIF Districts", top: "30%", left: "60%", rot: -4 },
  { label: "Municipal Code", top: "26%", left: "12%", rot: 5 },
  { label: "Permits · 311", top: "44%", left: "2%", rot: 3, dim: true },
  { label: "Opportunity Zones", top: "40%", left: "66%", rot: -5, dim: true },
  { label: "ARO / Affordable", top: "6%", left: "36%", rot: 2 },
  { label: "Comparable sales", top: "52%", left: "40%", rot: -2 },
  { label: "PDFs · spreadsheets", top: "34%", left: "34%", rot: 6, dim: true },
];

function HeadGlyph() {
  // Standard person silhouette (head + shoulders as one shape) so it reads unmistakably.
  return (
    <svg viewBox="0 0 24 24" className="w-32 md:w-36 text-text-muted" fill="currentColor" aria-hidden="true">
      <path d="M12 12.5a5 5 0 100-10 5 5 0 000 10zm0 2c-5.33 0-9.5 2.7-9.5 6.2V22h19v-1.3c0-3.5-4.17-6.2-9.5-6.2z" />
    </svg>
  );
}

function ClutteredMind({ animate }: { animate: boolean }) {
  const reduce = useReducedMotion();
  const float = animate && !reduce;
  return (
    <div className="relative h-[340px] md:h-[380px] w-full max-w-md mx-auto">
      {/* stressed head, low + centered (bubbles clog the space above it) */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2">
        <HeadGlyph />
      </div>
      {/* clogging source bubbles */}
      {SOURCES.map((s, i) => (
        <motion.div
          key={s.label}
          className="absolute"
          style={{ top: s.top, left: s.left, rotate: `${s.rot}deg` }}
          animate={float ? { y: [0, -7, 0] } : undefined}
          transition={float ? { duration: 3.2 + (i % 5) * 0.4, repeat: Infinity, ease: "easeInOut", delay: i * 0.18 } : undefined}
        >
          <span
            className={`inline-block whitespace-nowrap rounded-full border px-2.5 py-1 text-micro font-medium backdrop-blur-sm ${
              s.dim
                ? "border-dark-border bg-dark-surface/70 text-text-muted"
                : "border-dark-border-strong bg-dark-elevated text-text-secondary"
            }`}
          >
            {s.label}
          </span>
        </motion.div>
      ))}
      {/* faint stress glow */}
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10"
        style={{ background: "radial-gradient(closest-side, rgb(var(--state-warning) / 0.06), transparent)" }}
      />
    </div>
  );
}

function ClearAnswer() {
  return (
    <div className="relative h-[340px] md:h-[380px] w-full max-w-md mx-auto flex flex-col items-center justify-center gap-5">
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10"
        style={{ background: "radial-gradient(closest-side, rgb(var(--accent) / 0.12), transparent)" }}
      />
      {/* single source mark */}
      <div className="flex items-center gap-2.5 rounded-full border border-accent/30 bg-accent/10 px-4 py-2 shadow-glow">
        <img src="/logo.jpg" alt="" className="w-6 h-6 rounded-full" />
        <span className="font-display text-base font-semibold tracking-tight text-text-primary">UrbanLayer</span>
      </div>
      <svg className="w-5 h-8 text-accent/60" viewBox="0 0 20 32" fill="none" aria-hidden="true">
        <path d="M10 0v26M4 20l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {/* one clean answer card */}
      <div className="w-full max-w-xs rounded-2xl border border-dark-border bg-dark-surface p-4 shadow-card space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-caption text-text-secondary">1601 N Milwaukee Ave</span>
          <span className="inline-flex items-center gap-1 rounded-full bg-state-positive/15 px-2 py-0.5 text-micro font-semibold text-state-positive">
            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            Buildable
          </span>
        </div>
        <div className="flex items-baseline justify-between border-t border-dark-border pt-3">
          <span className="text-caption uppercase tracking-wide text-text-muted">Est. annual tax</span>
          <span className="text-title text-accent">$8,420</span>
        </div>
      </div>
    </div>
  );
}

const METRICS = [
  { before: "~2 weeks", after: "seconds", label: "Time to a verdict" },
  { before: "25+ sources", after: "one", label: "Places to look" },
  { before: "$1,500 consult", after: "free", label: "Cost per site" },
];

export function ProblemPivot() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <section ref={ref} className="py-24 px-6 bg-dark-bg overflow-hidden">
      <div className="max-w-6xl mx-auto space-y-14">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
          className="text-center space-y-4 max-w-2xl mx-auto"
        >
          <h2 className="text-section text-text-primary">The hardest part isn't the deal. It's the diligence.</h2>
          <p className="text-lead text-text-secondary">
            Every Chicago site means chasing zoning, incentives, tax, comps, and code across dozens of
            disconnected portals. We collapse it into one answer.
          </p>
        </motion.div>

        <div className="grid lg:grid-cols-[1fr_auto_1fr] gap-6 lg:gap-4 items-center">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={inView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="space-y-4"
          >
            <ClutteredMind animate={inView} />
            <p className="text-center text-caption text-text-muted max-w-sm mx-auto">
              Scattered across 25+ portals, PDFs, and spreadsheets — reassembled by hand, one site at a time.
            </p>
          </motion.div>

          {/* pivot */}
          <div className="flex lg:flex-col items-center justify-center gap-2 text-text-muted">
            <div className="hidden lg:block h-16 w-px bg-gradient-to-b from-transparent via-dark-border-strong to-transparent" />
            <svg className="w-8 h-8 text-accent rotate-90 lg:rotate-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M20 12H4" />
            </svg>
            <div className="hidden lg:block h-16 w-px bg-gradient-to-b from-transparent via-dark-border-strong to-transparent" />
          </div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={inView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.6, delay: 0.15, ease: "easeOut" }}
            className="space-y-4"
          >
            <ClearAnswer />
            <p className="text-center text-caption text-text-secondary max-w-sm mx-auto">
              One address → one cited Scorecard. Clear, fast, and free.
            </p>
          </motion.div>
        </div>

        {/* transformation metrics */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="grid grid-cols-1 sm:grid-cols-3 gap-4"
        >
          {METRICS.map((m) => (
            <div key={m.label} className="rounded-bento border border-dark-border bg-dark-surface p-5 text-center">
              <div className="flex items-center justify-center gap-2 text-title">
                <span className="text-text-muted line-through decoration-state-negative/60">{m.before}</span>
                <span className="text-text-muted">→</span>
                <span className="text-accent font-semibold">{m.after}</span>
              </div>
              <div className="mt-2 text-caption uppercase tracking-wide text-text-muted">{m.label}</div>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
