import { createContext, useContext, type ReactNode } from "react";
import { type UseTheme, useTheme } from "../lib/useTheme";

const ThemeContext = createContext<UseTheme | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const theme = useTheme();
  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>;
}

export function useThemeContext(): UseTheme {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useThemeContext must be used within ThemeProvider");
  return ctx;
}
