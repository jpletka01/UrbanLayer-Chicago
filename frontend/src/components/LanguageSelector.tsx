import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
] as const;

interface LanguageSelectorProps {
  variant?: "splash" | "workspace";
}

export default function LanguageSelector({ variant = "workspace" }: LanguageSelectorProps) {
  const { i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  function select(code: string) {
    i18n.changeLanguage(code);
    localStorage.setItem("urbanlayer-language", code);
    setOpen(false);
  }

  const current = LANGUAGES.find((l) => l.code === i18n.language) ?? LANGUAGES[0];
  const isSplash = variant === "splash";

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-caption font-medium transition-colors ${
          isSplash
            ? "text-text-secondary hover:text-text-primary hover:bg-white/5"
            : "text-text-muted hover:text-text-secondary hover:bg-dark-hover"
        }`}
        title="Language"
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M2 12h20" />
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
        {current.label}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 w-36 bg-dark-elevated border border-dark-border rounded-xl shadow-lg py-1 z-50">
          {LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              onClick={() => select(lang.code)}
              className={`w-full text-left px-3 py-1.5 text-body transition-colors ${
                lang.code === i18n.language
                  ? "text-accent bg-accent/5"
                  : "text-text-secondary hover:bg-dark-hover hover:text-text-primary"
              }`}
            >
              {lang.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
