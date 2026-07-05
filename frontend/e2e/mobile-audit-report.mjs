#!/usr/bin/env node
/**
 * Aggregates test-results/mobile-audit/results/*.json (written by
 * mobile-overflow.spec.ts) into a device × page matrix plus a per-failure
 * offender list. Run after `npm run test:mobile`:
 *
 *   node e2e/mobile-audit-report.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dir = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "test-results",
  "mobile-audit",
  "results",
);

if (!fs.existsSync(dir)) {
  console.error(`No results at ${dir} — run \`npm run test:mobile\` first.`);
  process.exit(1);
}

const entries = fs
  .readdirSync(dir)
  .filter((f) => f.endsWith(".json"))
  .map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")));

const devices = [...new Set(entries.map((e) => e.device))];
const pages = [...new Set(entries.map((e) => e.page))];

const cell = (e) => {
  if (!e) return "—";
  const fixed = e.offenders?.filter((o) => o.fixed).length ?? 0;
  if (e.overflowPx <= 1 && fixed === 0) return "ok";
  const parts = [];
  if (e.overflowPx > 1) parts.push(`+${e.overflowPx}px`);
  if (fixed > 0) parts.push(`${fixed} fixed`);
  return parts.join(" ");
};

// Matrix
const colW = Math.max(...devices.map((d) => d.length), 6) + 2;
const rowW = Math.max(...pages.map((p) => p.length), 4) + 2;
console.log("\nHorizontal-overflow matrix (px past viewport):\n");
console.log(" ".repeat(rowW) + devices.map((d) => d.padEnd(colW)).join(""));
for (const p of pages) {
  const row = devices.map((d) => {
    const e = entries.find((x) => x.device === d && x.page === p);
    return cell(e).padEnd(colW);
  });
  console.log(p.padEnd(rowW) + row.join(""));
}

// Failures detail
const failures = entries.filter(
  (e) => e.overflowPx > 1 || e.offenders?.some((o) => o.fixed),
);
if (failures.length === 0) {
  console.log("\nAll clean across the panel.\n");
} else {
  console.log(`\n${failures.length} failing page×device combos:\n`);
  for (const f of failures) {
    console.log(
      `● ${f.page} @ ${f.device} — scrollWidth ${f.scrollWidth} vs viewport ${f.viewportWidth} (+${f.overflowPx}px)`,
    );
    for (const o of f.offenders ?? []) {
      console.log(
        `    ${o.fixed ? "[fixed] " : ""}${o.path}  (left=${o.left} right=${o.right} w=${o.width})`,
      );
      if (o.text) console.log(`        "${o.text}"`);
    }
    console.log();
  }
  console.log(
    "Screenshots: test-results/mobile-audit/screens/<Device>--<page>.png\n",
  );
}
