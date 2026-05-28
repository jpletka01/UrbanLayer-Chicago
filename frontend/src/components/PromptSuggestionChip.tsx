interface Props {
  label: string;
  onClick: () => void;
}

export function PromptSuggestionChip({ label, onClick }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="px-4 py-2 text-sm font-medium rounded-full bg-white/10 hover:bg-white/20 border border-white/10 hover:border-white/20 text-white shadow-sm transition-all duration-150"
    >
      {label}
    </button>
  );
}
