import type { DataHealthSource, SourceState } from "./api";

// Worst first. Both alarm and error are red; the critical ones lead each state.
export const STATE_ORDER: SourceState[] = ["alarm", "error", "warn", "unknown", "acked", "ok", "frozen_ok"];

export function sortSources(rows: DataHealthSource[]): DataHealthSource[] {
  const rank = (s: SourceState) => {
    const i = STATE_ORDER.indexOf(s);
    return i < 0 ? STATE_ORDER.length : i;
  };
  return [...rows].sort(
    (a, b) =>
      rank(a.state) - rank(b.state) ||
      Number(b.severity === "critical") - Number(a.severity === "critical") ||
      a.id.localeCompare(b.id),
  );
}
