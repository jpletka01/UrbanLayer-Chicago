interface Props {
  isOpen: boolean;
  onToggle: () => void;
}

export function SidebarToggle({ isOpen, onToggle }: Props) {
  return (
    <button
      onClick={onToggle}
      className="absolute top-1/2 -translate-y-1/2 -left-3 z-20
                 w-6 h-6 rounded-full bg-dark-surface border border-dark-border
                 flex items-center justify-center
                 hover:bg-dark-elevated transition-all duration-200
                 shadow-lg"
      aria-label={isOpen ? "Close sidebar" : "Open sidebar"}
    >
      <svg
        className={`w-3.5 h-3.5 text-text-secondary transition-transform duration-300
                    ${isOpen ? "" : "rotate-180"}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
      </svg>
    </button>
  );
}
