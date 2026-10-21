import { describe, expect, it } from "vitest";

// Spanish comes later (WS7). Until then a new es string carries the English text and
// its key path is listed in es/_untranslated.json. This guard keeps that list honest:
// every listed key exists in both locales and still equals the English, so the list
// can't go stale once someone translates it (delete the entry then).

import untranslated from "./es/_untranslated.json";

const catalogs = import.meta.glob<{ default: Record<string, unknown> }>("./{en,es}/*.json", { eager: true });

function lookup(obj: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((o, k) => (o && typeof o === "object" ? (o as Record<string, unknown>)[k] : undefined), obj);
}

describe("es/_untranslated.json", () => {
  for (const [ns, keys] of Object.entries(untranslated as Record<string, string[]>)) {
    const en = catalogs[`./en/${ns}.json`]?.default;
    const es = catalogs[`./es/${ns}.json`]?.default;
    it(`${ns}: namespace exists`, () => {
      expect(en, `en/${ns}.json`).toBeDefined();
      expect(es, `es/${ns}.json`).toBeDefined();
    });
    for (const key of keys) {
      it(`${ns}:${key} exists in both locales and is still the English text`, () => {
        const enVal = lookup(en, key);
        expect(typeof enVal, `en ${ns}:${key}`).toBe("string");
        expect(lookup(es, key), `es ${ns}:${key} was translated — remove it from _untranslated.json`).toBe(enVal);
      });
    }
  }
});
