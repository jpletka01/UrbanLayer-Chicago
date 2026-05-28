interface Props {
  isOpen: boolean;
  onToggle: () => void;
  sourceCount?: number;
}

export function SidebarToggle({ isOpen, onToggle, sourceCount = 0 }: Props) {
  return (
    <button
      onClick={onToggle}
      className={`hidden md:flex absolute top-4 right-4 z-30
                 px-3 py-2 rounded-lg
                 items-center gap-2
                 transition-all duration-200
                 ${isOpen
                   ? "bg-accent/20 border border-accent/30 text-accent"
                   : "bg-dark-surface/80 border border-dark-border text-text-secondary hover:text-text-primary hover:bg-dark-elevated hover:border-dark-border/80"
                 }`}
      aria-label={isOpen ? "Close sources panel" : "Open sources panel"}
    >
      <svg
        className="w-4 h-4"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
        />
      </svg>
      <span className="text-xs font-medium">Sources</span>
      {sourceCount > 0 && (
        <span className={`min-w-[1.25rem] h-5 px-1.5 rounded-full text-xs font-medium flex items-center justify-center
                         ${isOpen
                           ? "bg-accent/30 text-accent"
                           : "bg-accent/20 text-accent"
                         }`}>
          {sourceCount}
        </span>
      )}
    </button>
  );
}
