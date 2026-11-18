// Pure wording for the corrections queue (decision Item 129, PR 4): what a report says, and what Accept applies by
// default. Kept out of the component file so the queue's tests can import them.
import type { AdminCorrection } from "../../lib/api";

/** What the reporter says, in words: "Stories: 20", "Floor area too high", "No building now" / "It's a condo" by what
 * the card showed (the two building and the two condo chips share a kind; the snapshot says which way). */
export function reportWords(r: Pick<AdminCorrection, "kinds" | "stories" | "area_dir" | "shown" | "now">): string[] {
  // The snapshot says what the card showed (reports sent before it carried these fall back to the index today).
  const structure = r.shown.structure !== undefined ? r.shown.structure : r.now?.structure;
  const condo = r.shown.condo !== undefined ? r.shown.condo : r.now?.condo;
  const hadBuilding = structure !== "empty";
  return r.kinds.map((k) => {
    if (k === "stories") return `Stories: ${r.stories ?? "?"}`;
    if (k === "area") return `Floor area too ${r.area_dir ?? "?"}`;
    if (k === "gone") return hadBuilding ? "No building now" : "There's a building";
    if (k === "condo") return condo ? "Not a condo" : "It's a condo";
    return "Other";
  });
}

/** What Accept applies by default: the reporter's story count, no building for "no building now", else stories for the
 * reviewer to type (floor area: a direction alone can't make a number), or nothing for a condo or "other" report. */
export function defaultApply(r: Pick<AdminCorrection, "kinds" | "stories">): { apply: "stories" | "empty" | "none"; stories: string } {
  if (r.kinds.includes("stories") && r.stories) return { apply: "stories", stories: String(r.stories) };
  if (r.kinds.includes("gone")) return { apply: "empty", stories: "" };
  if (r.kinds.includes("area")) return { apply: "stories", stories: "" };
  return { apply: "none", stories: "" };
}
