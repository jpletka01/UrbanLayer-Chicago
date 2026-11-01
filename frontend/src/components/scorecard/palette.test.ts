// The Profile picks color ROLES, never hues (decision Item 49). This fails on a raw Tailwind palette
// class (`text-amber-400`, `bg-emerald-500/20`, …) anywhere in the Profile's components, so a status
// color can't be chosen by hue again. Use the role tokens instead: `status-{success,warning,danger,
// info,neutral}`, `action` (clickable orange), `premium` (violet, paid only), the neutral ramp.
// Map and chart data encodings live in lib/ (mapColors.ts, upsideColor.ts) and are exempt.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const HUES = "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose";
const RAW = new RegExp(
  `\\b(?:[a-z-]+:)*(?:bg|text|border|ring|fill|stroke|from|to|via|outline|decoration|divide|shadow|accent|caret)-(?:${HUES})-\\d{2,3}\\b`,
  "g",
);

const ROOT = join(__dirname, "..");
const FILES = [
  ...readdirSync(join(ROOT, "scorecard"))
    .filter((f) => f.endsWith(".tsx") && !f.includes(".test."))
    .map((f) => join(ROOT, "scorecard", f)),
  join(ROOT, "ScorecardPage.tsx"),
  ...["Button.tsx", "StatusLabel.tsx", "ConfidenceState.tsx", "Toggletip.tsx"].map((f) => join(ROOT, "ui", f)),
];

describe("Profile color roles", () => {
  it("uses no raw palette classes", () => {
    const hits: string[] = [];
    for (const file of FILES) {
      readFileSync(file, "utf8").split("\n").forEach((line, i) => {
        for (const match of line.matchAll(RAW)) hits.push(`${file.slice(ROOT.length + 1)}:${i + 1} ${match[0]}`);
      });
    }
    expect(hits).toEqual([]);
  });

  it("would catch one", () => {
    expect("className=\"text-amber-400 md:bg-emerald-500/20\"".match(RAW)).toEqual(["text-amber-400", "md:bg-emerald-500"]);
  });
});
