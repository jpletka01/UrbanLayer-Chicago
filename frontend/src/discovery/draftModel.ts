// Draft model (Phase 0 of the Discovery redesign). Pure helpers over the two things the page
// holds: the DRAFT (what the user has asked for, edited freely) and the APPLIED query (the
// last response.cqs the server evaluated). Nothing here evaluates anything (INV-1/INV-3):
// the draft only drives controls, chips and the "Update results" button. The summary
// sentence, the count and the rows always come from the evaluated response (INV-4).

import { compilePanel } from "./uiCompiler";
import type { CQS, FilterId, PanelState, Predicate, SortSpec } from "./types";

export interface DiscoveryDraft {
  panelState: PanelState;
  text: string;
  sort: SortSpec | null;
  // Telemetry only; cleared the moment the user edits anything (see the hook).
  topicId: string | null;
}

/** applied = shown as evaluated; added/changed = pending in the draft; removed = evaluated
 *  filter the draft no longer has (shown struck through until applied, restorable). */
export type ChipState = "applied" | "added" | "changed" | "removed";

export interface ChipItem {
  id: FilterId;
  predicate: Predicate;
  state: ChipState;
}

/** Order-insensitive identity of a predicate. The server may sort enum values; a draft that
 *  lists them differently is still the same constraint. */
function predicateKey(p: Predicate): string {
  switch (p.kind) {
    case "enum":
      return `enum:${[...p.values].sort().join("|")}`;
    case "region":
      return `region:${[...p.regions].sort().join("|")}`;
    case "flag":
      return `flag:${p.value}`;
    case "range":
      return `range:${p.min ?? ""}:${p.max ?? ""}`;
  }
}

export function samePredicate(a: Predicate, b: Predicate): boolean {
  return predicateKey(a) === predicateKey(b);
}

/** Constraints the server derived from free text. They are not in the panel, so they are
 *  "carried" from the applied query for as long as the draft still has text. */
export function carriedFilters(cqs: CQS | null): Record<FilterId, Predicate> {
  const out: Record<FilterId, Predicate> = {};
  if (!cqs) return out;
  for (const [id, assignment] of Object.entries(cqs.filters)) {
    if (assignment.source !== "user") out[id] = assignment.predicate;
  }
  return out;
}

/** Every evaluated filter, any source, as plain predicates. */
export function appliedFilters(cqs: CQS | null): Record<FilterId, Predicate> {
  const out: Record<FilterId, Predicate> = {};
  if (!cqs) return out;
  for (const [id, assignment] of Object.entries(cqs.filters)) out[id] = assignment.predicate;
  return out;
}

/** The filters the draft would send: carried text constraints (while the draft keeps text)
 *  overridden by the panel's own controls. */
export function draftFilters(draft: DiscoveryDraft, applied: CQS | null): Record<FilterId, Predicate> {
  const out: Record<FilterId, Predicate> = {};
  if (draft.text.trim()) Object.assign(out, carriedFilters(applied));
  Object.assign(out, compilePanel(draft.panelState));
  return out;
}

export function sameSort(a: SortSpec | null | undefined, b: SortSpec | null | undefined): boolean {
  if (!a || !b) return !a && !b;
  return a.key === b.key && a.dir === b.dir;
}

export interface DraftDiff {
  chips: ChipItem[];
  /** Filter changes (added + changed + removed) plus a changed sort and changed text. */
  pendingCount: number;
}

/** Compare the draft with what the server last evaluated. `applied` null = nothing evaluated
 *  yet (no chips; the Search button is the only way to start). */
export function diffDraft(
  draft: DiscoveryDraft,
  applied: CQS | null,
  appliedText: string,
): DraftDiff {
  if (!applied) return { chips: [], pendingCount: 0 };
  const before = appliedFilters(applied);
  const after = draftFilters(draft, applied);
  const chips: ChipItem[] = [];
  let pending = 0;
  for (const id of [...new Set([...Object.keys(before), ...Object.keys(after)])].sort()) {
    const was = before[id];
    const now = after[id];
    if (now && !was) {
      chips.push({ id, predicate: now, state: "added" });
      pending++;
    } else if (now && was) {
      const same = samePredicate(now, was);
      chips.push({ id, predicate: now, state: same ? "applied" : "changed" });
      if (!same) pending++;
    } else if (was) {
      chips.push({ id, predicate: was, state: "removed" });
      pending++;
    }
  }
  // Non-empty text that differs from what was evaluated is one pending change (what it
  // will compile to is only known after the server answers). Emptying the text is already
  // counted above through the carried filters it takes away.
  if (draft.text.trim() && draft.text.trim() !== appliedText.trim()) pending++;
  if (draft.sort && !sameSort(draft.sort, applied.sort)) pending++;
  return { chips, pendingCount: pending };
}

/** Stable identity of a set of inputs, for "is this draft the search already in flight?". */
export function inputsSignature(inputs: {
  panelState: PanelState;
  text?: string | null;
  sort?: SortSpec | null;
}): string {
  const filters = compilePanel(inputs.panelState);
  const ids = Object.keys(filters).sort();
  return JSON.stringify({
    f: ids.map((id) => [id, predicateKey(filters[id])]),
    t: (inputs.text ?? "").trim(),
    s: inputs.sort ? [inputs.sort.key, inputs.sort.dir] : null,
  });
}

/** Remove one filter from the draft. A text-derived (carried) filter is not in the panel, so
 *  the first removal folds the evaluated query into the panel as plain user filters (the
 *  one-tap relax of the old chips) and drops the text those filters came from, unless the
 *  user has already typed new text. */
export function removeFromDraft(
  draft: DiscoveryDraft,
  applied: CQS | null,
  appliedText: string,
  id: FilterId,
): DiscoveryDraft {
  const panelState = { ...draft.panelState };
  const inPanel = id in panelState;
  if (inPanel) {
    delete panelState[id];
    return { ...draft, panelState, topicId: null };
  }
  // Carried: fold every carried filter into the panel, then drop this one.
  const carried = carriedFilters(applied);
  const folded: PanelState = { ...carried, ...panelState };
  delete folded[id];
  const textUnchanged = draft.text.trim() === appliedText.trim();
  return { ...draft, panelState: folded, text: textUnchanged ? "" : draft.text, topicId: null };
}

/** Put an evaluated filter back into the draft (undo of a struck-through chip). */
export function restoreToDraft(draft: DiscoveryDraft, applied: CQS | null, id: FilterId): DiscoveryDraft {
  const predicate = appliedFilters(applied)[id];
  if (!predicate) return draft;
  return { ...draft, panelState: { ...draft.panelState, [id]: predicate }, topicId: null };
}

/** After a response lands with no edits made while it was in flight, make the panel equal to
 *  the user-sourced filters the server actually evaluated (dropped/merged ones disappear). */
export function reconcileWithResponse(draft: DiscoveryDraft, cqs: CQS): DiscoveryDraft {
  const panelState: PanelState = {};
  for (const [id, assignment] of Object.entries(cqs.filters)) {
    if (assignment.source === "user") panelState[id] = assignment.predicate;
  }
  return { ...draft, panelState };
}
