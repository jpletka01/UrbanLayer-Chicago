import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import { fetchScorecard, type ScorecardResponse } from "../lib/api";
import type { SelectedParcel, ParcelQuery } from "../lib/types";

export interface SelectedParcelState {
  parcel: SelectedParcel | null;
  // The full ScorecardResponse for the held parcel, retained so the chat
  // workspace can ship pre-resolved grounding (scorecard_context) on a handoff
  // without re-fetching. Identity-paired with `parcel`: same write, same pin.
  scorecard: ScorecardResponse | null;
  select: (query: ParcelQuery) => Promise<ScorecardResponse | null>;
}

const SelectedParcelContext = createContext<SelectedParcelState | null>(null);

export function SelectedParcelProvider({ children }: { children: ReactNode }) {
  const [parcel, setParcel] = useState<SelectedParcel | null>(null);
  const [scorecard, setScorecard] = useState<ScorecardResponse | null>(null);

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
      setScorecard(result);
    }
    return result;
  }, []);

  return (
    <SelectedParcelContext.Provider value={{ parcel, scorecard, select }}>
      {children}
    </SelectedParcelContext.Provider>
  );
}

export function useSelectedParcel(): SelectedParcelState {
  const ctx = useContext(SelectedParcelContext);
  if (!ctx) throw new Error("useSelectedParcel must be used within SelectedParcelProvider");
  return ctx;
}
