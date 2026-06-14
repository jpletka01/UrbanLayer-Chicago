// Search client (08): compile panel state into a SearchRequest envelope and POST it.
// The envelope carries raw inputs (userFilters + topicId + text + sort + scope) — the
// backend compiles, merges, evaluates, and echoes back the canonical CQS.

import { discoverySearch, discoverySearchPins } from "../lib/api";
import { compilePanel } from "./uiCompiler";
import type {
  PanelState,
  PinsResponse,
  Registry,
  SearchRequest,
  SearchResponse,
  SortSpec,
  SpatialScope,
} from "./types";

export interface SearchInputs {
  panelState: PanelState;
  topicId?: string | null;
  text?: string | null;
  sort?: SortSpec | null;
  scope?: SpatialScope | null;
  offset?: number; // infinite-scroll window start (omitted = page 0)
  limit?: number; // window size (omitted = server default)
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
  if (inputs.offset != null) req.offset = inputs.offset;
  if (inputs.limit != null) req.limit = inputs.limit;
  return req;
}

export async function runSearch(
  inputs: SearchInputs,
  registry: Registry,
): Promise<SearchResponse | null> {
  return discoverySearch(buildRequest(inputs, registry));
}

/** Fetch the full ordered coord set for the map. Same buildRequest envelope as runSearch
 * (so the backend's shared _resolve yields a sequence-identical ordering). */
export async function runPins(
  inputs: SearchInputs,
  registry: Registry,
): Promise<PinsResponse | null> {
  return discoverySearchPins(buildRequest(inputs, registry));
}
