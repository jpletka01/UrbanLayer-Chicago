// Folded questions (shared on its second use, Item 75): the landing's FAQ (Phase 8, owner-approved) and Pricing's
// questions about paying (Item 123). Each question is a block-filled row that opens in place; a chevron says it opens.
// Native <details>, so it works with the keyboard and screen readers and without script.
import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { STROKE } from "../icons";

export function Faq({ id, title, items, center = false, titleClassName = "text-[2rem] font-bold tracking-[-0.02em]" }: {
  id: string;
  title: ReactNode;
  items: { key: string; q: ReactNode; a: ReactNode }[];
  /** Center the title over the questions (Pricing's centered page). */
  center?: boolean;
  titleClassName?: string;
}) {
  return (
    <section className="mx-auto flex w-full max-w-[760px] flex-col gap-3" aria-labelledby={id} data-testid={id}>
      <h2 id={id} className={`mb-2 ${titleClassName} ${center ? "text-center" : ""}`}>{title}</h2>
      {items.map(({ key, q, a }) => (
        <details key={key} className="group rounded-2xl bg-nx-block">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 font-semibold [&::-webkit-details-marker]:hidden">
            {q}
            <ChevronDown aria-hidden className="h-4 w-4 shrink-0 nx-muted transition-transform group-open:rotate-180" strokeWidth={STROKE} />
          </summary>
          <p className="-mt-1 px-5 pb-4 nx-muted">{a}</p>
        </details>
      ))}
    </section>
  );
}
