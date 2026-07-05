import { defineConfig, devices } from "@playwright/test";

/**
 * Mobile-friendliness audit config.
 *
 * 5-device panel = the popular phone form factors (3 iPhone + 2 Android),
 * spanning the 360–430px CSS-width range that covers virtually all phones:
 *   - Galaxy S24 (360w)          — narrowest mainstream width; the stress case
 *   - iPhone SE 3rd gen (375w)   — small/budget iPhone
 *   - Pixel 3 (393w)             — Jack's repro device
 *   - iPhone 15 (393w)           — current mainstream iPhone
 *   - iPhone 15 Pro Max (430w)   — large iPhone
 *
 * iPhones run on WebKit (Safari's engine — catches Safari-only layout bugs);
 * Androids run on Chromium. `npx playwright install webkit chromium` once.
 *
 * Requires the dev stack running (vite :5173 + backend :8001), or point at
 * prod: E2E_BASE_URL=https://urbanlayerchicago.com npm run test:mobile
 */
export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  workers: 3,
  timeout: 120_000,
  reporter: [["list"], ["json", { outputFile: "test-results/mobile-audit.json" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    // Kill entrance animations so we audit settled layout, not mid-transition frames.
    contextOptions: { reducedMotion: "reduce" },
  },
  projects: [
    { name: "Galaxy S24", use: { ...devices["Galaxy S24"] } },
    { name: "iPhone SE", use: { ...devices["iPhone SE (3rd gen)"] } },
    { name: "Pixel 3", use: { ...devices["Pixel 3"] } },
    { name: "iPhone 15", use: { ...devices["iPhone 15"] } },
    { name: "iPhone 15 Pro Max", use: { ...devices["iPhone 15 Pro Max"] } },
  ],
});
