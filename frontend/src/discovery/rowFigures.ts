// A Discovery row's title and figures (decision Items 46, 57), shared by the result list and the dot preview.
import { titleCaseAddress } from "../lib/format";
import type { ResultRow } from "./types";

/** The row's address, title-cased; a "~" prefix (nearest address on record) becomes an "Approx." label. */
export function rowTitle(row: ResultRow): { title: string; approx: boolean } {
  if (!row.address) return { title: row.pin, approx: false };
  const approx = row.address.startsWith("~");
  return { title: titleCaseAddress(approx ? row.address.slice(1) : row.address), approx };
}

/** The address a Profile link may carry beside the PIN, or null. Only an Address Point address: the Profile searches
    the City's permits and violations by it, and an approximate ("~") or Assessor address (Item 109) can be the house
    next door, whose records would read as this lot's. The PIN alone still opens the right lot. */
export function profileAddress(row: ResultRow): string | null {
  const { title, approx } = rowTitle(row);
  return row.address && !approx && row.address_source !== "assessor" ? title : null;
}
