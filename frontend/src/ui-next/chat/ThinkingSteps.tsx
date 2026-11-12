// What the analyst is doing while an answer is on its way (owner's review, 2026-11-12: answers can take 45 s, the
// old dots looked homemade). The steps come from the turn's plan (useChat's activities: the lot, zoning, crime,
// permits, the code …), shown one at a time like a thinking trace: the current step as a shimmering line, the ones
// before it checked. The backend sends no per-lookup progress yet, so the steps are paced on a timer and all check
// off when the records arrive; nothing claims to be done before it is. Once the answer starts, they fold into one
// line ("Checked 4 sources · 12 s") that opens the list. Reduced motion: no shimmer, same words.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, ChevronRight } from "lucide-react";
import type { ActivityItem } from "../../lib/types";
import { STROKE } from "../icons";

/** Seconds between revealing one planned step and the next while the records are being fetched. */
export const STEP_PACE_S = 2.4;

export interface StepView { id: string; label: string; state: "done" | "current" | "waiting" }

/** The steps to show `elapsed` seconds after the plan arrived. Planned lookups reveal one per STEP_PACE_S; the last
    one revealed stays current until the records arrive (the activities flip to done), never checked early. */
export function stepsAt(activities: ActivityItem[], elapsed: number): StepView[] {
  const lookups = activities.filter((a) => a.id.startsWith("retrieve_") || a.id === "location");
  const others = activities.filter((a) => !lookups.includes(a));
  const fetched = lookups.length > 0 && lookups.every((a) => a.status === "done");
  const out: StepView[] = [];
  for (const a of others.filter((o) => o.id === "routing")) out.push({ id: a.id, label: a.label, state: a.status === "done" ? "done" : "current" });
  if (fetched) {
    for (const a of lookups) out.push({ id: a.id, label: a.label, state: "done" });
  } else {
    // What is already done (the place was found) shows at once; pending lookups appear one per STEP_PACE_S.
    for (const a of lookups.filter((l) => l.status === "done")) out.push({ id: a.id, label: a.label, state: "done" });
    const pending = lookups.filter((l) => l.status !== "done");
    const shown = Math.min(pending.length, 1 + Math.floor(elapsed / STEP_PACE_S));
    pending.slice(0, shown).forEach((a, i) => out.push({ id: a.id, label: a.label, state: i < shown - 1 ? "done" : "current" }));
  }
  for (const a of others.filter((o) => o.id !== "routing")) out.push({ id: a.id, label: a.label, state: a.status === "done" ? "done" : "current" });
  return out;
}

export function ThinkingSteps({ activities, answering }: { activities: ActivityItem[]; answering: boolean }) {
  const { t } = useTranslation("next");
  const [startAt] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());
  const [open, setOpen] = useState(false);
  // When the plan arrived and when the answer began, noted by the clock below (refs: no extra render).
  const planAt = useRef<number | null>(null);
  const doneAt = useRef<number | null>(null);
  const planned = activities.some((a) => a.id.startsWith("retrieve_"));

  useEffect(() => {
    if (answering) { doneAt.current ??= Date.now(); return; }
    const id = window.setInterval(() => {
      const t0 = Date.now();
      if (planned) planAt.current ??= t0;
      setNow(t0);
    }, 400);
    return () => window.clearInterval(id);
  }, [answering, planned]);

  // eslint-disable-next-line react-hooks/refs -- the clock ticks every 400 ms; the ref is the plan's arrival time
  const steps = stepsAt(activities, planAt.current === null ? 0 : (now - planAt.current) / 1000);
  const lookups = steps.filter((s) => s.id.startsWith("retrieve_")).length;

  if (answering) {
    // eslint-disable-next-line react-hooks/refs -- read once the answer has begun
    const secs = Math.max(1, Math.round(((doneAt.current ?? now) - startAt) / 1000));
    return (
      <div className="flex flex-col gap-1.5 pl-9" data-testid="chat-steps">
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="inline-flex items-center gap-1.5 self-start text-caption text-nx-pill-purple touch-target">
          <ChevronRight aria-hidden className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-90" : ""}`} strokeWidth={STROKE} />
          {t("chat.steps.summary", { count: lookups, seconds: secs })}
        </button>
        {open && <StepList steps={steps.map((s) => ({ ...s, state: "done" as const }))} />}
      </div>
    );
  }

  const current = steps.find((s) => s.state === "current") ?? { id: "start", label: t("chat.steps.reading"), state: "current" as const };
  return (
    <div className="flex flex-col gap-2 pl-9" data-testid="chat-steps" role="status" aria-live="polite">
      <StepList steps={steps.filter((s) => s.state === "done")} />
      <p className="nx-shimmer text-body font-medium motion-safe:animate-text-shimmer" data-testid="chat-step-current">{current.label}</p>
    </div>
  );
}

function StepList({ steps }: { steps: StepView[] }) {
  if (steps.length === 0) return null;
  return (
    <ol className="flex flex-col gap-1">
      {steps.map((s) => (
        <li key={s.id} className="flex items-center gap-2 text-caption nx-muted">
          <Check aria-hidden className="h-3.5 w-3.5 shrink-0 text-nx-pill-green" strokeWidth={2} />
          {s.label}
        </li>
      ))}
    </ol>
  );
}
