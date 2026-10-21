// The Profile's provenance map, shared down the tree so a card can ask for its figure's entry
// (`useFact("property.stories")`) instead of threading the whole map through every prop list.
// Outside a provider (chat rail, tests) every lookup is undefined, so no caption renders and
// nothing else changes. The provider lives in contexts/ProvenanceContext.tsx.
import { createContext, useContext } from "react";
import type { Provenance } from "./api";

export const EMPTY_PROVENANCE: Record<string, Provenance> = {};
export const ProvenanceContext = createContext<Record<string, Provenance>>(EMPTY_PROVENANCE);

export function useFact(id: string): Provenance | undefined {
  return useContext(ProvenanceContext)[id];
}
