// Search client (08): compile panel state into a SearchRequest envelope and POST it.
// The envelope carries raw inputs (userFilters + topicId + text + sort + scope) — the
// backend compiles, merges, evaluates, and echoes back the canonical CQS.

import { discoverySearch } from "../lib/api";
import { compilePanel } from "./uiCompiler";
import type { PanelState, Registry, SearchRequest, SearchResponse, SortSpec, SpatialScope } from "./types";

export interface SearchInputs {
  panelState: PanelState;
  topicId?: string | null;
  text?: string | null;
  sort?: SortSpec | null;
  scope?: SpatialScope | null;
}

/** Build the wire envelope. `userFilters` is the compiled panel (cleared controls dropped). */
export function buildRequest(inputs: SearchInputs, registry: Registry): SearchRequest {
  const req: SearchRequest = {
    userFilters: compilePanel(inputs.panelState),
    registryVersion: registry.version,
  };
  if (inputs.topicId) req.topicId = inputs.topicId;
  if (inputs.text && inputs.text.trim()) req.text = inputs.text.trim();
  if (inputs.sort) req.sort = inputs.sort;
  if (inputs.scope && inputs.scope.mode !== "all") req.scope = inputs.scope;
  return req;
}

export async function runSearch(
  inputs: SearchInputs,
  registry: Registry,
): Promise<SearchResponse | null> {
  return discoverySearch(buildRequest(inputs, registry));
}
