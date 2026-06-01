// Shared display formatters.

/** Format an ISO date string as e.g. "Jan 5, 2026". Falls back to the raw string. */
export function formatDate(iso: string): string {
  if (!iso) return "";
  const t = new Date(iso);
  if (isNaN(t.getTime())) return iso;
  return t.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
