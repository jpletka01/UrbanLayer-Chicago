import { useState, type FormEvent } from "react";

interface Props {
  onSubmit: (message: string) => void;
  disabled?: boolean;
  variant?: "hero" | "compact";
  placeholder?: string;
}

export function ChatInput({ onSubmit, disabled, variant = "hero", placeholder }: Props) {
  const [value, setValue] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
  }

  const isHero = variant === "hero";
  const isActive = value.length > 0;

  if (isHero) {
    return (
      <form
        onSubmit={submit}
        className={`relative w-full max-w-2xl mx-auto rounded-2xl transition-all duration-300 ${
          isActive
            ? "bg-dark-surface/80 backdrop-blur-md border border-dark-border shadow-xl"
            : "bg-transparent border border-white/20 hover:border-white/30"
        }`}
      >
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          disabled={disabled}
          placeholder={placeholder ?? "Ask about Chicago..."}
          className="w-full bg-transparent px-4 py-3.5 pr-12 rounded-2xl text-base text-white placeholder-white/50 focus:outline-none"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className={`absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-300 ${
            isActive
              ? "bg-accent hover:bg-accent-hover text-white"
              : "bg-white/10 hover:bg-white/20 text-white/70"
          } disabled:opacity-30`}
          aria-label="Submit"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
          </svg>
        </button>
      </form>
    );
  }

  return (
    <div className="rounded-2xl bg-dark-surface border border-dark-border focus-within:border-accent/50 transition-all duration-200">
      <form onSubmit={submit} className="flex items-center gap-2 p-2">
        <button
          type="button"
          className="w-8 h-8 rounded-lg flex items-center justify-center text-text-muted hover:text-text-secondary hover:bg-dark-elevated transition-colors shrink-0"
          aria-label="Add attachment"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13"
            />
          </svg>
        </button>

        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          disabled={disabled}
          placeholder={placeholder ?? "Ask a follow-up..."}
          className="flex-1 bg-transparent py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none min-w-0"
        />

        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors bg-accent hover:bg-accent-hover disabled:bg-dark-elevated disabled:text-text-muted text-white shrink-0"
          aria-label="Submit"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
          </svg>
        </button>
      </form>
    </div>
  );
}
