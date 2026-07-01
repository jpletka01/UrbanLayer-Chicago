import { useTranslation } from "react-i18next";
import { Chip } from "../ui/Chip";

// A compact, realistic mock Scorecard shown beside the hero headline — the product, on the
// first screen. Static preview (no data fetch); values mirror a real B3-2 corridor parcel.
// Reuses the depth.* labels so it stays translated + consistent with DepthShowcase.
const STATS = [
  { key: "depth.estAnnualTax", value: "$8,420", accent: true },
  { key: "depth.lot", value: "3,125 ft²" },
  { key: "depth.building", value: "2-story" },
];

const SCORES = [
  { key: "depth.walkScore", value: 94 },
  { key: "depth.transitScore", value: 88 },
];

export function HeroScorecardPreview() {
  const { t } = useTranslation("landing");

  return (
    <div className="relative mx-auto w-full max-w-md">
      {/* Ambient bloom behind the card */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -inset-6 rounded-full"
        style={{ background: "radial-gradient(circle, rgba(249,164,116,0.16), transparent 70%)", filter: "blur(50px)" }}
      />
      <div className="relative rounded-bento border border-white/10 bg-white/[0.03] backdrop-blur-md p-5 space-y-4 shadow-[0_20px_60px_-20px_rgba(0,0,0,0.6)]">
        {/* Header: address + PIN + verdict */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-overline uppercase text-accent">
              <span className="w-1.5 h-1.5 rounded-full bg-accent" />
              Property Scorecard
            </div>
            <div className="text-title text-white mt-1 truncate">1601 N Milwaukee Ave</div>
            <div className="font-mono text-caption text-white/50">14-33-423-048-0000</div>
          </div>
          <Chip tone="positive" size="md">{t("heroPreview.verdict")}</Chip>
        </div>

        {/* Zoning */}
        <div className="flex items-center gap-2 border-t border-white/10 pt-3">
          <Chip tone="accent" mono size="md">B3-2</Chip>
          <span className="text-caption text-white/70 truncate">{t("depth.sampleZoneDesc")}</span>
        </div>

        {/* Key stats */}
        <div className="grid grid-cols-3 gap-3 border-t border-white/10 pt-3">
          {STATS.map((s) => (
            <div key={s.key}>
              <div className="text-overline uppercase text-white/40">{t(s.key)}</div>
              <div className={`text-title ${s.accent ? "text-accent" : "text-white"}`}>{s.value}</div>
            </div>
          ))}
        </div>

        {/* Walk / transit scores */}
        <div className="space-y-2 border-t border-white/10 pt-3">
          {SCORES.map((s) => (
            <div key={s.key} className="flex items-center gap-3 text-caption">
              <span className="text-white/60 w-24 shrink-0">{t(s.key)}</span>
              <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-accent rounded-full" style={{ width: `${s.value}%` }} />
              </div>
              <span className="font-mono text-white w-7 text-right">{s.value}</span>
            </div>
          ))}
        </div>

        {/* Overlays */}
        <div className="flex flex-wrap gap-1.5 border-t border-white/10 pt-3">
          {[t("depth.plannedDevelopment"), t("depth.pedestrianStreet"), t("depth.todEligible")].map((label) => (
            <Chip key={label} tone="neutral" size="sm">{label}</Chip>
          ))}
        </div>

        {/* Footer CTA caption */}
        <div className="border-t border-white/10 pt-3 text-caption text-accent font-medium">
          {t("heroPreview.cta")} →
        </div>
      </div>
    </div>
  );
}
