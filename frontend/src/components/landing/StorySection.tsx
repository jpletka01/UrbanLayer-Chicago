import { motion, useInView } from "motion/react";
import { useRef } from "react";

interface Props {
  title: string;
  subtitle: string;
  align?: "left" | "right";
}

// A themed statement band (no stock photography) — a big claim over the near-black canvas with
// a directional accent bloom + a faint masked grid. Flips with the theme (token text).
export function StorySection({ title, subtitle, align = "left" }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <section ref={ref} className="relative py-28 md:py-32 px-6 overflow-hidden bg-dark-bg">
      {/* Directional accent bloom on the copy side */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            align === "right"
              ? "radial-gradient(48rem 36rem at 100% 50%, rgb(var(--accent) / 0.10), transparent 60%)"
              : "radial-gradient(48rem 36rem at 0% 50%, rgb(var(--accent) / 0.10), transparent 60%)",
        }}
      />
      {/* Faint technical grid, radial-masked to fade at the edges */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(rgb(var(--border) / 0.7) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--border) / 0.7) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "radial-gradient(ellipse at center, black 25%, transparent 75%)",
          WebkitMaskImage: "radial-gradient(ellipse at center, black 25%, transparent 75%)",
        }}
      />
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={inView ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className={`relative z-10 max-w-5xl mx-auto w-full ${align === "right" ? "text-right" : "text-left"}`}
      >
        <h2 className={`text-section text-text-primary mb-4 max-w-2xl ${align === "right" ? "ml-auto" : ""}`}>
          {title}
        </h2>
        <p className={`text-lead text-text-secondary max-w-lg ${align === "right" ? "ml-auto" : ""}`}>
          {subtitle}
        </p>
      </motion.div>
    </section>
  );
}
