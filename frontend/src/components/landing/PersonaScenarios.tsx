import { motion, useInView } from "motion/react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { buildScorecardHref } from "../sidebar/ScorecardBridgeCard";
import { track } from "../../lib/tracking";
import { Card } from "../ui/Card";
import { Chip } from "../ui/Chip";

const PERSONA_ICONS = [
  (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3H21m-3.75 3H21" />
    </svg>
  ),
  (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
    </svg>
  ),
  (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v17.25m0 0c-1.472 0-2.882.265-4.185.75M12 20.25c1.472 0 2.882.265 4.185.75M18.75 4.97A48.416 48.416 0 0012 4.5c-2.291 0-4.545.16-6.75.47m13.5 0c1.01.143 2.01.317 3 .52m-3-.52l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.988 5.988 0 01-2.031.352 5.988 5.988 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L18.75 4.97zm-16.5.547c.99-.203 1.99-.377 3-.52m0 0l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.989 5.989 0 01-2.031.352 5.989 5.989 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L5.25 5.517z" />
    </svg>
  ),
];

export function PersonaScenarios() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const { t } = useTranslation("landing");
  const navigate = useNavigate();

  const personas = t("personas.items", { returnObjects: true }) as {
    title: string;
    question: string;
    domains: string[];
    framing: string;
    action?: "scorecard" | "chat";
    address?: string;
  }[];

  // Address-anchored personas open the parcel's Scorecard; code-research
  // personas open the analyst directly via the ?q= auto-send (App.tsx consumes
  // it). Missing i18n fields fall back to chat (the i18n cast is unchecked).
  function handleClick(p: (typeof personas)[number], index: number) {
    if (p.action === "scorecard" && p.address) {
      track("hero_address_submit", { source: "persona", persona: index, address: p.address });
      navigate(buildScorecardHref(null, p.address)!);
    } else {
      track("hero_librarian_click", { source: "persona", persona: index });
      navigate(`/?q=${encodeURIComponent(p.question)}`);
    }
  }

  return (
    <section ref={ref} className="py-24 px-6">
      <div className="max-w-6xl mx-auto space-y-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
          className="text-center space-y-4"
        >
          <h2 className="text-section text-text-primary">
            {t("personas.heading")}
          </h2>
          <p className="text-lead text-text-secondary max-w-lg mx-auto">
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
              className="h-full"
            >
              <Card
                padding="lg"
                interactive
                accentEdge
                onClick={() => handleClick(p, i)}
                className="group h-full"
              >
                <div className="space-y-5">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-accent/15 flex items-center justify-center text-accent">
                      {PERSONA_ICONS[i]}
                    </div>
                    <h3 className="text-subtitle text-text-primary">{p.title}</h3>
                  </div>

                  <div className="bg-dark-bg rounded-xl px-5 py-4 text-body text-text-primary leading-relaxed border border-dark-border-subtle group-hover:border-accent/20 transition-colors">
                    &ldquo;{p.question}&rdquo;
                  </div>

                  <div>
                    <div className="text-overline uppercase text-text-muted mb-2">{t("personas.returns")}</div>
                    <div className="flex flex-wrap gap-1.5">
                      {p.domains.map((d) => (
                        <Chip key={d} tone="neutral" size="sm">{d}</Chip>
                      ))}
                    </div>
                  </div>

                  <p className="text-caption text-text-muted italic">{p.framing}</p>

                  {/* Explicit action cue — turns the card from example text into a door. */}
                  <div className="text-caption font-medium text-accent group-hover:text-accent-hover transition-colors">
                    {p.action === "scorecard" ? t("personas.actionScorecard") : t("personas.actionChat")}
                  </div>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
