// The UI-version context and its hook, apart from the provider so the provider file only exports a component.
import { createContext, useContext } from "react";
import type { UiVersion } from "./uiVersion";

export interface UiVersionValue {
  version: UiVersion;
  /** False when the build turned the preview off. */
  enabled: boolean;
  setVersion: (v: UiVersion) => void;
}

export const UiVersionContext = createContext<UiVersionValue>({ version: "old", enabled: false, setVersion: () => {} });

export function useUiVersion(): UiVersionValue {
  return useContext(UiVersionContext);
}
