// Print the Property Profile's verdict text for saved /api/scorecard responses.
//
// The verdict (headline, reasons, caveats) is computed in the browser by
// frontend/src/lib/scorecardVerdict.ts, so the kit scorer asks the real module
// what a user would read, rather than re-implementing it. Usage:
//
//   node --experimental-strip-types eval/kit/verdict_text.mjs a.json b.json
//
// Prints a JSON object keyed by file path. Node >= 22.6 (the repo pins 24).
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..", "..");
const { computeVerdict } = await import(
  resolve(root, "frontend/src/lib/scorecardVerdict.ts")
);
const strings = JSON.parse(
  readFileSync(resolve(root, "frontend/src/locales/en/pages.json"), "utf8"),
);

// Just enough of i18next: dotted-path lookup, {{var}} interpolation, _one/_other.
function t(key, opts = {}) {
  const node = (k) => k.split(".").reduce((o, p) => (o == null ? o : o[p]), strings);
  let s = node(key);
  if (s === undefined && typeof opts.count === "number") {
    s = node(key + (opts.count === 1 ? "_one" : "_other"));
  }
  if (typeof s !== "string") return key;
  return s.replace(/\{\{\s*(\w+)\s*\}\}/g, (_, v) => String(opts[v] ?? ""));
}

const out = {};
for (const file of process.argv.slice(2)) {
  const v = computeVerdict(JSON.parse(readFileSync(file, "utf8")), t);
  out[file] = {
    category: v.category,
    headline: v.headline,
    reasons: v.reasons.map((r) => r.text),
    caveats: v.caveats,
    next_step: v.nextStep.label,
    confidence: v.confidence,
  };
}
process.stdout.write(JSON.stringify(out, null, 2) + "\n");
