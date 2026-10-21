// "Data health": every data source the product shows, with what the daily checker last found.
// Worst first, so a red source is the first thing an admin sees. Read-only; the numbers come
// from /api/admin/data-health (the store's rows joined with the registry, no network on the
// server side). English-only, like the rest of /admin.
import { useEffect, useState } from "react";
import {
  fetchDataHealth, fetchDataHealthHistory,
  type DataHealth, type DataHealthHistory, type DataHealthSource, type SourceState,
} from "../../lib/api";
import { STATE_ORDER, sortSources } from "../../lib/dataHealth";
import { formatDay } from "../../lib/format";

const stateCls: Record<SourceState, string> = {
  alarm: "text-state-negative border-state-negative/30 bg-state-negative/10",
  error: "text-state-negative border-state-negative/30 bg-state-negative/10",
  warn: "text-state-warning border-state-warning/30 bg-state-warning/10",
  acked: "text-state-warning border-state-warning/30 bg-state-warning/10",
  unknown: "text-text-muted border-border-subtle bg-transparent",
  ok: "text-state-positive border-state-positive/30 bg-state-positive/10",
  frozen_ok: "text-state-positive border-state-positive/30 bg-state-positive/10",
};
const stripCls: Record<SourceState, string> = {
  alarm: "bg-state-negative",
  error: "bg-state-negative",
  warn: "bg-state-warning",
  acked: "bg-state-warning",
  unknown: "bg-text-muted/40",
  ok: "bg-state-positive",
  frozen_ok: "bg-state-positive",
};
const STATE_LABEL: Record<SourceState, string> = {
  alarm: "alarm", error: "error", warn: "warn", unknown: "unknown", acked: "acked", ok: "ok", frozen_ok: "frozen",
};

function hoursAgo(h: number | null): string {
  if (h == null) return "never";
  return h < 1 ? "under an hour ago" : `${h.toFixed(h < 10 ? 1 : 0)} h ago`;
}

function ageText(s: DataHealthSource): string {
  if (s.age_days == null) return "—";
  const tol =
    s.alarm_days != null ? `alarm after ${s.alarm_days}` : s.warn_days != null ? `warn after ${s.warn_days}` : null;
  return tol ? `${s.age_days} d (${tol})` : `${s.age_days} d`;
}

function dateText(s: DataHealthSource): string {
  if (!s.as_of) return "—";
  return `${formatDay(s.as_of)}${s.basis ? ` · ${s.basis === "content" ? "data" : "publisher"}` : ""}`;
}

function HistoryStrip({ source }: { source: string }) {
  const [h, setH] = useState<DataHealthHistory | null | undefined>(undefined);
  useEffect(() => {
    fetchDataHealthHistory(source).then(setH);
  }, [source]);
  if (h === undefined) return <p className="text-caption text-text-muted">Loading history…</p>;
  if (h === null || h.history.length === 0) {
    return <p className="text-caption text-text-muted" data-testid="dh-history-empty">No history yet.</p>;
  }
  return (
    <div data-testid="dh-history">
      <div className="flex gap-px h-4 items-stretch">
        {h.history.map((p) => (
          <span
            key={p.checked_at}
            title={`${formatDay(p.checked_at)}: ${STATE_LABEL[p.state]}${p.reason ? ` — ${p.reason}` : ""}`}
            className={`flex-1 min-w-[3px] max-w-[10px] rounded-sm ${stripCls[p.state]}`}
          />
        ))}
      </div>
      <p className="text-caption text-text-muted mt-1">Last 90 days, one mark per check.</p>
    </div>
  );
}

function Counts({ counts }: { counts: DataHealth["counts"] }) {
  const entries = STATE_ORDER.filter((s) => (counts[s] ?? 0) > 0);
  return (
    <div className="flex flex-wrap gap-2" data-testid="dh-counts">
      {entries.map((s) => (
        <span key={s} className={`text-caption rounded-md border px-2 py-0.5 ${stateCls[s]}`} data-testid={`dh-count-${s}`}>
          {counts[s]} {STATE_LABEL[s]}
        </span>
      ))}
    </div>
  );
}

