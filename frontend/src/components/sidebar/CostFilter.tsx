export type CostFilterValue = "all" | "under25k" | "25k-250k" | "over250k";

interface Props {
  value: CostFilterValue;
  onChange: (value: CostFilterValue) => void;
  counts: Record<CostFilterValue, number>;
}

const OPTIONS: { value: CostFilterValue; label: string }[] = [
  { value: "all", label: "All" },
  { value: "under25k", label: "<$25K" },
  { value: "25k-250k", label: "$25K–$250K" },
  { value: "over250k", label: ">$250K" },
];

export function costBucket(cost: number): CostFilterValue {
  if (cost < 25_000) return "under25k";
  if (cost <= 250_000) return "25k-250k";
  return "over250k";
}

export function CostFilter({ value, onChange, counts }: Props) {
  return (
    <div className="absolute top-2 left-2 z-10 flex bg-dark-surface/90 backdrop-blur-sm
                    rounded-md border border-dark-border shadow-sm overflow-hidden">
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`px-2 py-1 text-[11px] font-medium transition-colors duration-150
            ${value === opt.value
              ? "bg-dark-elevated text-text-primary"
              : "text-text-muted hover:text-text-secondary hover:bg-dark-surface/60"
            }
            ${opt.value !== "all" ? "border-l border-dark-border" : ""}`}
        >
          {opt.label} ({counts[opt.value]})
        </button>
      ))}
    </div>
  );
}
