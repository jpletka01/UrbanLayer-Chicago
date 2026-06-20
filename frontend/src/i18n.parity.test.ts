import { describe, it, expect } from "vitest";

// Every locale namespace must have identical key structure across en/es. This is
// the guard that would have caught the 2026-06-20 "3 of 5 zones" / "3 of 3 zones"
// bug (a key that diverged in content) and catches the more common case of a key
// added to en but never translated into es (silent English leak).

import enCommon from "./locales/en/common.json";
import enChat from "./locales/en/chat.json";
import enSidebar from "./locales/en/sidebar.json";
import enLanding from "./locales/en/landing.json";
import enMap from "./locales/en/map.json";
import enData from "./locales/en/data.json";
import enPages from "./locales/en/pages.json";

import esCommon from "./locales/es/common.json";
import esChat from "./locales/es/chat.json";
import esSidebar from "./locales/es/sidebar.json";
import esLanding from "./locales/es/landing.json";
import esMap from "./locales/es/map.json";
import esData from "./locales/es/data.json";
import esPages from "./locales/es/pages.json";

type Json = Record<string, unknown>;

/** Recursively collect dotted key paths (leaves only). */
function keyPaths(obj: Json, prefix = ""): string[] {
  const out: string[] = [];
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) {
      out.push(...keyPaths(v as Json, path));
    } else {
      out.push(path); // string or array leaf
    }
  }
  return out;
}

/** Interpolation placeholders ({{x}}) referenced by a string value. */
function placeholders(s: string): string[] {
  return (s.match(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g) ?? []).sort();
}

const NS: Record<string, [Json, Json]> = {
  common: [enCommon, esCommon],
  chat: [enChat, esChat],
  sidebar: [enSidebar, esSidebar],
  landing: [enLanding, esLanding],
  map: [enMap, esMap],
  data: [enData, esData],
  pages: [enPages, esPages],
};

describe("locale key parity (en/es)", () => {
  for (const [ns, [en, es]] of Object.entries(NS)) {
    it(`${ns}: identical key set`, () => {
      const enKeys = new Set(keyPaths(en));
      const esKeys = new Set(keyPaths(es));
      const missingInEs = [...enKeys].filter((k) => !esKeys.has(k));
      const missingInEn = [...esKeys].filter((k) => !enKeys.has(k));
      expect({ ns, missingInEs, missingInEn }).toEqual({ ns, missingInEs: [], missingInEn: [] });
    });

    it(`${ns}: matching interpolation placeholders`, () => {
      // A translated string must reference the same {{vars}} as its English source,
      // so callers' interpolation always resolves in both languages.
      const flat = (obj: Json, prefix = ""): Record<string, string> => {
        const acc: Record<string, string> = {};
        for (const [k, v] of Object.entries(obj)) {
          const path = prefix ? `${prefix}.${k}` : k;
          if (typeof v === "string") acc[path] = v;
          else if (v && typeof v === "object" && !Array.isArray(v)) Object.assign(acc, flat(v as Json, path));
        }
        return acc;
      };
      const enFlat = flat(en);
      const esFlat = flat(es);
      const mismatches: string[] = [];
      for (const [path, enVal] of Object.entries(enFlat)) {
        const esVal = esFlat[path];
        if (esVal == null) continue; // key-set test covers missing keys
        const a = placeholders(enVal).join(",");
        const b = placeholders(esVal).join(",");
        if (a !== b) mismatches.push(`${path}: en[${a}] vs es[${b}]`);
      }
      expect(mismatches).toEqual([]);
    });
  }
});
