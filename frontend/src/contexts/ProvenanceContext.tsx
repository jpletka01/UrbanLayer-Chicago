import type { ReactNode } from "react";
import type { Provenance } from "../lib/api";
import { EMPTY_PROVENANCE, ProvenanceContext } from "../lib/provenanceContext";

export function ProvenanceProvider({ value, children }: {
  value: Record<string, Provenance> | null | undefined;
  children: ReactNode;
}) {
  return <ProvenanceContext.Provider value={value ?? EMPTY_PROVENANCE}>{children}</ProvenanceContext.Provider>;
}
