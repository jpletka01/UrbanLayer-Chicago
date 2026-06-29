// Theme state hook (light/dark/system) — guides/light-dark-theming.md.
// Owns the preference + the resolved theme, writes `data-theme` on <html>, persists to
// localStorage (same convention as `urbanlayer-language`), and tracks OS changes while in
// `system` mode. The pre-paint script in index.html sets data-theme before first paint; this
// hook keeps it in sync afterward. Default preference is `system`, resolving to dark when
// unknown — preserving the dark look for empty-prefs users.
import { useCallback, useEffect, useState } from "react";

export type ThemePref = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export interface UseTheme {
  theme: ThemePref;
  resolvedTheme: ResolvedTheme;
  setTheme: (t: ThemePref) => void;
}

const STORAGE_KEY = "urbanlayer-theme";
// Mirrors the pre-paint backgrounds in index.html / index.css (--bg) so the address-bar
// chrome matches the page.
const THEME_COLORS: Record<ResolvedTheme, string> = { dark: "#0d0d0d", light: "#fafaf9" };

function systemDark(): boolean {
  return typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function readPref(): ThemePref {
  const v = (typeof localStorage !== "undefined" && localStorage.getItem(STORAGE_KEY)) || "system";
  return v === "light" || v === "dark" ? v : "system";
}

function resolve(pref: ThemePref): ResolvedTheme {
  if (pref === "system") return systemDark() ? "dark" : "light";
  return pref;
}

export function useTheme(): UseTheme {
  const [theme, setThemeState] = useState<ThemePref>(readPref);
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => resolve(readPref()));

  // Apply to <html> + the theme-color meta whenever the resolved theme changes.
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", resolvedTheme);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", THEME_COLORS[resolvedTheme]);
  }, [resolvedTheme]);

  // Follow OS changes live while preference is `system`.
  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setResolvedTheme(mq.matches ? "dark" : "light");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);

  const setTheme = useCallback((t: ThemePref) => {
    setThemeState(t);
    setResolvedTheme(resolve(t));
    try {
      localStorage.setItem(STORAGE_KEY, t);
    } catch {
      /* private mode / storage disabled — non-fatal */
    }
  }, []);

  return { theme, resolvedTheme, setTheme };
}
