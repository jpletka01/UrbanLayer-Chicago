import { useState, useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { getAutocomplete } from "../lib/api";
import { AUTOCOMPLETE_DEBOUNCE_MS, MIN_AUTOCOMPLETE_CHARS } from "../lib/constants";
import type { AddressSuggestion } from "../lib/types";

export interface PendingAttachment {
  file: File;
  previewUrl: string | null;
}

interface Props {
  onSubmit: (message: string) => void;
  disabled?: boolean;
  variant?: "hero" | "compact";
  placeholder?: string;
  attachments?: PendingAttachment[];
  onAttach?: (files: File[]) => void;
  onRemoveAttachment?: (index: number) => void;
}

function findAddressFragment(text: string): { start: number; fragment: string } | null {
  const match = text.match(/\d+\D*$/);
  if (!match) return null;
  const start = match.index!;
  const fragment = text.slice(start);
  return fragment.length >= MIN_AUTOCOMPLETE_CHARS ? { start, fragment } : null;
}

export function ChatInput({
  onSubmit,
  disabled,
  variant = "hero",
  placeholder,
  attachments = [],
  onAttach,
  onRemoveAttachment,
}: Props) {
  const { t } = useTranslation("chat");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState("");
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const addressStartRef = useRef(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    const addr = findAddressFragment(value);
    if (!addr) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    addressStartRef.current = addr.start;

    debounceRef.current = setTimeout(async () => {
      const results = await getAutocomplete(addr.fragment);
      setSuggestions(results);
      setShowSuggestions(results.length > 0);
      setSelectedIndex(-1);
    }, AUTOCOMPLETE_DEBOUNCE_MS);

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

  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = el.scrollHeight + "px";
    }
  }, [value]);

  function doSubmit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
    setSuggestions([]);
    setShowSuggestions(false);
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    doSubmit();
  }

  function selectSuggestion(suggestion: AddressSuggestion) {
    const prefix = value.slice(0, addressStartRef.current);
    setValue(prefix + suggestion.address);
    setSuggestions([]);
    setShowSuggestions(false);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
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
        selectSuggestion(suggestions[selectedIndex]);
        return;
      } else if (e.key === "Escape") {
        setShowSuggestions(false);
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      doSubmit();
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
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
            disabled={disabled}
            placeholder={placeholder ?? t("placeholder")}
            rows={1}
            className="w-full bg-transparent px-4 py-3.5 pr-12 rounded-2xl text-base text-white placeholder-white/50 focus:outline-none resize-none max-h-40 overflow-y-auto"
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
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept="image/jpeg,image/png,image/webp,application/pdf"
        className="hidden"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length > 0 && onAttach) onAttach(files);
          e.target.value = "";
        }}
      />
      <div className="rounded-2xl bg-dark-surface border border-dark-border focus-within:border-accent/50 transition-all duration-200">
        {attachments.length > 0 && (
          <div className="flex gap-2 px-3 pt-2 pb-1 overflow-x-auto">
            {attachments.map((att, i) => (
              <div key={i} className="relative shrink-0 w-14 h-14 rounded-lg overflow-hidden border border-dark-border bg-dark-elevated group">
                {att.previewUrl ? (
                  <img src={att.previewUrl} alt={att.file.name} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center gap-0.5">
                    <svg className="w-5 h-5 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                    <span className="text-[8px] text-text-muted truncate max-w-[3rem] px-0.5">
                      {att.file.name.split(".").pop()?.toUpperCase()}
                    </span>
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => onRemoveAttachment?.(i)}
                  className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-dark-bg border border-dark-border flex items-center justify-center text-text-muted hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
        <form onSubmit={submit} className="flex items-center gap-2 p-2">
          {onAttach && (
            <button
              type="button"
              className="w-8 h-8 rounded-lg flex items-center justify-center text-text-muted hover:text-text-secondary hover:bg-dark-elevated transition-colors shrink-0"
              aria-label="Add attachment"
              onClick={() => fileInputRef.current?.click()}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13"
                />
              </svg>
            </button>
          )}

          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
            disabled={disabled}
            placeholder={placeholder ?? t("placeholder")}
            rows={1}
            className="flex-1 bg-transparent py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none min-w-0 resize-none max-h-40 overflow-y-auto"
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
