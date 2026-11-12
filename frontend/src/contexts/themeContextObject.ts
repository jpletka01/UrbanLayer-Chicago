import { createContext } from "react";
import type { UseTheme } from "../lib/useTheme";

/** The theme context object, in its own file so hooks beside the provider don't break fast refresh. */
export const ThemeContext = createContext<UseTheme | null>(null);
