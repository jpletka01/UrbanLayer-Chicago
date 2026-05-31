export type ArrestFilterValue = "all" | "arrested" | "not-arrested";

interface Props {
  value: ArrestFilterValue;
  onChange: (value: ArrestFilterValue) => void;
  arrestCount: number;
  totalCount: number;
}

const OPTIONS: { value: ArrestFilterValue; label: (ac: number, tc: number) => string }[] = [
  { value: "all", label: (_ac, tc) => `All (${tc})` },
  { value: "arrested", label: (ac) => `Arrested (${ac})` },
  { value: "not-arrested", label: (ac, tc) => `No Arrest (${tc - ac})` },
];

export function ArrestFilter({ value, onChange, arrestCount, totalCount }: Props) {
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
          {opt.label(arrestCount, totalCount)}
        </button>
      ))}
    </div>
  );
}
