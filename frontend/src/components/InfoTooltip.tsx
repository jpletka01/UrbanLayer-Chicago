import { createPortal } from "react-dom";
import { forwardRef, useCallback, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { getTermInfo, type TermInfo } from "../lib/termDefinitions";

interface Props {
  term?: string;
  content?: TermInfo;
  children: ReactNode;
}

export function InfoTooltip({ term, content, children }: Props) {
  const [visible, setVisible] = useState(false);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const hideTimeout = useRef<ReturnType<typeof setTimeout>>(undefined);

  const info = content ?? (term ? getTermInfo(term) : null);

  const show = useCallback(() => {
    clearTimeout(hideTimeout.current);
    setVisible(true);
  }, []);

  const scheduleHide = useCallback(() => {
    hideTimeout.current = setTimeout(() => setVisible(false), 150);
  }, []);

  const handleClickAway = useCallback((e: MouseEvent) => {
    if (
      triggerRef.current?.contains(e.target as Node) ||
      popoverRef.current?.contains(e.target as Node)
    ) return;
    setVisible(false);
  }, []);

  if (!info) return <>{children}</>;

  return (
    <>
      <span
        ref={triggerRef}
        className="border-b border-dotted border-current opacity-70 hover:opacity-100 cursor-help transition-opacity"
        onMouseEnter={show}
        onMouseLeave={scheduleHide}
        onClick={(e) => {
          e.stopPropagation();
          if (visible) { setVisible(false); return; }
          show();
          document.addEventListener("click", handleClickAway, { once: true });
        }}
      >
        {children}
      </span>
      {visible && (
        <Popover
          ref={popoverRef}
          triggerRef={triggerRef}
          info={info}
          onMouseEnter={show}
          onMouseLeave={scheduleHide}
        />
      )}
    </>
  );
}

interface PopoverProps {
  triggerRef: React.RefObject<HTMLSpanElement | null>;
  info: TermInfo;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

const Popover = forwardRef<HTMLDivElement, PopoverProps>(
  function Popover({ triggerRef, info, onMouseEnter, onMouseLeave }, ref) {
    const innerRef = useRef<HTMLDivElement>(null);
    const combinedRef = (node: HTMLDivElement | null) => {
      (innerRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
      if (typeof ref === "function") ref(node);
      else if (ref) (ref as React.MutableRefObject<HTMLDivElement | null>).current = node;
    };

    const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

    useLayoutEffect(() => {
      const trigger = triggerRef.current;
      const el = innerRef.current;
      if (!trigger || !el) return;

      const tr = trigger.getBoundingClientRect();
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      const pad = 8;
      const gap = 6;

      let left = tr.left + tr.width / 2 - w / 2;
      let top = tr.top - h - gap;

      left = Math.max(pad, Math.min(left, window.innerWidth - w - pad));
      if (top < pad) top = tr.bottom + gap;
      top = Math.min(top, window.innerHeight - h - pad);

      setPos({ left, top });
    }, [triggerRef]);

    return createPortal(
      <div
        ref={combinedRef}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        className="fixed z-[60] rounded-lg border border-[#444] shadow-[0_4px_24px_rgba(0,0,0,0.7)]"
        style={{
          backgroundColor: "#333",
          maxWidth: 260,
          ...(pos ? { left: pos.left, top: pos.top } : { opacity: 0, pointerEvents: "none" as const }),
        }}
      >
        <div className="px-3 py-2.5 space-y-1.5">
          <div className="text-[11px] font-medium text-text-secondary">{info.label}</div>
          <div className="text-[10px] text-text-muted leading-relaxed">{info.description}</div>
          {info.bullets.length > 0 && (
            <ul className="space-y-0.5 pt-0.5">
              {info.bullets.map((b) => (
                <li key={b} className="flex items-start gap-1.5 text-[10px] text-text-muted leading-relaxed">
                  <span className="w-1 h-1 rounded-full bg-text-muted/60 shrink-0 mt-[5px]" />
                  {b}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>,
      document.body,
    );
  },
);
