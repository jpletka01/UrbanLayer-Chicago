// The Profile's three answer panels (redesign plan §6a L1, decision Item 50): Build · In the way ·
// Value & cost. They replace the KPI strip and the verdict's reason pills in the first screen.
// Budget: at most 8 figures and 3 amber rows in all; each figure carries its confidence STATE as a
// short label (ConfidenceState) and its explanation behind ⓘ / ⏱ (Toggletip), never as a paragraph.
// A withheld figure shows "—" and a reason of 8 words or fewer, inline (rule §4.3: never silent).
// Presentational: the page decides every value and state; nothing here reads the API.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { ConfidenceKind } from "../../lib/confidence";
import type { CardId } from "../../lib/scorecardVerdict";
import { ConfidenceState } from "../ui/ConfidenceState";
import { StatusLabel, type StatusTone } from "../ui/StatusLabel";
import { Toggletip, type ToggletipKind } from "../ui/Toggletip";

export interface PanelFigure {
  key: string;
  label: string;
  value: ReactNode;
  /** Visible confidence state; null/undefined for a verified figure (no label). */
  state?: { kind: ConfidenceKind; low: boolean } | null;
  /** The explanation behind the figure's icon. */
  detail?: ReactNode;
  detailKind?: ToggletipKind;
  /** Text kept visible beside the ⏱ icon (the tax year). */
  detailVisible?: string;
  /** A withheld figure's short reason, shown inline under the "—". */
  withheldReason?: string;
}

export interface PanelRow {
  key: string;
  /** warning = check or act; danger = a blocker; neutral = information. */
  tone: StatusTone;
  /** When set, the row is a confidence state (Not checked ◌ / None found ∅), not a finding. */
  state?: ConfidenceKind;
  text: string;
  detail?: ReactNode;
}

/** Amber rows beyond this many collapse into "+N more" (plan §4 check 5: ≤3 amber items). */
export const MAX_AMBER_ROWS = 3;

function Figure({ f }: { f: PanelFigure }) {
  const withheld = f.state?.kind === "withheld";
  return (
    <div data-figure={f.key} className="min-w-0">
      <dt className="text-caption text-text-muted">{f.label}</dt>
      <dd className="mt-0.5 flex flex-wrap items-center gap-x-1.5 gap-y-1">
        <span className={`text-subtitle tabular-nums ${withheld ? "text-text-muted" : f.state?.low ? "text-text-secondary" : "text-text-primary"}`}>
          {withheld ? "—" : f.value}
        </span>
        {f.state && !withheld && <ConfidenceState kind={f.state.kind} low={f.state.low} />}
        {f.detail != null && (
          <Toggletip kind={f.detailKind ?? "info"} label={f.label} visible={f.detailVisible}>
            {f.detail}
          </Toggletip>
        )}
      </dd>
      {withheld && f.withheldReason && (
        <p className="mt-0.5 text-caption text-text-muted" data-withheld-reason>{f.withheldReason}</p>
      )}
    </div>
  );
}

function Row({ r }: { r: PanelRow }) {
  return (
    <li className="flex min-w-0 items-start gap-1.5">
      {r.state ? (
        <ConfidenceState kind={r.state} tone={r.tone} />
      ) : (
        <StatusLabel tone={r.tone}>{r.text}</StatusLabel>
      )}
      {r.state && <span className="text-caption text-text-secondary leading-5">{r.text}</span>}
      {r.detail != null && <Toggletip kind="info" label={r.text}>{r.detail}</Toggletip>}
    </li>
  );
}

function Panel({
  title,
  more,
  onMore,
  children,
  testId,
}: {
  title: string;
  more: string;
  onMore: () => void;
  children: ReactNode;
  testId: string;
}) {
  return (
    <section data-testid={testId} className="flex min-w-0 flex-col rounded-xl border border-dark-border bg-dark-surface p-4">
      <h3 className="text-overline uppercase text-text-muted">{title}</h3>
      <div className="mt-3 flex-1">{children}</div>
      <button
        type="button"
        onClick={onMore}
        className="mt-3 self-start rounded text-caption text-link cursor-pointer hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        {more} <span aria-hidden>↓</span>
      </button>
    </section>
  );
}

export function AnswerPanels({
  build,
  inTheWay,
  value,
  onScrollTo,
}: {
  build: PanelFigure[];
  inTheWay: PanelRow[];
  value: PanelFigure[];
  onScrollTo: (anchor: CardId) => void;
}) {
  const { t } = useTranslation("pages");
  // Amber is rationed: the first three warning rows show, the rest fold into one neutral "+N more".
  const amber = inTheWay.filter((r) => r.tone === "warning" || r.tone === "danger");
  const shownAmber = new Set(amber.slice(0, MAX_AMBER_ROWS).map((r) => r.key));
  const rows = inTheWay.filter((r) => (r.tone !== "warning" && r.tone !== "danger") || shownAmber.has(r.key));
  const hidden = amber.length - shownAmber.size;

  return (
    <div className="grid gap-3 sm:grid-cols-3" data-testid="answer-panels">
      <Panel testId="panel-build" title={t("scorecard.panels.build")} more={t("scorecard.panels.more")} onMore={() => onScrollTo("zoning")}>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-3 sm:grid-cols-1">
          {build.map((f) => <Figure key={f.key} f={f} />)}
        </dl>
      </Panel>
      <Panel testId="panel-in-the-way" title={t("scorecard.panels.inTheWay")} more={t("scorecard.panels.more")} onMore={() => onScrollTo("regulatory")}>
        <ul className="space-y-2">
          {rows.map((r) => <Row key={r.key} r={r} />)}
          {hidden > 0 && (
            <li className="text-caption text-text-muted">{t("scorecard.panels.moreRows", { count: hidden })}</li>
          )}
        </ul>
      </Panel>
      <Panel testId="panel-value" title={t("scorecard.panels.value")} more={t("scorecard.panels.more")} onMore={() => onScrollTo("property")}>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-3 sm:grid-cols-1">
          {value.map((f) => <Figure key={f.key} f={f} />)}
        </dl>
      </Panel>
    </div>
  );
}
