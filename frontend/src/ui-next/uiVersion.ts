// Which UI a visitor sees: today's ("old") or the rewrite's preview ("next") (decision Items 75–76).
//
// `?ui=next` turns the preview on and `?ui=old` turns it off; either is remembered in a versioned
// localStorage flag, so in-app links don't need to carry the parameter. The parameter is then removed
// from the address bar (replace, not push), so a copied link never forces the preview on someone else
// and Back never lands on a URL that flips the version again. A build-time switch (VITE_UI_PREVIEW=off)
// turns the preview off for everyone, whatever the URL or the flag say. Storage can fail (private mode,
// blocked site data): then the choice lasts for this page's session only, and nothing throws.

export type UiVersion = "old" | "next";

/** Bump the suffix to forget every stored choice (for example when the preview is reset). */
export const UI_FLAG_KEY = "urbanlayer-ui-preview:v1";
export const UI_PARAM = "ui";

/** The build-time kill switch: "off" disables the preview entirely. Read once, from the env. */
export function previewEnabled(env: { VITE_UI_PREVIEW?: string } = import.meta.env as { VITE_UI_PREVIEW?: string }): boolean {
  return (env.VITE_UI_PREVIEW ?? "").trim().toLowerCase() !== "off";
}

/** The version a `?ui=` value asks for, or null when the URL says nothing usable. */
export function versionFromParam(search: string): UiVersion | null {
  const value = new URLSearchParams(search).get(UI_PARAM)?.trim().toLowerCase();
  return value === "next" || value === "old" ? value : null;
}

export function readStoredVersion(storage: Pick<Storage, "getItem"> | null = safeLocalStorage()): UiVersion | null {
  try {
    const value = storage?.getItem(UI_FLAG_KEY);
    return value === "next" || value === "old" ? value : null;
  } catch {
    return null;
  }
}

/** Remember the choice. Returns false when storage refused it (the choice still holds in memory). */
export function writeStoredVersion(version: UiVersion, storage: Pick<Storage, "setItem" | "removeItem"> | null = safeLocalStorage()): boolean {
  try {
    if (!storage) return false;
    // "old" is the default, so it is stored as the absence of a flag.
    if (version === "old") storage.removeItem(UI_FLAG_KEY);
    else storage.setItem(UI_FLAG_KEY, version);
    return true;
  } catch {
    return false;
  }
}

/** The search string without the `ui` parameter ("" when nothing else is left). */
export function withoutUiParam(search: string): string {
  const params = new URLSearchParams(search);
  if (!params.has(UI_PARAM)) return search;
  params.delete(UI_PARAM);
  const rest = params.toString();
  return rest ? `?${rest}` : "";
}

/** The version for this load: the kill switch wins, then the URL, then the stored flag, then "old". */
export function resolveUiVersion({
  search,
  stored,
  enabled,
}: {
  search: string;
  stored: UiVersion | null;
  enabled: boolean;
}): UiVersion {
  if (!enabled) return "old";
  return versionFromParam(search) ?? stored ?? "old";
}

function safeLocalStorage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}
