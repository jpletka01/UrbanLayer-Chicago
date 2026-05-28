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

  return (
    <form
      onSubmit={submit}
      className={`relative w-full mx-auto shadow-2xl rounded-full backdrop-blur-md transition-all duration-300 ${
        isHero
          ? "max-w-2xl bg-white/10 border border-white/20 focus-within:bg-white/15 focus-within:border-white/30"
          : "max-w-3xl bg-white border border-slate-200 focus-within:border-sky-300"
      }`}
    >
      <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
        <svg
          className={`h-5 w-5 ${isHero ? "text-white/60" : "text-slate-400"}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
      </div>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        disabled={disabled}
        placeholder={placeholder ?? "What do you need help with in Chicago?"}
        className={`w-full bg-transparent pl-12 pr-14 py-4 rounded-full text-lg focus:outline-none focus:ring-0 border-0 ${
          isHero
            ? "text-white placeholder-white/60"
            : "text-slate-900 placeholder-slate-400"
        }`}
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className={`absolute right-2 top-2 bottom-2 w-10 h-10 rounded-full flex items-center justify-center font-bold shadow-md transition-colors ${
          isHero
            ? "bg-white text-slate-900 hover:bg-slate-100 disabled:bg-white/40"
            : "bg-sky-600 text-white hover:bg-sky-700 disabled:bg-slate-300"
        }`}
        aria-label="Submit"
      >
        →
      </button>
    </form>
  );
}
