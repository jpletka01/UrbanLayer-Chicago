import { useState, useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { getAutocomplete } from "../lib/api";
import { AUTOCOMPLETE_DEBOUNCE_MS, MIN_AUTOCOMPLETE_CHARS } from "../lib/constants";
import type { AddressSuggestion } from "../lib/types";

interface Props {
  onSubmit: (address: string) => void;
  placeholder: string;
  /** "hero" = over-image homepage styling (white chrome); "page" = token-backed
   *  themeable styling for in-app pages (Scorecard). */
  variant?: "hero" | "page";
  /** md = full search field; sm = compact re-search bar. Hero is always md. */
  size?: "md" | "sm";
  /** Initial text (e.g. a failed query the user should correct). */
  defaultValue?: string;
  /** Disables submit while a lookup is in flight. */
  busy?: boolean;
}

// Per-variant chrome. Hero keeps the original over-image styling verbatim; page
// maps every piece onto theme tokens so it flips with light/dark.
const CHROME = {
  hero: {
    formIdle: "bg-transparent border border-white/20 hover:border-white/30",
    formActive: "bg-dark-surface/80 backdrop-blur-md border border-dark-border shadow-xl",
    icon: "text-white/50",
    input: "text-white placeholder-white/50",
    submitIdle: "bg-white/10 hover:bg-white/20 text-white/70",
    submitActive: "bg-action hover:bg-action-hover text-white",
    suggestionActive: "bg-accent/20 text-white",
    suggestionIdle: "text-text-secondary hover:bg-dark-elevated hover:text-white",
  },
  page: {
    formIdle: "bg-dark-surface border border-dark-border hover:border-dark-border-strong",
    formActive: "bg-dark-surface border border-dark-border-strong shadow-card",
    icon: "text-text-muted",
    input: "text-text-primary placeholder:text-text-muted",
    submitIdle: "bg-dark-elevated hover:bg-dark-hover text-text-secondary",
    submitActive: "bg-action hover:bg-action-hover text-text-on-accent",
    suggestionActive: "bg-accent/15 text-text-primary",
    suggestionIdle: "text-text-secondary hover:bg-dark-elevated hover:text-text-primary",
  },
} as const;

// Size steps: radius, paddings, icon slot. sm is the compact "search another" bar.
const SIZING = {
  md: { form: "rounded-2xl", input: "pl-12 pr-12 py-3.5 text-base rounded-2xl", icon: "left-4 w-5 h-5", button: "right-2 w-8 h-8" },
  sm: { form: "rounded-xl", input: "pl-10 pr-11 py-2 text-body rounded-xl", icon: "left-3.5 w-4 h-4", button: "right-1.5 w-7 h-7" },
} as const;

/**
 * Address search input — shared between the homepage hero and the Scorecard page
 * so search looks and behaves the same everywhere: whole-value autocomplete
 * (300ms debounce), suggestion select submits immediately, free-text Enter
 * submits too (backend resolves it server-side).
 */
export function AddressInput({ onSubmit, placeholder, variant = "hero", size = "md", defaultValue, busy = false }: Props) {
  const { t } = useTranslation("common");
  const [value, setValue] = useState(defaultValue ?? "");
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const chrome = CHROME[variant];
  const sizing = SIZING[variant === "hero" ? "md" : size];

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
        className={`relative transition-all duration-300 ${sizing.form} ${isActive ? chrome.formActive : chrome.formIdle}`}
      >
        <svg
          className={`absolute top-1/2 -translate-y-1/2 pointer-events-none ${sizing.icon} ${chrome.icon}`}
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
          className={`w-full bg-transparent focus:outline-none ${sizing.input} ${chrome.input}`}
        />
        <button
          type="submit"
          disabled={!value.trim() || busy}
          className={`absolute top-1/2 -translate-y-1/2 rounded-lg flex items-center justify-center transition-all duration-300 ${sizing.button} ${
            isActive ? chrome.submitActive : chrome.submitIdle
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
                index === selectedIndex ? chrome.suggestionActive : chrome.suggestionIdle
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
