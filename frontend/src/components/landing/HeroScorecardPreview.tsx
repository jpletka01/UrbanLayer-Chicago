import { useTranslation } from "react-i18next";
import { Chip } from "../ui/Chip";
import { useThemeContext } from "../../contexts/ThemeContext";

// A compact, realistic mock Scorecard shown beside the hero headline — the product, on the
// first screen. Conclusion-first: leads with the verdict, then a few high-signal metrics
// (zoning, tax, walk/transit). Static preview; values mirror a real B3-2 corridor parcel.
const SCORES = [
  { key: "depth.walkScore", value: 94 },
  { key: "depth.transitScore", value: 88 },
];

export function HeroScorecardPreview() {
  const { t } = useTranslation("landing");
  // On the light hero the card reads as a dark "product screenshot" floating on
  // warm paper: mode-lock it to dark + give it an opaque surface (the hero's dark
  // bg no longer sits behind it, so the translucent chrome would wash out).
  const light = useThemeContext().resolvedTheme === "light";

  return (
    <div className="relative mx-auto w-full max-w-md" data-theme={light ? "dark" : undefined}>
      {/* Ambient bloom behind the card */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -inset-6 rounded-full"
        style={{ background: "radial-gradient(circle, rgba(249,164,116,0.16), transparent 70%)", filter: "blur(50px)" }}
      />
      <div className={`relative rounded-bento border border-white/10 backdrop-blur-md p-6 space-y-5 shadow-[0_20px_60px_-20px_rgba(0,0,0,0.6)] ${light ? "bg-dark-surface" : "bg-white/[0.03]"}`}>
        {/* Header: provenance + address + PIN */}
        <div>
          <div className="flex items-center gap-1.5 text-overline uppercase text-accent">
            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
            Property Scorecard
          </div>
          <div className="text-subtitle text-white mt-1.5">1601 N Milwaukee Ave</div>
          <div className="font-mono text-caption text-white/60">14-33-423-048-0000</div>
        </div>

        {/* Verdict band — the answer, first */}
        <div className="flex items-center gap-3 rounded-xl border border-state-positive/30 bg-state-positive/10 px-4 py-3">
          <svg className="w-6 h-6 shrink-0 text-state-positive" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="min-w-0">
            <div className="text-title text-state-positive font-semibold">{t("heroPreview.verdict")}</div>
            <div className="text-caption text-white/60 truncate">{t("depth.sampleZoneDesc")}</div>
          </div>
          <Chip tone="accent" mono size="md" className="ml-auto font-semibold">B3-2</Chip>
        </div>

        {/* One headline metric */}
        <div className="flex items-baseline justify-between border-t border-white/10 pt-4">
          <span className="text-caption uppercase tracking-wide text-white/50">{t("depth.estAnnualTax")}</span>
          <span className="text-stat text-accent">$8,420</span>
        </div>

        {/* Walk / transit scores — larger numbers */}
        <div className="space-y-2.5">
          {SCORES.map((s) => (
            <div key={s.key} className="flex items-center gap-3">
              <span className="text-caption text-white/70 w-24 shrink-0">{t(s.key)}</span>
              <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-accent rounded-full" style={{ width: `${s.value}%` }} />
              </div>
              <span className="font-mono text-body text-white w-8 text-right">{s.value}</span>
            </div>
          ))}
        </div>

        {/* CTA caption */}
        <div className="border-t border-white/10 pt-4 text-caption text-accent font-semibold">
          {t("heroPreview.cta")} →
        </div>
      </div>
    </div>
  );
}
