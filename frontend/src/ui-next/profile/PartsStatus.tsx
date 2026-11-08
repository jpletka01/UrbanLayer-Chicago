// What the Profile is still checking, what ran out of time and what failed, by name (decision Item 89). One quiet
// line while parts are on their way, no seconds counter; "Couldn't check in time" (never "none") with Retry once a
// source passes its deadline; "Couldn't load" with Retry when a part failed.
import { useTranslation } from "react-i18next";
import { LoaderCircle, RotateCw, TriangleAlert } from "lucide-react";
import type { ProfileLatePart } from "../../lib/api";
import type { PartStatus } from "./useProfileParts";

const ORDER: ProfileLatePart[] = ["building", "history", "money", "incentives", "neighborhood", "activity", "block_face"];

export function PartsStatus({
  parts,
  timedOut,
  onRetry,
}: {
  parts: Partial<Record<ProfileLatePart, PartStatus>>;
  timedOut: Partial<Record<ProfileLatePart, string[]>>;
  onRetry: (names: ProfileLatePart[]) => void;
}) {
  const { t, i18n } = useTranslation("next");
  const list = (items: string[]) =>
    new Intl.ListFormat(i18n.language.startsWith("es") ? "es-MX" : "en-US", { style: "long", type: "conjunction" }).format(items);
  const waiting = ORDER.filter((p) => parts[p] === "waiting");
  const failed = ORDER.filter((p) => parts[p] === "failed");
  const late = ORDER.filter((p) => parts[p] === "done" && (timedOut[p]?.length ?? 0) > 0);
  const lateSources = late.flatMap((p) => timedOut[p] ?? []);
  if (!waiting.length && !failed.length && !late.length) return null;

  const retry = (names: ProfileLatePart[]) => (
    <button type="button" onClick={() => onRetry(names)} className="inline-flex items-center gap-1 underline underline-offset-2 touch-target">
      <RotateCw aria-hidden className="h-3.5 w-3.5" strokeWidth={1.5} />
      {t("profile.parts.retry")}
    </button>
  );

  return (
    <div className="mt-8 flex flex-col gap-2 text-caption" data-testid="parts-status">
      {waiting.length > 0 && (
        <p className="flex items-start gap-2 nx-muted" role="status" data-testid="parts-waiting">
          <LoaderCircle aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin" strokeWidth={1.5} />
          {t("profile.parts.stillChecking", { list: list(waiting.map((p) => t(`profile.parts.part.${p}`))) })}
        </p>
      )}
      {late.length > 0 && (
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="parts-timed-out">
          <TriangleAlert aria-hidden className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
          {t("profile.parts.timedOut", { list: list(lateSources.map((s) => t(`profile.parts.source.${s}`, { defaultValue: s }))) })}
          {retry(late)}
        </p>
      )}
      {failed.length > 0 && (
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1" role="alert" data-testid="parts-failed">
          <TriangleAlert aria-hidden className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
          {t("profile.parts.failed", { list: list(failed.map((p) => t(`profile.parts.part.${p}`))) })}
          {retry(failed)}
        </p>
      )}
    </div>
  );
}
