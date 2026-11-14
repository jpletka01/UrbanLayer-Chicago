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
  alarm: "text-nx-pill-red border-nx-pill-red/30 bg-nx-pill-red/10",
  error: "text-nx-pill-red border-nx-pill-red/30 bg-nx-pill-red/10",
  warn: "text-nx-pill-yellow border-nx-pill-yellow/30 bg-nx-pill-yellow/10",
  acked: "text-nx-pill-yellow border-nx-pill-yellow/30 bg-nx-pill-yellow/10",
  unknown: "nx-muted border-nx-ink/10 bg-transparent",
  ok: "text-nx-pill-green border-nx-pill-green/30 bg-nx-pill-green/10",
  frozen_ok: "text-nx-pill-green border-nx-pill-green/30 bg-nx-pill-green/10",
};
const stripCls: Record<SourceState, string> = {
  alarm: "bg-nx-pill-red",
  error: "bg-nx-pill-red",
  warn: "bg-nx-pill-yellow",
  acked: "bg-nx-pill-yellow",
  unknown: "bg-nx-ink/30",
  ok: "bg-nx-pill-green",
  frozen_ok: "bg-nx-pill-green",
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
  if (h === undefined) return <p className="text-caption nx-muted">Loading history…</p>;
  if (h === null || h.history.length === 0) {
    return <p className="text-caption nx-muted" data-testid="dh-history-empty">No history yet.</p>;
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
      <p className="text-caption nx-muted mt-1">Last 90 days, one mark per check.</p>
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

/** What a source's daily contract checks, in a few words ("12 fields · 1 value set · count band"). */
function contractSummary(c: DataHealthSource["contract"]): string {
  if (!c) return "—";
  const parts = [
    c.required_fields.length ? `${c.required_fields.length} fields` : null,
    c.values?.length ? `${c.values.length} value set${c.values.length > 1 ? "s" : ""}` : null,
    c.count_band ? "count band" : null,
    c.layer_name ? "layer name" : null,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "checked";
}

function contractTitle(c: DataHealthSource["contract"]): string | undefined {
  if (!c) return undefined;
  return [
    c.layer_name ? `Layer name: ${c.layer_name}` : null,
    c.required_fields.length ? `Fields read: ${c.required_fields.join(", ")}` : null,
    c.values?.length ? `Value sets: ${c.values.join(", ")}` : null,
    c.count_band ? `Count band: ${c.count_band[0]}–${c.count_band[1]}` : null,
  ].filter(Boolean).join("\n") || undefined;
}

export function DataHealthSection() {
  const [data, setData] = useState<DataHealth | null | undefined>(undefined);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    fetchDataHealth().then(setData);
  }, []);

  if (data === undefined) return <p className="text-caption nx-muted">Loading…</p>;
  if (data === null) return <p className="text-caption nx-muted">Data health isn't available right now.</p>;

  const { checker } = data;
  const late = checker.state === "late";
  const rows = sortSources(data.sources);
  return (
    <div className="space-y-3" data-testid="data-health">
      {late && (
        <div
          className="rounded-md border border-nx-pill-red/30 bg-nx-pill-red/10 text-nx-pill-red text-caption px-3 py-2"
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
        <span className="text-caption nx-muted" data-testid="dh-last-run">
          Last run {hoursAgo(checker.age_h)}
          {checker.next_run ? ` · next ${formatDay(checker.next_run)} 05:37 UTC` : ""}
        </span>
      </div>
      {rows.length > 0 && (
        <div tabIndex={0} className="overflow-x-auto">
          <table className="w-full text-caption border-collapse" data-testid="dh-table">
            <thead>
              <tr className="text-left nx-muted">
                {["Source", "State", "Data date", "Age (tolerance)", "Structure", "Ack", "Surfaces"].map((h) => (
                  <th key={h} className="font-medium border-b border-nx-ink/10 px-2 py-1 whitespace-nowrap">{h}</th>
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
        className="border-b border-nx-ink/5 align-top cursor-pointer hover:bg-nx-ink/5"
        onClick={onToggle}
        data-testid={`dh-row-${s.id}`}
        aria-expanded={open}
      >
        <td className="px-2 py-1">
          <span className="text-nx-ink">
            {s.severity === "critical" && <span title="Critical source" aria-label="critical" className="text-nx-pill-yellow mr-1">★</span>}
            {s.name}
          </span>
          <span className="block nx-muted">{s.id}</span>
        </td>
        <td className="px-2 py-1 whitespace-nowrap">
          <span className={`rounded-md border px-1.5 py-0.5 ${stateCls[s.state]}`} data-testid={`dh-state-${s.id}`}>
            {STATE_LABEL[s.state]}
          </span>
        </td>
        <td className="px-2 py-1 whitespace-nowrap nx-muted">{dateText(s)}</td>
        <td className="px-2 py-1 whitespace-nowrap nx-muted">{ageText(s)}</td>
        <td className="px-2 py-1 whitespace-nowrap nx-muted" title={contractTitle(s.contract)}>{contractSummary(s.contract)}</td>
        <td className="px-2 py-1 nx-muted" data-testid={`dh-ack-${s.id}`}>
          {s.ack ? (
            <span title={s.ack.reason}>
              until {formatDay(s.ack.until)} ({s.ack.owner}): {s.ack.reason}
            </span>
          ) : (
            "—"
          )}
        </td>
        <td className="px-2 py-1 nx-muted">{s.surfaces.join(", ") || "—"}</td>
      </tr>
      {open && (
        <tr className="border-b border-nx-ink/5" data-testid={`dh-detail-${s.id}`}>
          <td colSpan={7} className="px-2 py-2 space-y-2">
            {s.reason && <p className="nx-muted break-words">{s.reason}</p>}
            <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-0.5 nx-muted">
              <div>Publisher: {s.publisher ?? "—"}</div>
              <div>In state since: {s.state_since ? formatDay(s.state_since) : "—"}</div>
              <div>Owner: {s.owner_modules.join(", ") || "—"}</div>
              <div>Last checked: {s.checked_at ? formatDay(s.checked_at) : "never"}</div>
              {s.frozen && <div>Frozen: {s.frozen}</div>}
              {s.link && (
                <div>
                  <a href={s.link} target="_blank" rel="noopener noreferrer" className="text-nx-ink underline hover:underline">
                    Open at the publisher
                  </a>
                </div>
              )}
            </dl>
            {s.note && <p className="nx-muted">{s.note}</p>}
            <HistoryStrip source={s.id} />
          </td>
        </tr>
      )}
    </>
  );
}
