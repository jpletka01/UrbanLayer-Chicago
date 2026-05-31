import { useState } from "react";
import type { RequestLogEntry } from "../../lib/types";

interface Props {
  rows: RequestLogEntry[];
  onLoadMore: () => void;
  hasMore: boolean;
}

function formatTime(ms: number): string {
  const d = new Date(ms);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms}ms`;
}

const INTENT_COLORS: Record<string, string> = {
  neighborhood_overview: "bg-blue-500/15 text-blue-400",
  legal_question: "bg-purple-500/15 text-purple-400",
  trend_analysis: "bg-teal-500/15 text-teal-400",
  incident_lookup: "bg-amber-500/15 text-amber-400",
  clarification_needed: "bg-gray-500/15 text-gray-400",
  event_query: "bg-emerald-500/15 text-emerald-400",
};

export function RequestsTable({ rows, onLoadMore, hasMore }: Props) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  if (rows.length === 0) {
    return (
      <div className="text-text-muted text-sm text-center py-8">
        No requests yet. Make some chat queries and they'll appear here.
      </div>
    );
  }

  return (
    <div>
      <table className="w-full text-[12px]">
        <thead>
          <tr className="text-text-muted uppercase tracking-wider text-[10px]">
            <th className="text-left py-2 font-medium">Time</th>
            <th className="text-left py-2 font-medium">Message</th>
            <th className="text-left py-2 font-medium">Intent</th>
            <th className="text-left py-2 font-medium">Area</th>
            <th className="text-right py-2 font-medium">Duration</th>
            <th className="text-center py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              className="border-t border-dark-border hover:bg-dark-elevated/50 cursor-pointer transition-colors"
              onClick={() =>
                setExpandedId(expandedId === row.id ? null : row.id)
              }
            >
              <td className="py-2 text-text-muted whitespace-nowrap">
                {formatTime(row.created_at)}
              </td>
              <td className="py-2 text-text-secondary max-w-[200px] truncate">
                {row.user_message}
              </td>
              <td className="py-2">
                {row.intent && (
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] ${
                      INTENT_COLORS[row.intent] ?? "bg-gray-500/15 text-gray-400"
                    }`}
                  >
                    {row.intent.replace(/_/g, " ")}
                  </span>
                )}
              </td>
              <td className="py-2 text-text-muted truncate max-w-[100px]">
                {row.community_area_name ?? "-"}
              </td>
              <td className="py-2 text-right font-mono text-text-primary">
                {formatDuration(row.total_duration_ms)}
              </td>
              <td className="py-2 text-center">
                <span
                  className={`inline-block w-2 h-2 rounded-full ${
                    row.status === "ok" ? "bg-emerald-400" : "bg-rose-400"
                  }`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Expanded detail row */}
      {expandedId !== null && (() => {
        const row = rows.find((r) => r.id === expandedId);
        if (!row) return null;
        return (
          <div className="bg-dark-elevated border border-dark-border rounded-lg p-4 mt-2 mb-2 text-xs">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="text-text-muted">Full message: </span>
                <span className="text-text-secondary">{row.user_message}</span>
              </div>
              <div>
                <span className="text-text-muted">Sources: </span>
                <span className="text-text-secondary">
                  {row.sources.join(", ") || "none"}
                </span>
              </div>
              {row.error_message && (
                <div className="col-span-2">
                  <span className="text-text-muted">Error: </span>
                  <span className="text-rose-400">{row.error_message}</span>
                </div>
              )}
              <div>
                <span className="text-text-muted">Request group: </span>
                <span className="text-text-secondary font-mono">
                  {row.request_group.slice(0, 8)}
                </span>
              </div>
            </div>
          </div>
        );
      })()}

      {hasMore && (
        <div className="text-center py-3">
          <button
            onClick={onLoadMore}
            className="text-xs text-accent hover:text-accent-hover transition-colors"
          >
            Load more
          </button>
        </div>
      )}
    </div>
  );
}
