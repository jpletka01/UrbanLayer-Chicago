export type StatusFilterValue = "all" | "closed" | "open";

interface Props {
  value: StatusFilterValue;
  onChange: (value: StatusFilterValue) => void;
  closedCount: number;
  totalCount: number;
}

const OPTIONS: { value: StatusFilterValue; label: (cc: number, tc: number) => string }[] = [
  { value: "all", label: (_cc, tc) => `All (${tc})` },
  { value: "closed", label: (cc) => `Closed (${cc})` },
  { value: "open", label: (cc, tc) => `Open (${tc - cc})` },
];

export function StatusFilter({ value, onChange, closedCount, totalCount }: Props) {
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
          {opt.label(closedCount, totalCount)}
        </button>
      ))}
    </div>
  );
}
