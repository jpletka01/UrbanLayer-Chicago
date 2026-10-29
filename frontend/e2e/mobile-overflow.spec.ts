import { test, expect, type Page, type TestInfo } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Mobile horizontal-overflow audit.
 *
 * For every route × device project (see playwright.config.ts):
 *   1. Load the page, wait for its data to arrive, let layout settle.
 *   2. Assert the document doesn't scroll horizontally (scrollWidth ≤ viewport).
 *   3. Walk the DOM and name the SPECIFIC offending elements — visible, extending
 *      past the viewport, and not clipped by a scrollable/hidden ancestor — so a
 *      failure tells you exactly which component to fix, not just "page too wide".
 *   4. Re-check after scrolling to the bottom (sticky strips, lazy content).
 *   5. Save a full-page screenshot + JSON verdict to test-results/mobile-audit/
 *      for the visual "odd UI" pass (run e2e/mobile-audit-report.mjs to aggregate).
 *
 * Fixed-position elements can't add scrollWidth but CAN silently clip off-screen
 * (the invisible-to-scrollWidth class of bug — hit 2026-07-03 with nav icons over
 * the wordmark), so they're reported too, tagged `fixed`.
 */

interface Offender {
  path: string;
  left: number;
  right: number;
  width: number;
  fixed: boolean;
  text: string;
}

interface AuditResult {
  viewportWidth: number;
  scrollWidth: number;
  overflowPx: number;
  offenders: Offender[];
}

const PAGES: Array<{
  id: string;
  path: string;
  /** substring of an API response to await before auditing (best-effort) */
  awaitApi?: string;
  /** extra settle time after load, ms */
  settle?: number;
}> = [
  { id: "home", path: "/" },
  { id: "workspace-ask", path: "/?ask=1" },
  {
    id: "scorecard",
    path: "/scorecard?address=1601%20N%20Milwaukee%20Ave",
    awaitApi: "/api/scorecard",
    settle: 3000,
  },
  // The Start panel (nothing runs on arrival): audited on its own, then again after one search.
  { id: "discovery-start", path: "/discovery", settle: 1500 },
  { id: "discovery", path: "/discovery", awaitApi: "/search", settle: 3000 },
  { id: "pricing", path: "/pricing" },
  { id: "about", path: "/about" },
  { id: "settings", path: "/settings" },
  { id: "privacy", path: "/privacy" },
];

const OUT_DIR = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "test-results",
  "mobile-audit",
);

/** In-page overflow scan. Runs in the browser. */
async function auditOverflow(page: Page): Promise<AuditResult> {
  return page.evaluate(() => {
    const TOL = 1; // px tolerance for subpixel rounding
    const vw = document.documentElement.clientWidth;

    const cssPath = (el: Element): string => {
      const parts: string[] = [];
      let cur: Element | null = el;
      let depth = 0;
      while (cur && cur !== document.body && depth < 4) {
        let s = cur.tagName.toLowerCase();
        const id = (cur as HTMLElement).id;
        const testid = cur.getAttribute("data-testid");
        if (id) s += `#${id}`;
        else if (testid) s += `[data-testid=${testid}]`;
        else if (typeof (cur as HTMLElement).className === "string") {
          const cls = ((cur as HTMLElement).className as string)
            .trim()
            .split(/\s+/)
            .slice(0, 3)
            .join(".");
          if (cls) s += `.${cls}`;
        }
        parts.unshift(s);
        cur = cur.parentElement;
        depth++;
      }
      return parts.join(" > ");
    };

    /** True if some ancestor clips horizontal overflow within the viewport. */
    const clippedByAncestor = (el: Element): boolean => {
      let a = el.parentElement;
      while (a && a !== document.body) {
        const st = getComputedStyle(a);
        if (/(auto|scroll|hidden|clip)/.test(st.overflowX)) {
          const r = a.getBoundingClientRect();
          if (r.right <= vw + TOL && r.left >= -TOL) return true;
        }
        a = a.parentElement;
      }
      return false;
    };

    const offenderEls = new Set<Element>();
    const meta = new Map<Element, { fixed: boolean }>();

    for (const el of Array.from(document.querySelectorAll("body *"))) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      const st = getComputedStyle(el);
      if (st.display === "none" || st.visibility === "hidden") continue;
      if (r.right <= vw + TOL && r.left >= -TOL) continue;
      const fixed = st.position === "fixed";
      if (!fixed && clippedByAncestor(el)) continue;
      offenderEls.add(el);
      meta.set(el, { fixed });
    }

    // Keep only root offenders — if the parent is already reported, skip the child.
    const roots = Array.from(offenderEls).filter(
      (el) => !el.parentElement || !offenderEls.has(el.parentElement),
    );

    const offenders = roots.slice(0, 15).map((el) => {
      const r = el.getBoundingClientRect();
      return {
        path: cssPath(el),
        left: Math.round(r.left),
        right: Math.round(r.right),
        width: Math.round(r.width),
        fixed: meta.get(el)!.fixed,
        text: (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 60),
      };
    });

    const scrollWidth = Math.max(
      document.documentElement.scrollWidth,
      document.body?.scrollWidth ?? 0,
    );

    return {
      viewportWidth: vw,
      scrollWidth,
      overflowPx: Math.max(0, scrollWidth - vw),
      offenders,
    };
  });
}

