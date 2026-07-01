// Faint accent-orange plat-grid rails along the outer page margins, continuing the hero
// backdrop's survey-map language down the landing page. Masked to the edges so the grid
// never sits under section content, and drawn at very low opacity so it can't compete
// with real orange CTAs. Uses the accent token, so it renders identically in both themes
// (the brand orange is shared) over the theme's flipping canvas.
export function AccentRails() {
  return (
    <div
      className="pointer-events-none absolute inset-0"
      aria-hidden="true"
      style={{
        backgroundImage:
          "linear-gradient(rgb(var(--accent) / 0.09) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--accent) / 0.09) 1px, transparent 1px)",
        backgroundSize: "170px 140px",
        maskImage: "linear-gradient(90deg, black, transparent 13%, transparent 87%, black)",
        WebkitMaskImage: "linear-gradient(90deg, black, transparent 13%, transparent 87%, black)",
      }}
    />
  );
}
