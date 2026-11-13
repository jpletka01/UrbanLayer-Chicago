// Settings in the new UI (owner-approved design B, 2026-11-13): one section at a time, each at its own address
// (/settings/<id>). Pure: which sections exist for this visitor, and which one an address opens.

export type SectionId = "account" | "plan" | "signin" | "preferences" | "things" | "reports" | "delete";

export const SECTION_ORDER: readonly SectionId[] = ["account", "plan", "signin", "preferences", "things", "reports", "delete"];

/** The sections this visitor has. Signed out (with sign-in on): Preferences only. Reports only when the account
    bought one with the old $25 purchase. Sign-in methods only when sign-in is on (development has none). */
export function sectionsFor({ signedIn, authRequired, hasReports }: {
  signedIn: boolean;
  authRequired: boolean;
  hasReports: boolean;
}): SectionId[] {
  if (authRequired && !signedIn) return ["preferences"];
  return SECTION_ORDER.filter((s) => {
    if (s === "reports") return hasReports;
    if (s === "signin") return authRequired;
    if (s === "delete") return authRequired;
    return true;
  });
}

/** The section an address opens: the one named when this visitor has it, else the first. */
export function sectionFrom(param: string | undefined, sections: SectionId[]): SectionId {
  return param && (sections as string[]).includes(param) ? (param as SectionId) : sections[0];
}

/** Share of the month's questions used, 0–1; null when there is no limit (admin) or nothing to show. */
export function usedShare(used: number, limit: number | null): number | null {
  if (limit == null || limit <= 0) return null;
  return Math.max(0, Math.min(1, used / limit));
}
