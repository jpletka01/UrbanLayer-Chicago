// What the lot is used for today, from Discovery's own row for it (decision Item 112): surface parking or empty land,
// measured from what stands on the lot. Asked only for an exact match (a nearest parcel may be a neighbor's); a
// failed or missing row shows nothing, never "not parking".
import { useEffect, useState } from "react";
import type { ResultRow } from "../../discovery/types";
import { fetchParcelRow } from "../../discovery/searchClient";

export type LotInUseRow = Pick<ResultRow, "surface_parking" | "empty_land" | "land_kind" | "structure">;

export function useLotInUse(pin10: string | null): LotInUseRow | null {
  const [row, setRow] = useState<{ pin10: string; row: LotInUseRow | null } | null>(null);
  useEffect(() => {
    if (!pin10) return;
    const controller = new AbortController();
    fetchParcelRow(pin10, "lot_size", controller.signal)
      .then((r) => setRow({ pin10, row: r }))
      .catch(() => { if (!controller.signal.aborted) setRow({ pin10, row: null }); });
    return () => controller.abort();
  }, [pin10]);
  return pin10 && row?.pin10 === pin10 ? row.row : null;
}
