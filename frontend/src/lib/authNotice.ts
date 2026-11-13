// What a sign-in or linking round trip came back with (Phase 9, Item 121). The server lands on the page the visitor
// started from with one of: ?signin_error=<code>, ?signin_hint=<provider>, ?link=<result>&provider=<provider>.
// Read once, then removed from the address bar so a reload or a shared link doesn't repeat it.
import type { SignInProviderId } from "./api";

/** Brand names, the same in every language. */
export const PROVIDER_NAMES: Record<SignInProviderId, string> = {
  google: "Google",
  apple: "Apple",
  microsoft: "Microsoft",
};

export type AuthNotice =
  | { kind: "error"; code: "declined" | "expired" | "failed" | "unavailable" | "session" }
  | { kind: "hint"; provider: SignInProviderId }
  | { kind: "link"; result: "linked" | "already_yours" | "taken" | "provider_exists"; provider: SignInProviderId };

const PROVIDERS = new Set(["google", "apple", "microsoft"]);
const ERRORS = new Set(["declined", "expired", "failed", "unavailable", "session"]);
const LINKS = new Set(["linked", "already_yours", "taken", "provider_exists"]);
const PARAMS = ["signin_error", "signin_hint", "link", "provider"];

/** Pure: the notice in a query string, or null (unknown values are ignored, never shown raw). */
export function parseAuthNotice(search: string): AuthNotice | null {
  const q = new URLSearchParams(search);
  const err = q.get("signin_error");
  if (err) return { kind: "error", code: (ERRORS.has(err) ? err : "failed") as Extract<AuthNotice, { kind: "error" }>["code"] };
  const hint = q.get("signin_hint");
  if (hint && PROVIDERS.has(hint)) return { kind: "hint", provider: hint as SignInProviderId };
  const link = q.get("link");
  const provider = q.get("provider");
  if (link && LINKS.has(link) && provider && PROVIDERS.has(provider)) {
    return { kind: "link", result: link as Extract<AuthNotice, { kind: "link" }>["result"], provider: provider as SignInProviderId };
  }
  return null;
}

/** Pure: the query string without the notice's parameters ("" when nothing is left). */
export function stripAuthNotice(search: string): string {
  const q = new URLSearchParams(search);
  PARAMS.forEach((p) => q.delete(p));
  const rest = q.toString();
  return rest ? `?${rest}` : "";
}

/** Reads the notice from the current address once and replaces the address without it. */
export function takeAuthNotice(): AuthNotice | null {
  if (typeof window === "undefined") return null;
  const notice = parseAuthNotice(window.location.search);
  if (notice) {
    const clean = `${window.location.pathname}${stripAuthNotice(window.location.search)}${window.location.hash}`;
    window.history.replaceState(window.history.state, "", clean);
  }
  return notice;
}

/** The i18n key (namespace common) and values for a notice's sentence. */
export function noticeText(n: AuthNotice, providerName: (p: SignInProviderId) => string): { key: string; values: Record<string, string> } {
  if (n.kind === "error") return { key: `auth.notice.error.${n.code}`, values: {} };
  if (n.kind === "hint") return { key: "auth.notice.hint", values: { provider: providerName(n.provider) } };
  return { key: `auth.notice.link.${n.result}`, values: { provider: providerName(n.provider) } };
}
