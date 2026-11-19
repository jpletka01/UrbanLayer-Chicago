// Render the landing hero from the live site's own 3D map (the Cities: Skylines style, never satellite; Item 133's
// review, owner 2026-11-18): the Profile's Build view at 1601 N Milwaukee Ave, full frame, labels, pins and page
// chrome hidden, at 2x. Reads only the public site; no model calls.
//
//   cd frontend && node scripts/render-hero.mjs light /tmp/hero-light.png
//   cd frontend && node scripts/render-hero.mjs dark  /tmp/hero-dark.png
//   PW_CHROME=<path to a Chromium> overrides the browser (when Playwright's own build isn't downloaded).
//
// Then encode at 2400x920 and 1200x460 as JPEG (q84) into src/app/landing/hero/.
import { chromium } from "@playwright/test";

const [, , theme = "light", out = `hero-${theme}.png`] = process.argv;
const W = 1200, H = 460;
const CAMERA = { center: [-87.6778, 41.9108], zoom: 16.8, pitch: 60, bearing: -30 };

const browser = await chromium.launch({
  ...(process.env.PW_CHROME && { executablePath: process.env.PW_CHROME }),
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 2, colorScheme: theme });
await page.addInitScript((t) => localStorage.setItem("urbanlayer-theme", t), theme);
await page.goto("https://urbanlayerchicago.com/scorecard?address=1601+N+Milwaukee+Ave&tab=build", { waitUntil: "domcontentloaded" });
await page.waitForSelector(".maplibregl-canvas", { timeout: 90_000 });
await page.waitForTimeout(12_000); // the Profile's parts and the zoning mass arrive after the map

// The production build exposes no map handle, so find the MapLibre instance through the map box's React fiber.
await page.evaluate(({ W, H, CAMERA }) => {
  const box = document.querySelector(".maplibregl-canvas").closest(".maplibregl-map");
  const fiberKey = Object.keys(box).find((k) => k.startsWith("__reactFiber"));
  const isMap = (o) => o && typeof o === "object" && typeof o.jumpTo === "function" && typeof o.getStyle === "function";
  const scan = (o, d) => {
    if (!o || typeof o !== "object" || d > 3) return null;
    if (isMap(o)) return o;
    for (const k of Object.keys(o)) { try { const r = scan(o[k], d + 1); if (r) return r; } catch { /* getters */ } }
    return null;
  };
  let f = box[fiberKey], map = null;
  for (let up = 0; f && !map && up < 60; up++, f = f.return) {
    for (let s = f.memoizedState, i = 0; s && !map && i < 40; s = s.next, i++) map = scan(s.memoizedState, 0);
  }
  if (!map) throw new Error("map instance not found");
  window.__heroMap = map;
  const st = document.createElement("style");
  st.textContent = `body *{visibility:hidden!important} .hero-map,.hero-map *{visibility:visible!important}
    .hero-map{position:fixed!important;inset:0!important;width:${W}px!important;height:${H}px!important;z-index:2147483647!important;border-radius:0!important}
    .hero-map > :not(.maplibregl-canvas-container){display:none!important}`;
  document.head.appendChild(st);
  box.classList.add("hero-map");
  map.resize();
  for (const l of map.getStyle().layers) if (l.type === "symbol") map.setLayoutProperty(l.id, "visibility", "none");
  map.jumpTo(CAMERA);
}, { W, H, CAMERA });
await page.waitForTimeout(3000);
await page.evaluate(() => new Promise((r) => {
  const m = window.__heroMap;
  if (m.loaded() && m.areTilesLoaded()) r(); else m.once("idle", r);
  setTimeout(r, 30_000);
}));
await page.waitForTimeout(1500);
await page.screenshot({ path: out, type: "png" });
await browser.close();
console.log(`wrote ${out}`);
