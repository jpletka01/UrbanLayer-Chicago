import { useTranslation } from "react-i18next";

export type LandingSource = "all" | "crime" | "311" | "permits";

const TAB_KEYS: LandingSource[] = ["all", "crime", "311", "permits"];

interface Props {
  active: LandingSource;
  onChange: (s: LandingSource) => void;
}

export function DataSourceTabs({ active, onChange }: Props) {
  const { t } = useTranslation("landing");

  return (
    <div className="flex gap-2">
      {TAB_KEYS.map((key) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors ${
            active === key
              ? "bg-accent text-white"
              : "bg-dark-elevated text-text-secondary hover:text-text-primary hover:bg-dark-border"
          }`}
        >
          {t(`explorer.${key}`)}
        </button>
      ))}
    </div>
  );
}
