// Live-site sweep: load every main route on desktop and a phone, and report
// console errors, uncaught page errors, failed requests (HTTP >= 400) and
// horizontal overflow. Exits 1 if anything is found.
//
//   npm run sweep:live                                   # production
//   SWEEP_BASE_URL=http://localhost:5173 npm run sweep:live
//
// Needs a Playwright browser once: npx playwright install chromium
import { chromium, devices } from "@playwright/test";

const BASE = (process.env.SWEEP_BASE_URL ?? "https://urbanlayerchicago.com").replace(/\/$/, "");
const ROUTES = [
  "/",
  "/scorecard?address=1601%20N%20Milwaukee%20Ave",
  "/discovery",
  "/pricing",
  "/about",
  "/privacy",
  "/?ask=1",
  "/no-such-page",
];
const VIEWPORTS = [
  ["desktop", { viewport: { width: 1440, height: 900 } }],
  ["mobile", devices["iPhone 15"]],
];

const browser = await chromium.launch();
let total = 0;
for (const [label, options] of VIEWPORTS) {
  const context = await browser.newContext({ ...options, colorScheme: "light" });
  for (const route of ROUTES) {
    const page = await context.newPage();
    const issues = [];
    page.on("console", (m) => m.type() === "error" && issues.push(`console: ${m.text().slice(0, 140)}`));
    page.on("pageerror", (e) => issues.push(`pageerror: ${String(e).slice(0, 140)}`));
    page.on("response", (r) => r.status() >= 400 && issues.push(`${r.status()} ${r.url().replace(BASE, "").slice(0, 90)}`));
    try {
      await page.goto(BASE + route, { waitUntil: "networkidle", timeout: 90_000 });
      // The Property Profile keeps loading after networkidle on a cold lookup.
      await page.waitForTimeout(route.startsWith("/scorecard") ? 6000 : 2500);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (overflow > 1) issues.push(`horizontal overflow ${overflow}px`);
    } catch (e) {
      issues.push(`navigation: ${String(e).slice(0, 100)}`);
    }
    total += issues.length;
    console.log(`${label.padEnd(8)}${route.padEnd(50)}${issues.length ? issues.join(" | ") : "clean"}`);
    await page.close();
  }
  await context.close();
}
await browser.close();
console.log(`\n${total === 0 ? "clean" : `${total} issue(s)`} (${BASE})`);
process.exit(total === 0 ? 0 : 1);
