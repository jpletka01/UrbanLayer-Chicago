// ConfidenceCaption / ConfidenceValue — the one way a figure says how far to trust it
// (WS0 M4; spec: claude-context/guides/source-confidence.md §4 and plans/WS0 §5).
//
// Quiet by default: a caption prints only when the tier is C–F, the figure is low or
// withheld, or its source is more than 24 months old (`wantsCaption`). Everything else
// keeps its five fields in the label's tooltip (`SourceTooltip`). The words are always on
// the page; the hatch pattern and the faded value only reinforce them.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { Provenance } from "../../lib/api";
import { captionParts, displayState, sourceBullets, type CaptionOpts } from "../../lib/confidence";
import { InfoTooltip } from "../InfoTooltip";

type Size = "caption" | "micro";

/** A one-line caption under or beside a figure. Renders nothing when the rule says to stay quiet. */
export function ConfidenceCaption({ entry, size = "caption", className = "", prefix, inline = false, unavailable = false, ...opts }: {
  entry: Provenance | null | undefined;
  /** A span that continues the line it sits on ("class norm 5.3% · tax year 2023"). */
  inline?: boolean;
  /** The source couldn't be checked today (WS6): says so instead of any other caption. */
  unavailable?: boolean;
  /** Names the figure when several captions share a block ("Price per ft²"). */
  prefix?: string;
  /** `micro` for KPI tiles, the chat rail and PDF footnotes; `caption` at page scale. */
  size?: Size;
  className?: string;
} & CaptionOpts) {
  const { t } = useTranslation("common");
  const caption = captionParts(entry, t, opts);
  if (!caption.visible && !unavailable) return null;
  const text = size === "micro" ? "text-micro" : "text-caption";
  const Tag = inline ? "span" : "p";
  return (
    <Tag data-testid="confidence-caption" data-state={unavailable ? "unavailable" : caption.state}
      className={`${text} text-text-muted leading-snug ${className}`}>
      {prefix && <span className="text-text-secondary">{prefix}: </span>}
      {unavailable ? t("confidence.unavailable") : caption.withheld ?? (
        <>
          {caption.ai && (
            <span className="mr-1 rounded-md border border-dark-border px-1 font-mono text-micro">
              {t("confidence.ai")}
            </span>
          )}
          {caption.lead && <span className="text-state-warning">{caption.lead}</span>}
          {caption.lead && caption.parts.length > 0 && " · "}
          {caption.parts.join(" · ")}
        </>
      )}
    </Tag>
  );
}

/** A figure's value in its confidence state: low is quieter (text-secondary, never opacity,
    so contrast holds), withheld is a dash. Pass `entry` undefined to render the value as is. */
export function ConfidenceValue({ entry, children, className = "", unavailable = false }: {
  entry: Provenance | null | undefined;
  children: ReactNode;
  className?: string;
  /** The source couldn't be checked today (WS6): a dash, like a withheld figure. */
  unavailable?: boolean;
}) {
  const state = displayState(entry);
  if (state === "withheld" || unavailable) {
    return <span className={`text-text-muted ${className}`} data-state={unavailable ? "unavailable" : "withheld"}>—</span>;
  }
  if (state === "low") {
    return <span className={`text-text-secondary font-normal ${className}`} data-state="low">{children}</span>;
  }
  return <span className={className}>{children}</span>;
}

/** A label whose tooltip carries the figure's "Source" block after its own definition.
    Without an entry it is the same InfoTooltip it always was. */
export function SourceTooltip({ label, description, entry, children, ...opts }: {
  label: string;
  description?: string;
  entry: Provenance | null | undefined;
  children: ReactNode;
} & CaptionOpts) {
  const { t } = useTranslation("common");
  const bullets = sourceBullets(entry, t, opts);
  if (!description && bullets.length === 0) return <>{children}</>;
  return (
    <InfoTooltip content={{
      label,
      description: description ?? t("confidence.sourceHeading"),
      bullets,
    }}>
      {children}
    </InfoTooltip>
  );
}

/** A caption for a figure that has no entry of its own but a known method: the violations'
    category rows are our keyword grouping of free text, whatever the address. */
export function MethodCaption({ method, size = "caption", className = "" }: {
  method: string;
  size?: Size;
  className?: string;
}) {
  const { t } = useTranslation("common");
  return (
    <p className={`${size === "micro" ? "text-micro" : "text-caption"} text-text-muted leading-snug ${className}`}>
      {t(`confidence.method.${method}`)}
    </p>
  );
}
