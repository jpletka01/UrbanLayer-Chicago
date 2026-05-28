interface Props {
  label: string;
  onClick: () => void;
}

export function PromptSuggestionChip({ label, onClick }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="px-3 py-2 text-sm font-medium rounded-lg bg-white/10 hover:bg-white/20 border border-white/20 hover:border-white/30 text-white transition-all duration-150"
    >
      {label}
    </button>
  );
}
