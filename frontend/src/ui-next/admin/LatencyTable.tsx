import type { LatencyPercentiles } from "../../lib/types";

interface Props {
  rows: LatencyPercentiles[];
}

const PHASE_LABELS: Record<string, string> = {
  conversation: "Conversation",
  router: "Router",
  synthesizer: "Synthesizer",
};

function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms}ms`;
}

function msColor(ms: number): string {
  if (ms >= 5000) return "text-nx-pill-red";
  if (ms >= 2000) return "text-nx-pill-yellow";
  return "text-nx-ink";
}

export function LatencyTable({ rows }: Props) {
  if (rows.length === 0) {
    return (
      <div className="nx-muted text-body text-center py-4">
        No latency data yet
      </div>
    );
  }

  return (
    <table className="w-full text-micro">
      <thead>
        <tr className="nx-muted uppercase tracking-wider">
          <th className="text-left py-2 font-medium">Phase</th>
          <th className="text-right py-2 font-medium">p50</th>
          <th className="text-right py-2 font-medium">p90</th>
          <th className="text-right py-2 font-medium">p99</th>
          <th className="text-right py-2 font-medium">Calls</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            key={row.phase}
            className="border-t border-nx-ink/10"
          >
            <td className="py-2 nx-muted">
              {PHASE_LABELS[row.phase] ?? row.phase}
            </td>
            <td className={`py-2 text-right font-mono ${msColor(row.p50_ms)}`}>
              {formatMs(row.p50_ms)}
            </td>
            <td className={`py-2 text-right font-mono ${msColor(row.p90_ms)}`}>
              {formatMs(row.p90_ms)}
            </td>
            <td className={`py-2 text-right font-mono ${msColor(row.p99_ms)}`}>
              {formatMs(row.p99_ms)}
            </td>
            <td className="py-2 text-right font-mono nx-muted">
              {row.count.toLocaleString()}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
