import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import { fetchScorecard, type ScorecardResponse } from "../lib/api";
import type { SelectedParcel, ParcelQuery } from "../lib/types";

export interface SelectedParcelState {
  parcel: SelectedParcel | null;
  select: (query: ParcelQuery) => Promise<ScorecardResponse | null>;
}

const SelectedParcelContext = createContext<SelectedParcelState | null>(null);

export function SelectedParcelProvider({ children }: { children: ReactNode }) {
  const [parcel, setParcel] = useState<SelectedParcel | null>(null);

  // The only SelectedParcel write in the codebase. Identity fields come
  // exclusively from the backend resolver's response — never from the query.
  const select = useCallback(async (query: ParcelQuery): Promise<ScorecardResponse | null> => {
    const result = await fetchScorecard(query);
    if (result) {
      setParcel({
        pin: result.resolved_pin,
        confidence: result.resolved_confidence,
        lat: result.resolved_lat,
        lon: result.resolved_lon,
        address: result.address,
      });
    }
    return result;
  }, []);

  return (
    <SelectedParcelContext.Provider value={{ parcel, select }}>
      {children}
    </SelectedParcelContext.Provider>
  );
}

export function useSelectedParcel(): SelectedParcelState {
  const ctx = useContext(SelectedParcelContext);
  if (!ctx) throw new Error("useSelectedParcel must be used within SelectedParcelProvider");
  return ctx;
}
