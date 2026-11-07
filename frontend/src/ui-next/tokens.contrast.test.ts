// Contrast of every text and pill pairing in the new UI's tokens, both themes (Item 74 left this "to check when
// the tokens are built"). Read from ui-next.css itself, so a token change re-runs the check. WCAG 2 AA: 4.5:1
// for small text; 3:1 for the lot's outline and chart marks against their surface is not asserted here (charts
// carry labels, Item 74).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const CSS = readFileSync(join(__dirname, "ui-next.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");

function block(selectorStart: string): Record<string, string> {
  const i = CSS.indexOf(selectorStart);
  const body = CSS.slice(CSS.indexOf("{", i) + 1, CSS.indexOf("}", i));
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/--([a-z0-9-]+):\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}
const LIGHT = block(".ui-next {");
const DARK = { ...LIGHT, ...block('[data-theme="dark"] .ui-next') };

type RGB = [number, number, number];
const rgb = (theme: Record<string, string>, name: string): RGB => theme[name].split(/\s+/).map(Number) as RGB;
const mix = (fg: RGB, a: number, bg: RGB): RGB => fg.map((c, i) => Math.round(c * a + bg[i] * (1 - a))) as RGB;
function lum([r, g, b]: RGB) {
  const f = (v: number) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
function ratio(a: RGB, b: RGB) {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe.each([["light", LIGHT], ["dark", DARK]] as const)("%s theme", (_name, theme) => {
  const ink = rgb(theme, "nx-ink");
  const muted = Number(theme["nx-ink-muted-a"]);
  const surfaces = ["nx-page", "nx-block"].map((s) => [s, rgb(theme, s)] as const);

  it("ink and secondary text pass AA on the page and on blocks", () => {
    for (const [s, bg] of surfaces) {
      expect(ratio(ink, bg), `ink on ${s}`).toBeGreaterThanOrEqual(4.5);
      expect(ratio(mix(ink, muted, bg), bg), `muted on ${s}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("stat-card text passes AA on both card colors", () => {
    const cardInk = rgb(theme, "nx-card-ink");
    for (const c of ["nx-stat-a", "nx-stat-b"]) {
      const bg = rgb(theme, c);
      expect(ratio(cardInk, bg), `card ink on ${c}`).toBeGreaterThanOrEqual(4.5);
      expect(ratio(mix(cardInk, 0.68, bg), bg), `card muted on ${c}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("every status pill's word passes AA on its fill", () => {
    for (const p of ["purple", "green", "blue", "yellow", "red"]) {
      expect(ratio(rgb(theme, `nx-pill-${p}`), rgb(theme, `nx-pill-${p}-bg`)), p).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("the main button's label passes AA", () => {
    expect(ratio(rgb(theme, "nx-primary-fg"), rgb(theme, "nx-primary"))).toBeGreaterThanOrEqual(4.5);
  });

  it("the analyst's Send label (dark) passes AA on both gradient ends", () => {
    for (const end of ["nx-send-a", "nx-send-b"]) expect(ratio([28, 28, 28], rgb(theme, end))).toBeGreaterThanOrEqual(4.5);
  });
});
