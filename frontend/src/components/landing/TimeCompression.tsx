import { useRef } from "react";
import { motion, useInView } from "motion/react";

const traditionalTrack = [
  { name: "Zoning & Code Research", detail: "14 days", grow: 26, muted: true },
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

const neutralBlock = "bg-dark-elevated border-dark-border text-text-secondary";
const mutedBlock = "bg-dark-surface border-dark-border text-text-muted";
const blockBase = "h-16 rounded-lg border flex flex-col items-center justify-center px-2 text-center overflow-hidden";

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

        <div className="space-y-8">
          <div className="space-y-2.5">
            <div className="flex items-center justify-between text-caption text-text-muted">
              <span className="uppercase tracking-wide">The traditional way</span>
              <span className="hidden sm:inline">~14 days before you can start</span>
            </div>
            <div className="flex gap-2">
              {traditionalTrack.map((phase, index) => (
                <motion.div
                  key={phase.name}
                  style={{ flexGrow: phase.grow, flexBasis: 0, transformOrigin: "left" }}
                  initial={{ opacity: 0, scaleX: 0.35 }}
                  animate={started ? { opacity: 1, scaleX: 1 } : {}}
                  transition={{ delay: 0.2 + index * 0.28, duration: 0.5, ease: "easeOut" }}
                  className={`${blockBase} ${phase.muted ? mutedBlock : neutralBlock}`}
                >
                  <span className="w-full truncate text-micro font-medium leading-tight">{phase.name}</span>
                  {phase.detail && <span className="text-[10px] opacity-75">{phase.detail}</span>}
                </motion.div>
              ))}
            </div>
          </div>

          <div className="space-y-2.5">
            <div className="flex items-center justify-between text-caption">
              <span className="font-semibold uppercase tracking-wide text-accent">With UrbanLayer</span>
              <span className="hidden sm:inline text-text-muted">One instant Scorecard replaces the research phase</span>
            </div>
            <div className="flex gap-2">
              <motion.div
                style={{ flexGrow: scorecardGrow, flexBasis: 0 }}
                initial={{ opacity: 0, scale: 0.7 }}
                animate={started ? { opacity: 1, scale: 1 } : {}}
                transition={{ delay: 1.5, duration: 0.35, ease: "backOut" }}
                className="h-16 min-w-[40px] rounded-lg bg-brand-gradient shadow-glow flex items-center justify-center"
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
                  className={`${blockBase} ${neutralBlock}`}
                >
                  <span className="w-full truncate text-micro font-medium leading-tight">{phase.name}</span>
                </motion.div>
              ))}

              <div style={{ flexGrow: savedGrow, flexBasis: 0 }} className="relative flex items-center justify-center">
                <div className="absolute inset-y-4 left-0 border-l border-dashed border-state-positive/40" />
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={started ? { opacity: 1, scale: 1 } : {}}
                  transition={{ delay: 2.5, duration: 0.4, ease: "easeOut" }}
                  className="flex items-center gap-1.5 whitespace-nowrap rounded-full border border-state-positive/30 bg-state-positive/15 px-3 py-1.5 text-caption font-semibold text-state-positive"
                >
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                  </svg>
                  2 weeks faster
                </motion.div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
