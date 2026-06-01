import { motion, useInView } from "motion/react";
import { useRef } from "react";

const PROPS = [
  {
    title: "Know your neighborhood",
    body: "See what's happening around any Chicago address — crime patterns, open 311 requests, building permits, and zoning, all in one place.",
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
      </svg>
    ),
  },
  {
    title: "Understand what's changing",
    body: "Month-over-month trends show you whether crime is rising, construction is booming, or complaints are being resolved.",
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
      </svg>
    ),
  },
  {
    title: "Get answers, not spreadsheets",
    body: "Ask questions in plain English. Our AI searches 14,000+ municipal code sections and 5 live city datasets to build your answer.",
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
      </svg>
    ),
  },
];

export function ValueProps() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <section ref={ref} className="py-24 px-6">
      <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
        {PROPS.map((p, i) => (
          <motion.div
            key={p.title}
            initial={{ opacity: 0, y: 30 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: i * 0.15, duration: 0.5, ease: "easeOut" }}
            className="bg-dark-surface/80 backdrop-blur-md border border-white/10 rounded-xl p-8 space-y-4"
          >
            <div className="w-12 h-12 rounded-lg bg-accent/15 flex items-center justify-center text-accent">
              {p.icon}
            </div>
            <h3 className="text-lg font-semibold text-text-primary">{p.title}</h3>
            <p className="text-sm text-text-secondary leading-relaxed">{p.body}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
