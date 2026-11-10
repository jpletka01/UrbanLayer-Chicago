// Search client (08): compile panel state into a SearchRequest envelope and POST it.
// The envelope carries raw inputs (userFilters + topicId + text + sort + scope) — the
// backend compiles, merges, evaluates, and echoes back the canonical CQS.

import type { DiscoveryOutlineLookup } from "../lib/api";
import { discoveryExportCsv, discoveryOutlineRow, discoveryParcelRow, discoverySearch, discoverySearchPins, discoveryTextPreview } from "../lib/api";
import { compilePanel } from "./uiCompiler";
import type {
  PanelState,
  PinsResponse,
  Registry,
  ResultRow,
  SearchRequest,
  SearchResponse,
  SortSpec,
  SpatialScope,
  TextPreview,
} from "./types";

export interface SearchInputs {
  panelState: PanelState;
  topicId?: string | null;
  text?: string | null;
  sort?: SortSpec | null;
  scope?: SpatialScope | null;
  offset?: number; // infinite-scroll window start (omitted = page 0)
  limit?: number; // window size (omitted = server default)
  includePins?: boolean; // ask for the map's points in the same response (one evaluation)
  includeUnusual?: boolean; // opt in to the parcels the default `hide_unusual` filter keeps out (Item 60)
  includeAreaCounts?: boolean; // matches per community area from the same evaluation (Item 104)
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
  if (inputs.includePins) req.includePins = true;
  if (inputs.includeUnusual) req.includeUnusual = true;
  if (inputs.includeAreaCounts) req.includeAreaCounts = true;
  return req;
}

export async function runSearch(
  inputs: SearchInputs,
  registry: Registry,
  signal?: AbortSignal,
): Promise<SearchResponse | null> {
  return discoverySearch(buildRequest(inputs, registry), signal);
}

/** Fetch the full ordered coord set for the map. Same buildRequest envelope as runSearch
 * (so the backend's shared _resolve yields a sequence-identical ordering). The page asks
 * runSearch for the points with `includePins` instead; this separate request is the fallback
 * for a backend that does not return them. */
export async function runPins(
  inputs: SearchInputs,
  registry: Registry,
  signal?: AbortSignal,
): Promise<PinsResponse | null> {
  return discoverySearchPins(buildRequest(inputs, registry), signal);
}

/** What the text compiler makes of a phrase, without searching (null if it could not be asked). */
export async function previewText(text: string, signal?: AbortSignal): Promise<TextPreview | null> {
  return discoveryTextPreview(text, signal);
}

/** Download the full match set as CSV (server-side, premium-gated). Same envelope, so the
 * export is exactly what was filtered, in the same order. */
export async function exportCsv(inputs: SearchInputs, registry: Registry): Promise<boolean> {
  return discoveryExportCsv(buildRequest(inputs, registry));
}

/** One row by PIN for the dot preview (decision Item 57); the active sort key picks the row's sort figure. */
export async function fetchParcelRow(pin: string, sortKey: string, signal?: AbortSignal): Promise<ResultRow | null> {
  return discoveryParcelRow(pin, sortKey, signal);
}

/** The lot behind a map outline, by its PIN10 (Item 68): found, missing from the index, or failed. */
export async function fetchOutlineRow(pin10: string, sortKey: string, signal?: AbortSignal): Promise<OutlineLookup> {
  return discoveryOutlineRow(pin10, sortKey, signal);
}

export type OutlineLookup = DiscoveryOutlineLookup;
