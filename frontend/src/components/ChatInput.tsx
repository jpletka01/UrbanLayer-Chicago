import { useState, useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";
import { getAutocomplete } from "../lib/api";
import type { AddressSuggestion } from "../lib/types";

interface Props {
  onSubmit: (message: string) => void;
  disabled?: boolean;
  variant?: "hero" | "compact";
  placeholder?: string;
}

export function ChatInput({ onSubmit, disabled, variant = "hero", placeholder }: Props) {
  const [value, setValue] = useState("");
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (value.length < 3) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      const results = await getAutocomplete(value);
      setSuggestions(results);
      setShowSuggestions(results.length > 0);
      setSelectedIndex(-1);
    }, 300);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [value]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function submit(e: FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
    setSuggestions([]);
    setShowSuggestions(false);
  }

  function selectSuggestion(suggestion: AddressSuggestion) {
    setValue(suggestion.address);
    setSuggestions([]);
    setShowSuggestions(false);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (!showSuggestions || suggestions.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : prev));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
    } else if (e.key === "Enter" && selectedIndex >= 0) {
      e.preventDefault();
      selectSuggestion(suggestions[selectedIndex]);
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
    }
  }

  const isHero = variant === "hero";
  const isActive = value.length > 0;

  if (isHero) {
    return (
      <div ref={containerRef} className="relative w-full max-w-2xl mx-auto">
        <form
          onSubmit={submit}
          className={`relative rounded-2xl transition-all duration-300 ${
            isActive
              ? "bg-dark-surface/80 backdrop-blur-md border border-dark-border shadow-xl"
              : "bg-transparent border border-white/20 hover:border-white/30"
          }`}
        >
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
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

        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute z-50 w-full mt-2 rounded-xl bg-dark-surface/95 backdrop-blur-md border border-dark-border shadow-xl overflow-hidden">
            {suggestions.map((suggestion, index) => (
              <button
                key={suggestion.address}
                type="button"
                onClick={() => selectSuggestion(suggestion)}
                className={`w-full px-4 py-3 text-left text-sm transition-colors ${
                  index === selectedIndex
                    ? "bg-accent/20 text-white"
                    : "text-text-secondary hover:bg-dark-elevated hover:text-white"
                }`}
              >
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-text-muted shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
                  </svg>
                  {suggestion.address}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative">
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
            onKeyDown={handleKeyDown}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
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

      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-50 w-full mt-2 rounded-xl bg-dark-surface/95 backdrop-blur-md border border-dark-border shadow-xl overflow-hidden">
          {suggestions.map((suggestion, index) => (
            <button
              key={suggestion.address}
              type="button"
              onClick={() => selectSuggestion(suggestion)}
              className={`w-full px-4 py-2.5 text-left text-sm transition-colors ${
                index === selectedIndex
                  ? "bg-accent/20 text-white"
                  : "text-text-secondary hover:bg-dark-elevated hover:text-white"
              }`}
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4 text-text-muted shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
                </svg>
                {suggestion.address}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
