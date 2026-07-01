import { useRef } from "react";
import { motion, useInView } from "motion/react";

const traditionalTrack = [
  { name: "Zoning & Code Research", detail: "14 days", grow: 26 },
  { name: "Architect Feasibility", detail: "", grow: 22 },
  { name: "Permitting & Approvals", detail: "", grow: 26 },
  { name: "Construction", detail: "", grow: 26 },
];

const acceleratedTrack = [
  { name: "Architect Feasibility", grow: 22 },
  { name: "Permitting & Approvals", grow: 26 },
  { name: "Construction", grow: 26 },
];

const scorecardGrow = 4;
const savedGrow = 22;

const barShell = "relative flex h-16 rounded-xl border border-dark-border divide-x-2 divide-dark-bg";
const segmentBase = "flex flex-col items-center justify-center px-2 text-center overflow-hidden";
const traditionalSegment = "bg-dark-elevated text-text-muted";
const acceleratedSegment = "bg-dark-hover text-text-primary";
const hatchPattern =
  "repeating-linear-gradient(-45deg, rgb(var(--state-positive) / 0.16) 0, rgb(var(--state-positive) / 0.16) 1px, transparent 1px, transparent 8px)";

function SavedBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-state-positive/30 bg-state-positive/15 px-3 py-1.5 text-caption font-semibold text-state-positive">
      <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
      </svg>
      2 weeks faster
    </span>
  );
}

export function TimeCompression() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const started = useInView(sectionRef, { once: true, margin: "-120px" });

  return (
    <section ref={sectionRef} className="bg-dark-bg px-6 py-24 overflow-hidden">
      <div className="mx-auto max-w-6xl space-y-14">
        <div className="mx-auto max-w-2xl space-y-4 text-center">
          <h2 className="text-section text-text-primary">Cut the research, and the whole project moves up.</h2>
          <p className="text-lead text-text-secondary">
            The two weeks you save on diligence don't just disappear — they pull your entire development
            timeline forward.
          </p>
        </div>

        <div className="relative">
          <div className="mb-2 text-caption font-medium uppercase tracking-wide text-text-muted">The traditional way</div>
          <div className={`${barShell} mb-9`}>
            {traditionalTrack.map((phase, index) => (
              <motion.div
                key={phase.name}
                style={{ flexGrow: phase.grow, flexBasis: 0, transformOrigin: "left" }}
                initial={{ opacity: 0, scaleX: 0.35 }}
                animate={started ? { opacity: 1, scaleX: 1 } : {}}
                transition={{ delay: 0.2 + index * 0.26, duration: 0.5, ease: "easeOut" }}
                className={`${segmentBase} ${traditionalSegment} ${index === 0 ? "rounded-l-xl" : ""} ${
                  index === traditionalTrack.length - 1 ? "rounded-r-xl" : ""
                }`}
              >
                <span className="w-full truncate text-micro font-medium leading-tight">{phase.name}</span>
                {phase.detail && <span className="text-[10px] opacity-75">{phase.detail}</span>}
              </motion.div>
            ))}
          </div>

          <div className="mb-2 text-caption font-semibold uppercase tracking-wide text-accent">With UrbanLayer</div>
          <div className={barShell}>
            <motion.div
              style={{ flexGrow: scorecardGrow, flexBasis: 0 }}
              initial={{ opacity: 0, scale: 0.7 }}
              animate={started ? { opacity: 1, scale: 1 } : {}}
              transition={{ delay: 1.5, duration: 0.35, ease: "backOut" }}
              className="flex h-full min-w-[42px] items-center justify-center rounded-l-xl bg-brand-gradient shadow-glow"
            >
              <span className="text-[10px] font-bold text-[#1a120d]">2s</span>
            </motion.div>

            {acceleratedTrack.map((phase, index) => (
              <motion.div
                key={phase.name}
                style={{ flexGrow: phase.grow, flexBasis: 0 }}
                initial={{ opacity: 0, x: 70 }}
                animate={started ? { opacity: 1, x: 0 } : {}}
                transition={{ delay: 1.7 + index * 0.22, duration: 0.5, ease: "easeOut" }}
                className={`${segmentBase} ${acceleratedSegment}`}
              >
                <span className="w-full truncate text-micro font-medium leading-tight">{phase.name}</span>
              </motion.div>
            ))}

            <div
              style={{ flexGrow: savedGrow, flexBasis: 0, backgroundImage: hatchPattern }}
              className="relative flex items-center justify-center rounded-r-xl bg-state-positive/[0.04]"
            >
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={started ? { opacity: 1, scale: 1 } : {}}
                transition={{ delay: 2.5, duration: 0.4, ease: "easeOut" }}
                className="hidden sm:block"
              >
                <SavedBadge />
              </motion.div>
            </div>
          </div>

          <motion.div
            initial={{ opacity: 0, scaleY: 0 }}
            animate={started ? { opacity: 1, scaleY: 1 } : {}}
            transition={{ delay: 1.3, duration: 0.4, ease: "easeOut" }}
            style={{ originY: 0 }}
            className="pointer-events-none absolute right-0 top-7 bottom-0 border-l-2 border-dashed border-text-muted/50"
          />
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={started ? { opacity: 1 } : {}}
          transition={{ delay: 2.5, duration: 0.4 }}
          className="flex justify-center sm:hidden"
        >
          <SavedBadge />
        </motion.div>
      </div>
    </section>
  );
}
