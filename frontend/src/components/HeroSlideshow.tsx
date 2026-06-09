import { useEffect, useState } from "react";
import { HERO_SLIDE_INTERVAL_MS as INTERVAL_MS } from "../lib/constants";

const SLIDES = [
  "https://images.unsplash.com/photo-1494522855154-9297ac14b55f?w=1920&q=80",
  "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=1920&q=80",
  "https://images.unsplash.com/photo-1494522358652-f30e61a60313?w=1920&q=80",
  "https://images.unsplash.com/photo-1745872262717-69c8951b5c49?w=1920&q=80",
  "https://images.unsplash.com/photo-1616624446421-b6a136da737d?w=1920&q=80",
];

export function HeroSlideshow() {
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % SLIDES.length), INTERVAL_MS);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="absolute inset-0 z-0 overflow-hidden">
      {SLIDES.map((src, i) => (
        <img
          key={src}
          src={src}
          alt=""
          className="absolute inset-0 w-full h-full object-cover transition-opacity duration-[2000ms]"
          style={{
            opacity: i === idx ? 1 : 0,
            filter: "brightness(0.35)",
          }}
        />
      ))}
    </div>
  );
}
