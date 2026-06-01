// Building-permit cost filter values + bucketing. Rendered via the shared
// <ToggleGroup> in MapView.
export type CostFilterValue = "all" | "under25k" | "25k-250k" | "over250k";

export function costBucket(cost: number): CostFilterValue {
  if (cost < 25_000) return "under25k";
  if (cost <= 250_000) return "25k-250k";
  return "over250k";
}
