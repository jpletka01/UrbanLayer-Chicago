import { staticMapUrl, CHI_CITY } from "../../lib/staticMap";

// Hero backdrop grounded in real geography: a dark-v11 Chicago basemap, faded and radial-masked
// so the split hero content stays readable, warmed by an orange bloom. Falls back to just the
// bloom when the Mapbox token is absent.
export function HeroBackdrop() {
  const map = staticMapUrl({ ...CHI_CITY, zoom: 12, width: 1280, height: 760 });

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {map && (
        <img
          src={map}
          alt=""
          className="absolute inset-0 w-full h-full object-cover opacity-30"
          style={{
            maskImage: "radial-gradient(ellipse 85% 75% at 60% 42%, black 20%, transparent 78%)",
            WebkitMaskImage: "radial-gradient(ellipse 85% 75% at 60% 42%, black 20%, transparent 78%)",
          }}
        />
      )}
      {/* Warm ambient bloom behind the headline */}
      <div
        className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          width: 900,
          height: 900,
          background: "radial-gradient(circle, rgba(249,164,116,0.14), transparent 70%)",
          filter: "blur(130px)",
        }}
      />
    </div>
  );
}
