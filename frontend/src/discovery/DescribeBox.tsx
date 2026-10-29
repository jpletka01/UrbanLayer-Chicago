// The free-text box and its Search button: one component, shown in the Start panel before the
// first search and in the results header after it. The text is a draft like any other control;
// Search or Enter applies it (and asks the compiler first, see useDiscoverySearch.apply).

import { useTranslation } from "react-i18next";

interface Props {
  value: string;
  onChange: (text: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
}

export function DescribeBox({ value, onChange, onSubmit, disabled = false }: Props) {
  const { t } = useTranslation("pages");
  return (
    <div className="flex items-center gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onSubmit();
        }}
        placeholder={t("discovery.searchPlaceholder")}
        aria-label={t("discovery.searchAria")}
        className="min-w-0 flex-1 rounded-lg border border-dark-border bg-dark-elevated px-3 py-2 text-body text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
      />
      <button
        type="button"
        onClick={onSubmit}
        disabled={disabled}
        className="flex-shrink-0 rounded-lg bg-action px-4 py-2 text-title text-text-on-accent transition-colors hover:bg-action-hover disabled:opacity-50"
      >
        {t("discovery.search")}
      </button>
    </div>
  );
}
