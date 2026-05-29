import { useLayoutEffect, useRef, useState, type ReactNode } from "react";

interface Props {
  className?: string;
  children: ReactNode;
}

export function Tooltip({ className = "", children }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const trigger = el.parentElement;
    if (!trigger) return;

    const tr = trigger.getBoundingClientRect();
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    const pad = 8;
    const gap = 8;

    let left = tr.left + tr.width / 2 - w / 2;
    let top = tr.top - h - gap;

    left = Math.max(pad, Math.min(left, window.innerWidth - w - pad));
    if (top < pad) top = tr.bottom + gap;

    setPos({ left, top });
  }, []);

  return (
    <div
      ref={ref}
      className={`fixed z-50 rounded-lg border border-[#444]
                  shadow-[0_4px_24px_rgba(0,0,0,0.7)] pointer-events-none ${className}`}
      style={
        pos
          ? { left: pos.left, top: pos.top, backgroundColor: "#333" }
          : { opacity: 0, backgroundColor: "#333" }
      }
    >
      {children}
    </div>
  );
}
