// "Code currency": how old the Municipal Code text is, whether the daily check of the
// City Clerk's list of passed amendments is running, and which amendments passed after
// the text's vintage are still unreviewed. Read-only; the numbers come from
// /api/admin/code-currency (no network on the server side). English-only, like the rest of /admin.
import { useEffect, useState } from "react";
import { fetchAdminCodeCurrency, type AdminCodeCurrency } from "../../lib/api";
import { amendmentStatus, formatDay } from "../../lib/format";
import { RecordLink } from "../scorecard/AmendmentList";

const statusCls = {
  green: "text-state-positive border-state-positive/30 bg-state-positive/10",
  amber: "text-state-warning border-state-warning/30 bg-state-warning/10",
  red: "text-state-negative border-state-negative/30 bg-state-negative/10",
} as const;

const STATUS_LABEL = { applied: "applied", none: "no effect", pending: "not reviewed" } as const;

function Stat({ label, value, testId }: { label: string; value: string | number; testId?: string }) {
  return (
    <div className="flex justify-between gap-3 text-caption">
      <dt className="text-text-muted">{label}</dt>
      <dd className="text-text-primary" data-testid={testId}>{value}</dd>
    </div>
  );
}

export function CodeCurrencySection() {
  const [data, setData] = useState<AdminCodeCurrency | null | undefined>(undefined);

  useEffect(() => {
    fetchAdminCodeCurrency().then(setData);
  }, []);

  if (data === undefined) return <p className="text-caption text-text-muted">Loading…</p>;
  if (data === null) return <p className="text-caption text-text-muted">Code currency isn't available right now.</p>;

  const { code, clerk, amendments, map_lag: lagRez } = data;
  const lag = code.lag;
  const unknown = code.check_state === "unknown";
  return (
    <div className="space-y-4" data-testid="code-currency">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`text-caption rounded-md border px-2 py-0.5 ${statusCls[code.status]}`} data-testid="code-status">
          {code.status}
        </span>
        {code.reasons.map((r) => (
          <span key={r} className="text-caption text-text-secondary">{r}</span>
        ))}
      </div>
      <div className="grid md:grid-cols-2 gap-x-10 gap-y-4">
        <dl className="space-y-1">
          <Stat label="Code text current through" value={code.as_of ? formatDay(code.as_of) : "unknown"} />
          <Stat label="Age" value={code.age_days != null ? `${code.age_days} days` : "unknown"} />
          <Stat label="Ingested" value={code.ingested_at ? formatDay(code.ingested_at) : "unknown"} />
          <Stat
            label="Title 17 amendments since"
            value={unknown || lag.title17_passed_since == null ? "unknown (no fresh check)" : lag.title17_passed_since}
            testId="code-title17"
          />
          <Stat label="Unreviewed" value={lag.unreviewed} />
          <Stat label="Oldest unreviewed" value={lag.oldest_unreviewed_days != null ? `${lag.oldest_unreviewed_days} days` : "none"} />
          <Stat label="Applied ahead of codification" value={lag.uncodified_applied} />
        </dl>
        <dl className="space-y-1">
          <Stat label="Clerk check state" value={code.check_state} />
          <Stat label="Last successful check" value={clerk.last_success ? formatDay(clerk.last_success) : "never"} />
          <Stat label="Consecutive failures" value={clerk.consecutive_failures} />
          <Stat label="Snapshot" value={clerk.snapshot_state} />
          <Stat label="Contract" value={clerk.contract_ok ? "ok" : "problems"} />
          {clerk.last_error && <p className="text-caption text-state-negative break-words">{clerk.last_error}</p>}
          {clerk.contract_problems.map((p) => (
            <p key={p} className="text-caption text-state-warning break-words">{p}</p>
          ))}
        </dl>
      </div>
      {lagRez && (
        <dl className="space-y-1 max-w-xl" data-testid="map-lag">
          <Stat label="Passed rezonings not on the City's map" value={lagRez.passed_not_on_map ?? "unknown (never checked)"} testId="map-lag-count" />
          <Stat label="Oldest waiting" value={lagRez.oldest_days != null ? `${lagRez.oldest_days} days` : "none"} />
          <Stat label="Shown on the Profile (parcels found)" value={lagRez.with_parcels ?? "unknown"} />
          <Stat label="Titles the parser can't place" value={lagRez.unparsed_titles ?? "unknown"} />
          <Stat label="Clean titles with no address point" value={lagRez.no_parcels.length} />
          <Stat label="Rezoning check" value={lagRez.check_status} />
          {lagRez.unparsed.length > 0 && (
            <p className="text-caption text-text-secondary break-words">Map by hand in rezoning_overrides.json: {lagRez.unparsed.join(", ")}</p>
          )}
          {lagRez.last_error && <p className="text-caption text-state-negative break-words">{lagRez.last_error}</p>}
        </dl>
      )}
      {amendments.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-caption border-collapse" data-testid="code-amendments-table">
            <thead>
              <tr className="text-left text-text-muted">
                <th className="font-medium border-b border-border-subtle px-2 py-1">Passed</th>
                <th className="font-medium border-b border-border-subtle px-2 py-1">Record</th>
                <th className="font-medium border-b border-border-subtle px-2 py-1">Scope</th>
                <th className="font-medium border-b border-border-subtle px-2 py-1">Review</th>
                <th className="font-medium border-b border-border-subtle px-2 py-1">Summary / title</th>
              </tr>
            </thead>
            <tbody>
              {amendments.map((a) => (
                <tr key={a.record} className="border-b border-border-subtle/50 last:border-b-0 align-top">
                  <td className="px-2 py-1 whitespace-nowrap text-text-secondary">{formatDay(a.passed_on)}</td>
                  <td className="px-2 py-1 whitespace-nowrap"><RecordLink a={a} /></td>
                  <td className="px-2 py-1 text-text-secondary">{a.relevance === "title17" ? "Title 17" : "cited"}</td>
                  <td className="px-2 py-1 whitespace-nowrap text-text-secondary">{STATUS_LABEL[amendmentStatus(a)]}</td>
                  <td className="px-2 py-1 text-text-secondary">{a.summary || a.title}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
