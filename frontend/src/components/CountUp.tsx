import { useEffect, useRef } from "react";
import {
  useMotionValue,
  useTransform,
  motion,
  animate,
  useInView,
} from "motion/react";

interface CountUpProps {
  to: number;
  format?: (n: number) => string;
  duration?: number;
  delay?: number;
  className?: string;
}

export function CountUp({
  to,
  format = String,
  duration = 1.6,
  delay = 0,
  className,
}: CountUpProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const motionVal = useMotionValue(0);
  const rounded = useTransform(motionVal, (v) => format(Math.round(v)));
  const inView = useInView(ref, { once: true });

  useEffect(() => {
    if (!inView) return;
    const controls = animate(motionVal, to, {
      duration,
      delay,
      ease: [0.16, 1, 0.3, 1],
    });
    return controls.stop;
  }, [inView, to, duration, delay, motionVal]);

  return <motion.span ref={ref} className={className}>{rounded}</motion.span>;
}
