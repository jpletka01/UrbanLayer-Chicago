import type { ContextObject } from "./types";

/** How many data categories a turn's context filled — drives the sidebar Data
 *  badge and the per-message chip strip. */
export function countDataCategories(ctx: ContextObject | null): number {
  if (!ctx) return 0;
  let count = 0;
  if (ctx.crime_last_90d) count++;
  if (ctx.open_311_requests) count++;
  if (ctx.permits) count++;
  if (ctx.violations) count++;
  if (ctx.businesses) count++;
  if (ctx.parcel_zoning) count++;
  if (ctx.regulatory) count++;
  if (ctx.property) count++;
  if (ctx.incentives) count++;
  if (ctx.neighborhood) count++;
  return count;
}
