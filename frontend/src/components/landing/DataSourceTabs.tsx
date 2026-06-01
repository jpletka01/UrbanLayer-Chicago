export type LandingSource = "all" | "crime" | "311" | "permits";

const TABS: { key: LandingSource; label: string }[] = [
  { key: "all", label: "All" },
  { key: "crime", label: "Crime" },
  { key: "311", label: "311" },
  { key: "permits", label: "Permits" },
];

interface Props {
  active: LandingSource;
  onChange: (s: LandingSource) => void;
}

export function DataSourceTabs({ active, onChange }: Props) {
  return (
    <div className="flex gap-2">
      {TABS.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors ${
            active === t.key
              ? "bg-accent text-white"
              : "bg-dark-elevated text-text-secondary hover:text-text-primary hover:bg-dark-border"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
