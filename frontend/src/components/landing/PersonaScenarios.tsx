import { motion, useInView } from "motion/react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";

interface Props {
  onAsk: (question: string) => void;
}

const PERSONA_ICONS = [
  (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3H21m-3.75 3H21" />
    </svg>
  ),
  (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 21v-7.5a.75.75 0 01.75-.75h3a.75.75 0 01.75.75V21m-4.5 0H2.36m11.14 0H18m0 0h3.64m-1.39 0V9.349m-16.5 11.65V9.35m0 0a3.001 3.001 0 003.75-.615A2.993 2.993 0 009.75 9.75c.896 0 1.7-.393 2.25-1.016a2.993 2.993 0 002.25 1.016c.896 0 1.7-.393 2.25-1.016a3.001 3.001 0 003.75.614m-16.5 0a3.004 3.004 0 01-.621-4.72L4.318 3.44A1.5 1.5 0 015.378 3h13.243a1.5 1.5 0 011.06.44l1.19 1.189a3 3 0 01-.621 4.72m-13.5 8.65h3.75a.75.75 0 00.75-.75V13.5a.75.75 0 00-.75-.75H6.75a.75.75 0 00-.75.75v3.15c0 .415.336.75.75.75z" />
    </svg>
  ),
  (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 21v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21m0 0h4.5V3.545M12.75 21h7.5V10.75M2.25 21h1.5m18 0h-18M2.25 9l4.5-1.636M18.75 3l-1.5.545m0 6.205l3 1m1.5.5l-1.5-.5M6.75 7.364V3h-3v18m3-13.636l10.5-3.819" />
    </svg>
  ),
];

export function PersonaScenarios({ onAsk }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const { t } = useTranslation("landing");

  const personas = t("personas.items", { returnObjects: true }) as {
    title: string; question: string; domains: string[]; framing: string;
  }[];

  return (
    <section ref={ref} className="py-24 px-6">
      <div className="max-w-6xl mx-auto space-y-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
          className="text-center space-y-4"
        >
          <h2 className="text-2xl md:text-3xl font-semibold text-text-primary tracking-tight">
            {t("personas.heading")}
          </h2>
          <p className="text-sm md:text-base text-text-secondary max-w-lg mx-auto leading-relaxed">
            {t("personas.subheading")}
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {personas.map((p, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 30 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 0.1 + i * 0.1, duration: 0.5, ease: "easeOut" }}
              className="bg-dark-surface/80 backdrop-blur-md border border-white/10 border-l-2 border-l-accent rounded-xl p-6 space-y-5 cursor-pointer hover:border-l-accent-hover hover:bg-dark-surface transition-all group"
              onClick={() => onAsk(p.question)}
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-accent/15 flex items-center justify-center text-accent">
                  {PERSONA_ICONS[i]}
                </div>
                <h3 className="text-base font-semibold text-text-primary">{p.title}</h3>
              </div>

              <div className="bg-dark-bg/60 rounded-lg px-3 py-2.5 text-sm text-white/90 border border-white/5 group-hover:border-accent/20 transition-colors">
                &ldquo;{p.question}&rdquo;
              </div>

              <div>
                <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2">{t("personas.returns")}</div>
                <div className="flex flex-wrap gap-1.5">
                  {p.domains.map((d) => (
                    <span
                      key={d}
                      className="text-[11px] text-text-secondary bg-dark-elevated px-2 py-0.5 rounded-md border border-dark-border"
                    >
                      {d}
                    </span>
                  ))}
                </div>
              </div>

              <p className="text-xs text-text-muted italic">{p.framing}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
