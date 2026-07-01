// Clean abstract hero backdrop — a warm orange bloom over a faint, radial-masked grid. No map
// (its labels fought the type) and no busy "radar" rings; just quiet depth behind the content.
export function HeroBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {/* Warm ambient bloom behind the headline */}
      <div
        className="absolute left-[38%] top-[42%] -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          width: 820,
          height: 820,
          background: "radial-gradient(circle, rgba(249,164,116,0.16), transparent 70%)",
          filter: "blur(130px)",
        }}
      />
      {/* Faint grid, radial-masked so it dissolves at the edges */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          maskImage: "radial-gradient(ellipse 80% 70% at 50% 45%, black 30%, transparent 80%)",
          WebkitMaskImage: "radial-gradient(ellipse 80% 70% at 50% 45%, black 30%, transparent 80%)",
        }}
      />
    </div>
  );
}