export function DataHealthSection() {
  const [data, setData] = useState<DataHealth | null | undefined>(undefined);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    fetchDataHealth().then(setData);
  }, []);

  if (data === undefined) return <p className="text-caption text-text-muted">Loading…</p>;
  if (data === null) return <p className="text-caption text-text-muted">Data health isn't available right now.</p>;

  const { checker } = data;
  const late = checker.state === "late";
  const rows = sortSources(data.sources);
  return (
    <div className="space-y-3" data-testid="data-health">
      {late && (
        <div
          className="rounded-md border border-state-negative/30 bg-state-negative/10 text-state-negative text-caption px-3 py-2"
          data-testid="dh-late"
        >
          {checker.last_run
            ? `The daily check hasn't finished in over ${checker.late_after_h} hours (last run ${hoursAgo(checker.age_h)}). The rows below are from that run.`
            : "The daily check has never finished, or its store can't be read."}
          {checker.last_error ? ` Last error: ${checker.last_error}` : ""}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Counts counts={data.counts} />
        <span className="text-caption text-text-muted" data-testid="dh-last-run">
          Last run {hoursAgo(checker.age_h)}
          {checker.next_run ? ` · next ${formatDay(checker.next_run)} 05:37 UTC` : ""}
        </span>
      </div>
      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-caption border-collapse" data-testid="dh-table">
            <thead>
              <tr className="text-left text-text-muted">
                {["Source", "State", "Data date", "Age (tolerance)", "Structure", "Ack", "Surfaces"].map((h) => (
                  <th key={h} className="font-medium border-b border-border-subtle px-2 py-1 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <SourceRow key={s.id} s={s} open={open === s.id} onToggle={() => setOpen(open === s.id ? null : s.id)} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SourceRow({ s, open, onToggle }: { s: DataHealthSource; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr
        className="border-b border-border-subtle/50 align-top cursor-pointer hover:bg-dark-elevated/40"
        onClick={onToggle}
        data-testid={`dh-row-${s.id}`}
        aria-expanded={open}
      >
        <td className="px-2 py-1">
          <span className="text-text-primary">
            {s.severity === "critical" && <span title="Critical source" aria-label="critical" className="text-state-warning mr-1">★</span>}
            {s.name}
          </span>
          <span className="block text-text-muted">{s.id}</span>
        </td>
        <td className="px-2 py-1 whitespace-nowrap">
          <span className={`rounded-md border px-1.5 py-0.5 ${stateCls[s.state]}`} data-testid={`dh-state-${s.id}`}>
            {STATE_LABEL[s.state]}
          </span>
        </td>
        <td className="px-2 py-1 whitespace-nowrap text-text-secondary">{dateText(s)}</td>
        <td className="px-2 py-1 whitespace-nowrap text-text-secondary">{ageText(s)}</td>
        <td className="px-2 py-1 whitespace-nowrap text-text-secondary">{s.contract ? "checked" : "—"}</td>
        <td className="px-2 py-1 text-text-secondary" data-testid={`dh-ack-${s.id}`}>
          {s.ack ? (
            <span title={s.ack.reason}>
              until {formatDay(s.ack.until)} ({s.ack.owner}): {s.ack.reason}
            </span>
          ) : (
            "—"
          )}
        </td>
        <td className="px-2 py-1 text-text-secondary">{s.surfaces.join(", ") || "—"}</td>
      </tr>
      {open && (
        <tr className="border-b border-border-subtle/50" data-testid={`dh-detail-${s.id}`}>
          <td colSpan={7} className="px-2 py-2 space-y-2">
            {s.reason && <p className="text-text-secondary break-words">{s.reason}</p>}
            <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-0.5 text-text-muted">
              <div>Publisher: {s.publisher ?? "—"}</div>
              <div>In state since: {s.state_since ? formatDay(s.state_since) : "—"}</div>
              <div>Owner: {s.owner_modules.join(", ") || "—"}</div>
              <div>Last checked: {s.checked_at ? formatDay(s.checked_at) : "never"}</div>
              {s.frozen && <div>Frozen: {s.frozen}</div>}
              {s.link && (
                <div>
                  <a href={s.link} target="_blank" rel="noopener noreferrer" className="text-text-primary underline hover:text-accent">
                    Open at the publisher
                  </a>
                </div>
              )}
            </dl>
            {s.note && <p className="text-text-muted">{s.note}</p>}
            <HistoryStrip source={s.id} />
          </td>
        </tr>
      )}
    </>
  );
}
