import { motion, useInView } from "motion/react";
import { useRef } from "react";

interface Props {
  /** Unsplash (or other) image URL — Chicago cityscape / planning / construction. */
  image: string;
  title: string;
  subtitle: string;
  /** Which side the image sits on (image + text alternate down the page). */
  align?: "left" | "right";
}

// Split interstitial: a framed Chicago photo on one side, the claim on the other. Alternates
// sides down the page. Photos are easy to swap (just change the URL passed from App.tsx).
export function StorySection({ image, title, subtitle, align = "left" }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });
  const imageRight = align === "right";

  return (
    <section ref={ref} className="py-20 md:py-24 px-6">
      <div className="max-w-6xl mx-auto grid md:grid-cols-2 gap-8 md:gap-14 items-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={inView ? { opacity: 1, scale: 1 } : {}}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className={`relative rounded-bento overflow-hidden aspect-[4/3] border border-dark-border shadow-card ${
            imageRight ? "md:order-2" : ""
          }`}
        >
          <img src={image} alt="" loading="lazy" className="absolute inset-0 w-full h-full object-cover" />
          {/* Cohesion wash + inset hairline so the photo reads as part of the dark UI */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/45 via-black/10 to-transparent" />
          <div className="pointer-events-none absolute inset-0 rounded-bento ring-1 ring-inset ring-white/10" />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.1, ease: "easeOut" }}
          className={imageRight ? "md:order-1" : ""}
        >
          <h2 className="text-section text-text-primary mb-4">{title}</h2>
          <p className="text-lead text-text-secondary max-w-md">{subtitle}</p>
        </motion.div>
      </div>
    </section>
  );
}