function mergeAudits(top: AuditResult, bottom: AuditResult): AuditResult {
  const seen = new Set(top.offenders.map((o) => o.path));
  return {
    viewportWidth: top.viewportWidth,
    scrollWidth: Math.max(top.scrollWidth, bottom.scrollWidth),
    overflowPx: Math.max(top.overflowPx, bottom.overflowPx),
    offenders: [
      ...top.offenders,
      ...bottom.offenders.filter((o) => !seen.has(o.path)),
    ],
  };
}

function formatOffenders(result: AuditResult): string {
  if (result.offenders.length === 0) return "  (no element-level offenders found)";
  return result.offenders
    .map(
      (o) =>
        `  ${o.fixed ? "[fixed] " : ""}${o.path}\n` +
        `      left=${o.left} right=${o.right} width=${o.width} (viewport ${result.viewportWidth})` +
        (o.text ? `\n      text: "${o.text}"` : ""),
    )
    .join("\n");
}

async function saveArtifacts(
  page: Page,
  testInfo: TestInfo,
  pageId: string,
  result: AuditResult,
) {
  const slug = `${testInfo.project.name.replace(/\s+/g, "-")}--${pageId}`;
  fs.mkdirSync(path.join(OUT_DIR, "screens"), { recursive: true });
  fs.mkdirSync(path.join(OUT_DIR, "results"), { recursive: true });

  const shotPath = path.join(OUT_DIR, "screens", `${slug}.png`);
  try {
    await page.screenshot({ path: shotPath, fullPage: true });
  } catch {
    // fullPage can fail on GL-heavy pages; fall back to viewport shot
    await page.screenshot({ path: shotPath }).catch(() => {});
  }

  fs.writeFileSync(
    path.join(OUT_DIR, "results", `${slug}.json`),
    JSON.stringify(
      { device: testInfo.project.name, page: pageId, ...result },
      null,
      2,
    ),
  );
}

