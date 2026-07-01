// Bento hero backdrop (design-system hero.md): a near-black canvas broken up by a big blurred
// orange bloom, a faint 60px grid, concentric technical rings (one dashed), and centered
// crosshairs — all masked by a radial gradient so the pattern fades smoothly at the edges.
// Purely decorative + non-interactive; sits behind the hero content.
const RINGS = [280, 520, 760, 1040, 1400];

export function HeroBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {/* Base ambient bloom — warm orange, heavily blurred, centered behind the headline. */}
      <div
        className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          width: 900,
          height: 900,
          background: "radial-gradient(circle, rgba(249,164,116,0.16), transparent 70%)",
          filter: "blur(130px)",
        }}
      />
      {/* Layered geometry, masked to dissolve into the background at the edges. */}
      <div
        className="absolute inset-0"
        style={{
          maskImage: "radial-gradient(ellipse at center, black 40%, transparent 80%)",
          WebkitMaskImage: "radial-gradient(ellipse at center, black 40%, transparent 80%)",
        }}
      >
        {/* 60px grid at ~2% white */}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />
        {/* Concentric rings — subtle white borders, one dashed for a technical feel. */}
        {RINGS.map((d, i) => (
          <div
            key={d}
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border"
            style={{
              width: d,
              height: d,
              borderColor: `rgba(255,255,255,${Math.max(0.02, 0.08 - i * 0.013)})`,
              borderStyle: i === 2 ? "dashed" : "solid",
            }}
          />
        ))}
        {/* Crosshairs through the center, fading to transparent at both ends. */}
        <div
          className="absolute inset-x-0 top-1/2 h-px"
          style={{ background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent)" }}
        />
        <div
          className="absolute inset-y-0 left-1/2 w-px"
          style={{ background: "linear-gradient(180deg, transparent, rgba(255,255,255,0.08), transparent)" }}
        />
      </div>
    </div>
  );
}
