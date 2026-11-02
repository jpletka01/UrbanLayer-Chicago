// The first-screen counter shared by the page budgets (Profile: decision Item 51; Discovery: Item 57). Runs
// in the page (Playwright serializes it): words, amber items, solid-orange elements and page height, as a
// reader meets them on the first screen, without the site nav, footer, maps or anything aria-hidden.
export type Counts = { words: number; amber: number; orange: number; screens: number; duplicateHeadings: string[]; multiStateFigures: string[] };

export function firstScreenCounts(): Counts {
  const H = window.innerHeight;
  const skip = (el: Element) => !!el.closest("header, nav, footer, .mapboxgl-map, canvas, [data-budget-skip]");
  const shown = (el: Element) => {
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return s.visibility !== "hidden" && s.display !== "none" && Number(s.opacity) > 0 && r.width > 0 && r.height > 0;
  };
  const inFold = (el: Element) => { const r = el.getBoundingClientRect(); return r.top < H && r.bottom > 0; };
  let words = 0;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n: Node | null;
  while ((n = walker.nextNode())) {
    const el = n.parentElement;
    if (!el || skip(el) || !shown(el) || !inFold(el) || el.closest("script, style, .sr-only, [aria-hidden=true]")) continue;
    const text = (n.textContent ?? "").replace(/\s+/g, " ").trim();
    if (text) words += text.split(" ").filter((w) => /[\p{L}\p{N}$]/u.test(w)).length;
  }
  const all = [...document.body.querySelectorAll("*")];
  const isAmber = (el: Element) => {
    const cls = typeof el.className === "string" ? el.className : "";
    return /(^|\s)(text|bg|border)-(state-warning|status-warning)/.test(cls) || el.getAttribute("data-status-label") === "warning" || el.getAttribute("data-state") === "low";
  };
  const amberEls = all.filter((el) => !skip(el) && shown(el) && inFold(el) && isAmber(el));
  const amber = amberEls.filter((el) => !amberEls.some((o) => o !== el && o.contains(el))).length;
  const orange = all.filter((el) => {
    if (skip(el) || !shown(el) || !inFold(el)) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 24 || r.height < 16) return false;
    const bg = getComputedStyle(el).backgroundColor;
    return bg === "rgb(249, 164, 116)" || bg === "rgb(243, 154, 103)";
  }).length;
  const headings = [...document.querySelectorAll("main h1, main h2, main h3, main h4")].filter(shown)
    .map((h) => (h as HTMLElement).innerText.replace(/\s+/g, " ").trim()).filter(Boolean);
  const duplicateHeadings = [...new Set(headings.filter((h, i) => headings.indexOf(h) !== i))];
  const multiStateFigures = [...document.querySelectorAll("[data-figure]")]
    .filter((f) => f.querySelectorAll("[data-confidence-state]").length > 1)
    .map((f) => f.getAttribute("data-figure") ?? "?");
  const screens = Math.round((document.documentElement.scrollHeight / H) * 10) / 10;
  return { words, amber, orange, screens, duplicateHeadings, multiStateFigures };
}
