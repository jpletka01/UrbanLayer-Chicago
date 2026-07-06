import { useThemeContext } from "../contexts/ThemeContext";

interface Props {
  label: string;
  onClick: () => void;
}

export function PromptSuggestionChip({ label, onClick }: Props) {
  const light = useThemeContext().resolvedTheme === "light";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-2 text-sm font-medium rounded-lg border transition-all duration-150 ${
        light
          ? "bg-dark-surface hover:bg-dark-elevated border-dark-border hover:border-dark-border-strong text-text-primary"
          : "bg-white/10 hover:bg-white/20 border-white/20 hover:border-white/30 text-white"
      }`}
    >
      {label}
    </button>
  );
}
