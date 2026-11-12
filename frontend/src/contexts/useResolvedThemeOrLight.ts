import { useContext } from "react";
import { ThemeContext } from "./themeContextObject";

/** The resolved theme, or light outside a provider (component tests render pages without one). */
export function useResolvedThemeOrLight(): "light" | "dark" {
  return useContext(ThemeContext)?.resolvedTheme === "dark" ? "dark" : "light";
}
