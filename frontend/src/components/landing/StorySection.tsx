import { motion, useInView } from "motion/react";
import { useRef, useState } from "react";

interface Props {
  image: string;
  title: string;
  subtitle: string;
  align?: "left" | "right";
}

export function StorySection({ image, title, subtitle, align = "left" }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });
  const [hovered, setHovered] = useState(false);

  return (
    <section
      ref={ref}
      className="relative h-[50vh] min-h-[360px] overflow-hidden cursor-default"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <motion.img
        src={image}
        alt=""
        className="absolute inset-0 w-full h-full object-cover"
        style={{ filter: "brightness(0.35)" }}
        animate={{ scale: hovered ? 1.03 : 1 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        loading="lazy"
      />
      <div className="relative z-10 h-full flex items-center">
        <motion.div
          initial={{ opacity: 0, x: align === "left" ? -30 : 30 }}
          animate={inView
            ? { opacity: 1, x: 0, y: hovered ? -8 : 0 }
            : {}
          }
          transition={{ duration: 0.5, ease: "easeOut" }}
          className={`max-w-5xl mx-auto w-full px-4 md:px-8 ${align === "right" ? "text-right" : "text-left"}`}
        >
          {/* over-image text: white stays (exempt from the dark-chrome neutral ramp) */}
          <h2 className="text-section text-white mb-3">
            {title}
          </h2>
          <p
            className="text-lead text-white/70 max-w-md"
            style={align === "right" ? { marginLeft: "auto" } : {}}
          >
            {subtitle}
          </p>
        </motion.div>
      </div>
    </section>
  );
}
