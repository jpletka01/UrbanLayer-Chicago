import { useState, useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { getAutocomplete } from "../lib/api";
import { AUTOCOMPLETE_DEBOUNCE_MS, MIN_AUTOCOMPLETE_CHARS } from "../lib/constants";
import type { AddressSuggestion } from "../lib/types";

interface Props {
  onSubmit: (address: string) => void;
  placeholder: string;
}

/**
 * Hero address input: the whole value is an address, so autocomplete runs on
 * the full input (no fragment detection). Selecting a suggestion submits
 * immediately — the address IS the terminal action. Free-text Enter also
 * submits; the backend resolves it server-side.
 */
export function AddressInput({ onSubmit, placeholder }: Props) {
  const { t } = useTranslation("common");
  const [value, setValue] = useState("");
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (value.trim().length < MIN_AUTOCOMPLETE_CHARS) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      const results = await getAutocomplete(value.trim());
      setSuggestions(results);
      setShowSuggestions(results.length > 0);
      setSelectedIndex(-1);
    }, AUTOCOMPLETE_DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
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

  function doSubmit(address: string) {
    const trimmed = address.trim();
    if (!trimmed) return;
    setShowSuggestions(false);
    onSubmit(trimmed);
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    doSubmit(value);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (showSuggestions && suggestions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : prev));
        return;
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
        return;
      } else if (e.key === "Enter" && selectedIndex >= 0) {
        e.preventDefault();
        doSubmit(suggestions[selectedIndex].address);
        return;
      } else if (e.key === "Escape") {
        setShowSuggestions(false);
        return;
      }
    }
  }

  const isActive = value.length > 0;

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
        <svg
          className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/50 pointer-events-none"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
        </svg>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
          placeholder={placeholder}
          autoComplete="off"
          className="w-full bg-transparent pl-12 pr-12 py-3.5 rounded-2xl text-base text-white placeholder-white/50 focus:outline-none"
        />
        <button
          type="submit"
          disabled={!value.trim()}
          className={`absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-300 ${
            isActive
              ? "bg-action hover:bg-action-hover text-white"
              : "bg-white/10 hover:bg-white/20 text-white/70"
          } disabled:opacity-30`}
          aria-label={t("submit")}
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
              onClick={() => doSubmit(suggestion.address)}
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
