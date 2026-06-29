// 3-state theme control (light / dark / system) — guides/light-dark-theming.md.
// A compact segmented pill of icon radios. Lives in the page/workspace/splash headers.
import { useTranslation } from "react-i18next";
import { useThemeContext } from "../contexts/ThemeContext";
import type { ThemePref } from "../lib/useTheme";

const Icon = ({ d }: { d: string }) => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d={d} />
  </svg>
);

// Heroicons-style outline glyphs: sun, moon, monitor.
const ICONS: Record<ThemePref, string> = {
  light:
    "M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z",
  dark: "M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z",
  system:
    "M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25A2.25 2.25 0 015.25 3h13.5A2.25 2.25 0 0121 5.25z",
};

const ORDER: ThemePref[] = ["light", "dark", "system"];

export default function ThemeToggle({ className = "" }: { className?: string }) {
  const { t } = useTranslation("common");
  const { theme, setTheme } = useThemeContext();

  return (
    <div
      role="radiogroup"
      aria-label={t("theme.label")}
      className={`inline-flex items-center gap-0.5 rounded-full border border-dark-border bg-dark-elevated p-0.5 ${className}`}
    >
      {ORDER.map((opt) => {
        const active = theme === opt;
        const label = t(`theme.${opt}`);
        return (
          <button
            key={opt}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            title={label}
            onClick={() => setTheme(opt)}
            className={`flex items-center justify-center w-6 h-6 rounded-full transition-colors ${
              active
                ? "bg-dark-hover text-text-primary"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            <Icon d={ICONS[opt]} />
          </button>
        );
      })}
    </div>
  );
}
