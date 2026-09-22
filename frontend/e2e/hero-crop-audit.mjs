#!/usr/bin/env node
/**
 * Hero backdrop crop audit — "how much of the Bean survives at each screen shape?"
 *
 *   node e2e/hero-crop-audit.mjs                      # audits prod
 *   node e2e/hero-crop-audit.mjs http://localhost:5173
 *   node e2e/hero-crop-audit.mjs --json               # machine-readable
 *
 * WHY THIS EXISTS
 * ---------------
 * `DotMatrix` paints the hero photo with object-fit: cover semantics (`coverCrop`
 * in dotGrid.ts). Cover always sacrifices one axis. Our asset is LANDSCAPE
 * (700×385, aspect 1.82) and the hero container is TALL on phones — its height is
 * driven by stacked content (headline + input + chips + preview card ≈ 1350px), not
 * by the viewport — so narrow screens crop HORIZONTALLY, and hard. The subject is
 * a wide object whose whole identity is its silhouette, so a horizontal crop
 * destroys it in a way a vertical crop never would.
 *
 * You cannot see this in an overflow audit (nothing overflows) or in a desktop
 * screenshot (desktop is fine). It needs its own metric.
 *
 * THE METRICS
 * -----------
 * Measured per device, against the REAL rendered canvas rect (hero height is
 * content-driven, so it must be measured, never assumed from the viewport):
 *
 *   heroAspect   = canvas.width / canvas.height
 *   keep         = min(1, heroAspect / imgAspect)
 *                  fraction of the SOURCE IMAGE WIDTH that survives coverCrop.
 *                  This is coverCrop's own formula, not an approximation.
 *   beanCoverage = fraction of the subject's bounding box still inside the window
 *   archCoverage = fraction of the arch+legs (the recognizable feature) still in
 *
 * `keep` measures the crop. `beanCoverage`/`archCoverage` measure what the crop
 * COSTS — which is the number that actually matters. A tall-but-wide hero can
 * have a low `keep` and still show the whole subject if the subject is narrow;
 * ours isn't, so the two track closely.
 *
 * GRADES (on beanCoverage — the subject, not the crop)
 *   >= 0.90  ok        subject essentially intact
 *   >= 0.70  clipped   edges lost, still reads as the object
 *   <  0.70  broken    no longer recognizable — this is a bug, not a crop
 *
 * The crop is theme-independent (same asset, same geometry in light and dark), so
 * one dark-mode pass covers both.
 */
import { chromium } from "playwright";

const BASE = process.argv.find((a) => a.startsWith("http")) ?? "https://urbanlayerchicago.com";
const AS_JSON = process.argv.includes("--json");

/** Source asset intrinsics — update together if the asset is replaced. */
const IMG = { w: 700, h: 385 };
/**
 * Subject extents as fractions of source width, read off a 20-division measured
 * grid over the asset (scratch: overlay gridlines, read the edges).
 *   bean — the sculpture's full bounding box
 *   arch — the legs and the opening between them: the feature that makes it
 *          READ as Cloud Gate rather than as a gray blob
 */
const BEAN = { x0: 0.100, x1: 0.925 };
const ARCH = { x0: 0.330, x1: 0.720 };

const GRADES = [
  { min: 0.9, name: "ok" },
  { min: 0.7, name: "clipped" },
  { min: 0, name: "BROKEN" },
];

/**
 * Standard screen shapes. Deliberately wider than playwright.config.ts's phone
 * panel: this failure is driven by ASPECT RATIO, so it has to sweep from the
 * narrowest phone to ultrawide to find where the subject actually breaks.
 */
const PANEL = [
  ["phone", "Galaxy S24", 360, 800],
  ["phone", "iPhone SE", 375, 667],
  ["phone", "iPhone 14/15", 390, 844],
  ["phone", "Pixel 8 / iPhone 15", 393, 852],
  ["phone", "Android large", 412, 915],
  ["phone", "iPhone Pro Max", 430, 932],
  ["phone-ls", "iPhone 15 landscape", 852, 393],
  ["tablet", "iPad portrait", 768, 1024],
  ["tablet", "iPad Air portrait", 820, 1180],
  ["tablet", "iPad landscape", 1024, 768],
  ["laptop", "MacBook Air 13", 1280, 800],
  ["laptop", "1366x768", 1366, 768],
  ["laptop", "MacBook Pro 16", 1512, 982],
  ["desktop", "1080p", 1920, 1080],
  ["desktop", "1440p", 2560, 1440],
  ["desktop", "ultrawide", 3440, 1440],
];

const overlap = (a0, a1, b0, b1) => Math.max(0, Math.min(a1, b1) - Math.max(a0, b0));
const gradeOf = (c) => GRADES.find((g) => c >= g.min).name;

const browser = await chromium.launch();
const rows = [];
for (const [cls, name, w, h] of PANEL) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h } });
  await ctx.addInitScript(() => localStorage.setItem("urbanlayer-theme", "dark"));
  const page = await ctx.newPage();
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  const rect = await page.evaluate(() => {
    const c = document.querySelector("canvas");
    if (!c) return null;
    const r = c.getBoundingClientRect();
    return { w: r.width, h: r.height };
  });
  await ctx.close();

  if (!rect || !rect.w || !rect.h) {
    rows.push({ cls, name, w, h, error: "hero canvas not found" });
    continue;
  }
  const heroAspect = rect.w / rect.h;
  const keep = Math.min(1, heroAspect / (IMG.w / IMG.h));
  const win0 = 0.5 - keep / 2;
  const win1 = 0.5 + keep / 2;
  const bean = overlap(win0, win1, BEAN.x0, BEAN.x1) / (BEAN.x1 - BEAN.x0);
  const arch = overlap(win0, win1, ARCH.x0, ARCH.x1) / (ARCH.x1 - ARCH.x0);
  rows.push({
    cls, name, viewport: `${w}x${h}`,
    hero: `${Math.round(rect.w)}x${Math.round(rect.h)}`,
    heroAspect: +heroAspect.toFixed(3),
    keep: +keep.toFixed(3),
    beanCoverage: +bean.toFixed(3),
    archCoverage: +arch.toFixed(3),
    grade: gradeOf(bean),
  });
}
await browser.close();

if (AS_JSON) {
  console.log(JSON.stringify({ base: BASE, img: IMG, bean: BEAN, arch: ARCH, rows }, null, 2));
} else {
  console.log(`\nHero crop audit — ${BASE}\n`);
  console.log(
    ["class", "device".padEnd(20), "viewport".padEnd(10), "hero".padEnd(10),
     "aspect", " keep", " bean", " arch", "grade"].join("  "),
  );
  console.log("-".repeat(88));
  for (const r of rows) {
    if (r.error) { console.log(`${r.cls}  ${r.name}  ${r.error}`); continue; }
    console.log(
      [r.cls.padEnd(8), r.name.padEnd(20), r.viewport.padEnd(10), r.hero.padEnd(10),
       r.heroAspect.toFixed(2).padStart(6),
       `${Math.round(r.keep * 100)}%`.padStart(5),
       `${Math.round(r.beanCoverage * 100)}%`.padStart(5),
       `${Math.round(r.archCoverage * 100)}%`.padStart(5),
       r.grade].join("  "),
    );
  }
  const broken = rows.filter((r) => r.grade === "BROKEN");
  console.log(
    `\n${broken.length} of ${rows.length} shapes BROKEN (subject coverage < 70%)` +
    (broken.length ? `: ${[...new Set(broken.map((r) => r.cls))].join(", ")}` : ""),
  );
}
process.exit(rows.some((r) => r.grade === "BROKEN") ? 1 : 0);