for (const pageDef of PAGES) {
  test(`no horizontal overflow: ${pageDef.id}`, async ({ page }, testInfo) => {
    // Arm the API wait before navigating so a fast response isn't missed.
    const apiWait = pageDef.awaitApi
      ? page
          .waitForResponse((r) => r.url().includes(pageDef.awaitApi!), {
            timeout: 90_000,
          })
          .catch(() => null)
      : Promise.resolve(null);

    await page.goto(pageDef.path, { waitUntil: "domcontentloaded" });
    // Discovery opens on the Start panel; "discovery" audits the page after one explicit search.
    if (pageDef.id === "discovery") {
      await page.getByTestId("discovery-start-recipe-vacant_mf_transit").click();
    }
    await page.waitForLoadState("load").catch(() => {});
    await apiWait;
    await page.evaluate(() => document.fonts.ready).catch(() => {});
    await page.waitForTimeout(pageDef.settle ?? 1200);

    // Discovery keeps one Mapbox instance mounted behind the List tab. Reveal it
    // before auditing so the phone gate catches the hidden-init 400×300 fallback.
    if (pageDef.id === "discovery") {
      await page.getByRole("button", { name: "Map", exact: true }).click();
      const mapPane = page.getByTestId("discovery-map-pane");
      const mapContainer = page.getByTestId("discovery-map-container");
      const canvas = mapPane.locator("canvas.mapboxgl-canvas");
      await expect(mapPane).toBeVisible();
      await expect(canvas).toBeVisible();
      await expect.poll(async () => {
        const containerBox = await mapContainer.boundingBox();
        const canvasBox = await canvas.boundingBox();
        if (!containerBox || !canvasBox) return false;
        const backingStoreMatches = await canvas.evaluate((element) => {
          const pixelRatio = window.devicePixelRatio;
          const rect = element.getBoundingClientRect();
          return (
            Math.abs(element.width - Math.ceil(rect.width) * pixelRatio) <= pixelRatio &&
            Math.abs(element.height - Math.ceil(rect.height) * pixelRatio) <= pixelRatio
          );
        });
        return backingStoreMatches && (
          Math.abs(containerBox.width - canvasBox.width) <= 1 &&
          Math.abs(containerBox.height - canvasBox.height) <= 1
        );
      }, { message: "Discovery Mapbox canvas and backing store must fill its revealed container" }).toBe(true);

      const keyButton = page.getByTestId("discovery-map-key-button");
      await expect(keyButton).toBeVisible();
      await keyButton.click();
      const keyPanel = page.getByTestId("discovery-map-legend");
      await expect(keyPanel).toBeVisible();
      const keyBox = await keyPanel.boundingBox();
      expect(keyBox).not.toBeNull();
      expect(keyBox!.x).toBeGreaterThanOrEqual(0);
      expect(keyBox!.x + keyBox!.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1);
      expect(keyBox!.y).toBeGreaterThanOrEqual(0);
      expect(keyBox!.y + keyBox!.height).toBeLessThanOrEqual(page.viewportSize()!.height + 1);

      const controls = [
        mapPane.locator(".mapboxgl-ctrl-bottom-left"),
        mapPane.locator(".mapboxgl-ctrl-bottom-right"),
      ];
      for (const control of controls) {
        const controlBox = await control.boundingBox();
        if (!controlBox) continue;
        const overlapsControl = !(
          keyBox!.x + keyBox!.width <= controlBox.x
          || controlBox.x + controlBox.width <= keyBox!.x
          || keyBox!.y + keyBox!.height <= controlBox.y
          || controlBox.y + controlBox.height <= keyBox!.y
        );
        expect(overlapsControl, "Discovery Map key must not cover Mapbox controls").toBe(false);
      }
    }

    const topAudit = await auditOverflow(page);

    // Sticky strips and lazy sections can introduce overflow further down.
    // Scroll in viewport steps (not one jump) so IntersectionObserver-driven
    // content (whileInView sections, CountUp) actually mounts/animates — an
    // instant jump skips the observers and audits/screenshots a ghost page.
    await page.evaluate(async () => {
      const step = window.innerHeight * 0.8;
      let y = 0;
      while (y < document.documentElement.scrollHeight) {
        window.scrollTo(0, y);
        await new Promise((r) => setTimeout(r, 120));
        y += step;
      }
      window.scrollTo(0, document.documentElement.scrollHeight);
    });
    await page.waitForTimeout(800);
    const bottomAudit = await auditOverflow(page);
    let popoverAudit: AuditResult | null = null;

    // M3 parcel-map control: audit the responsive Layers surface while it is
    // actually open, including the Mapbox-owned bottom-left attribution area.
    if (pageDef.id === "scorecard") {
      const layersButton = page.getByTestId("parcel-map-layers-button").first();
      await expect(layersButton).toBeVisible();
      await layersButton.scrollIntoViewIfNeeded();
      await layersButton.click();
      const popover = page.getByTestId("parcel-map-controls-mobile").first();
      await expect(popover).toBeVisible();
      const popoverBox = await popover.boundingBox();
      expect(popoverBox).not.toBeNull();
      expect(popoverBox!.x).toBeGreaterThanOrEqual(0);
      expect(popoverBox!.x + popoverBox!.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1);

      const attributionBox = await layersButton.locator("xpath=..").locator(".mapboxgl-ctrl-bottom-left").boundingBox();
      if (attributionBox) {
        const overlapsAttribution = !(
          popoverBox!.x + popoverBox!.width <= attributionBox.x
          || attributionBox.x + attributionBox.width <= popoverBox!.x
          || popoverBox!.y + popoverBox!.height <= attributionBox.y
          || attributionBox.y + attributionBox.height <= popoverBox!.y
        );
        expect(overlapsAttribution, "Layers popover must not cover Mapbox attribution").toBe(false);
      }
      popoverAudit = await auditOverflow(page);
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(400);

    const result = popoverAudit
      ? mergeAudits(mergeAudits(topAudit, bottomAudit), popoverAudit)
      : mergeAudits(topAudit, bottomAudit);
    await saveArtifacts(page, testInfo, pageDef.id, result);

    const scrollingOffenders = result.offenders.filter((o) => !o.fixed);
    const fixedOffenders = result.offenders.filter((o) => o.fixed);

    const message =
      `[${testInfo.project.name}] ${pageDef.id}: page scrolls horizontally — ` +
      `scrollWidth ${result.scrollWidth}px vs viewport ${result.viewportWidth}px ` +
      `(+${result.overflowPx}px)\nOffending elements:\n${formatOffenders(result)}`;

    expect(result.overflowPx, message).toBeLessThanOrEqual(1);

    // Fixed-position chrome running past the viewport clips invisibly — flag it too.
    const fixedMessage =
      `[${testInfo.project.name}] ${pageDef.id}: fixed-position element(s) extend ` +
      `past the viewport (clipped, no scrollbar):\n` +
      formatOffenders({ ...result, offenders: fixedOffenders });
    expect(fixedOffenders, fixedMessage).toHaveLength(0);

    // Belt-and-braces: if the page overflows but element detection missed the
    // culprit, still surface the raw numbers.
    void scrollingOffenders;
  });
}
