// A figure that counts up from zero the first time its block scrolls into view (owner, 2026-11-12: the landing's
// stats and money cards). Once only; with reduced motion, or no IntersectionObserver, it shows the final value.
import { useEffect, useRef, useState, type RefObject } from "react";

function reducedMotion(): boolean {
  try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; }
}

/** 0 → 1 progress for everything in `ref`, eased, starting the first time it is at least half visible. */
export function useCountUp(ref: RefObject<HTMLElement | null>, durationMs = 1400): number {
  const [p, setP] = useState(() => (typeof IntersectionObserver === "undefined" || reducedMotion() ? 1 : 0));
  const started = useRef(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || p === 1 || started.current) return;
    let raf = 0;
    const io = new IntersectionObserver((entries) => {
      if (started.current || !entries.some((e) => e.isIntersecting)) return;
      started.current = true;
      io.disconnect();
      const t0 = performance.now();
      const step = (now: number) => {
        const t = Math.min(1, (now - t0) / durationMs);
        setP(1 - Math.pow(1 - t, 3));
        if (t < 1) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    }, { threshold: 0.5 });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [ref, durationMs, p]);
  return p;
}

/** A whole number at progress `p`, grouped for the language. */
export function countText(value: number, p: number, locale: string): string {
  return Math.round(value * p).toLocaleString(locale);
}
