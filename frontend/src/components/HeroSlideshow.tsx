import { useEffect, useState } from "react";

const SLIDES = [
  "https://images.unsplash.com/photo-1494522855154-9297ac14b55f?w=1920&q=80",
  "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=1920&q=80",
  "https://images.unsplash.com/photo-1494522358652-f30e61a60313?w=1920&q=80",
  "https://images.unsplash.com/photo-1564505750082-7e87dbed6c2c?w=1920&q=80",
  "https://images.unsplash.com/photo-1531263939005-49b1ec38c5b9?w=1920&q=80",
];

const INTERVAL_MS = 6000;

export function HeroSlideshow() {
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % SLIDES.length), INTERVAL_MS);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="absolute inset-0 z-0 overflow-hidden bg-[#090d16]">
      {SLIDES.map((src, i) => (
        <img
          key={src}
          src={src}
          alt=""
          className="absolute inset-0 w-full h-full object-cover transition-opacity duration-[2000ms] brightness-50 contrast-125"
          style={{ opacity: i === idx ? 1 : 0 }}
        />
      ))}
      <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-black/30 to-black/60" />
    </div>
  );
}
