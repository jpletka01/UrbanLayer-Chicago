// Item 89's skeleton rule, shared by the Profile's tabs: a block that waits on a late part keeps its own outline
// in its final shape, named while it waits, and says "Couldn't check in time · Retry" in the same place.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { LoaderCircle, RotateCw, TriangleAlert } from "lucide-react";
import { STROKE } from "../icons";
import type { LateBlockState } from "./moneyModel";

export function LateSlot({ state, what, onRetry, skeleton, children }: {
  state: LateBlockState; what: string; onRetry: () => void; skeleton: ReactNode; children: ReactNode;
}) {
  const { t } = useTranslation("next");
  if (state === "loading") {
    return (
      <div aria-busy="true" className="flex flex-col gap-3">
        <p className="flex items-center gap-2 text-caption nx-muted" role="status">
          <LoaderCircle aria-hidden className="h-3.5 w-3.5 animate-spin" strokeWidth={STROKE} />
          {t("profile.money.checking", { what })}
        </p>
        {skeleton}
      </div>
    );
  }
  if (state === "timedOut" || state === "failed") return <RetryLine state={state} what={what} onRetry={onRetry} />;
  return <>{children}</>;
}

export function RetryLine({ state, what, onRetry }: { state: "timedOut" | "failed"; what: string; onRetry: () => void }) {
  const { t } = useTranslation("next");
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption" role={state === "failed" ? "alert" : undefined} data-late={state}>
      <TriangleAlert aria-hidden className="h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} />
      {state === "timedOut" ? t("profile.parts.timedOut", { list: what }) : t("profile.parts.failed", { list: what })}
      <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 underline underline-offset-2 touch-target">
        <RotateCw aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
        {t("profile.parts.retry")}
      </button>
    </p>
  );
}

export const pulse = "block rounded bg-nx-ink/10 motion-safe:animate-pulse";

export function BarsSkeleton({ rows }: { rows: number }) {
  return (
    <div aria-hidden className="flex flex-col gap-3">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="grid grid-cols-[4.5rem_1fr] items-center gap-3">
          <span className={`${pulse} h-3`} />
          <span className={`${pulse} h-3`} style={{ width: `${80 - i * 14}%` }} />
        </div>
      ))}
    </div>
  );
}
