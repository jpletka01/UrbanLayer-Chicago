// The old/new isolation test (decision Item 75, Phase 1 acceptance): old and new surfaces rendered together;
// no `.ui-next` token may reach today's pages, and with the preview off nothing of the new UI renders.
import { readFileSync, globSync } from "node:fs";
import { join } from "node:path";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import tailwind from "../../tailwind.config.js";
import { Button } from "../components/ui/Button";
import { StatusLabel } from "../components/ui/StatusLabel";
import { ConfidenceState } from "../components/ui/ConfidenceState";
import { UiVersionProvider } from "./UiVersionProvider";
import { VersionedRoute } from "./VersionedRoute";
import { PreviewBadge } from "./PreviewBadge";
import { Block, Pill } from "./ui/Blocks";
import { UI_FLAG_KEY } from "./uiVersion";

const SRC = join(__dirname, "..");
const CSS = readFileSync(join(__dirname, "ui-next.css"), "utf8");

/** Every selector of every rule in a stylesheet (comments removed, @media/@supports bodies walked). */
function selectors(css: string): string[] {
  const out: string[] = [];
  const body = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const re = /([^{}]+)\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}/g;
  for (const m of body.matchAll(re)) {
    const head = m[1].trim();
    if (head.startsWith("@")) out.push(...selectors(m[2]));
    else out.push(...head.split(",").map((s) => s.trim()).filter(Boolean));
  }
  return out;
}

const NX_CLASS = /(?:^|[\s"'`:[])(?:[a-z-]+:)*(?:bg|text|border|ring|fill|stroke|from|to|via|shadow|outline|placeholder|divide|decoration)-nx-[a-z0-9-]+/;

describe("isolation: the stylesheet", () => {
  it("scopes every rule of ui-next.css to .ui-next", () => {
    const all = selectors(CSS);
    expect(all.length).toBeGreaterThan(5);
    expect(all.filter((s) => !s.includes(".ui-next"))).toEqual([]);
  });

  it("the parser would catch an unscoped rule", () => {
    expect(selectors(".ui-next { --a: 1 } :root { --nx-page: 1 } @media (x) { body { color: red } }"))
      .toEqual([".ui-next", ":root", "body"]);
  });

  it("every nx-* Tailwind color resolves only through a --nx-* variable", () => {
    const nx = (tailwind as { theme: { extend: { colors: { nx: Record<string, string> } } } }).theme.extend.colors.nx;
    for (const [k, v] of Object.entries(nx)) expect(`${k}: ${v}`).toMatch(/var\(--nx-[a-z0-9-]+\)/);
  });
});

describe("isolation: the source", () => {
  it("no file outside src/ui-next uses an nx-* class, a --nx-* variable or the .ui-next class", () => {
    const files = globSync("**/*.{ts,tsx,css}", { cwd: SRC })
      .filter((f) => !f.startsWith("ui-next/") && !f.includes(".test."));
    const hits: string[] = [];
    for (const f of files) {
      const text = readFileSync(join(SRC, f), "utf8");
      text.split("\n").forEach((line, i) => {
        if (NX_CLASS.test(line) || /--nx-/.test(line) || /className=["'`{][^"'`}]*\bui-next\b/.test(line)) hits.push(`${f}:${i + 1}`);
      });
    }
    expect(hits).toEqual([]);
  });

  it("the scan would catch one", () => {
    expect(NX_CLASS.test('className="rounded bg-nx-block"')).toBe(true);
    expect(NX_CLASS.test('className="hover:text-nx-ink/50"')).toBe(true);
    expect(NX_CLASS.test('className="bg-dark-surface"')).toBe(false);
  });
});

describe("isolation: rendered together", () => {
  beforeEach(() => localStorage.clear());
  afterEach(cleanup);

  it("old and new side by side: the new tokens stay inside the new subtree", () => {
    const style = document.createElement("style");
    style.textContent = CSS;
    document.head.appendChild(style);
    render(
      <div>
        <div data-testid="old">
          <Button variant="primary">Old</Button>
          <StatusLabel tone="warning">Old label</StatusLabel>
          <ConfidenceState kind="estimate" />
        </div>
        <div className="ui-next" data-testid="new">
          <Block title="New"><Pill tone="green">Recorded</Pill></Block>
          <Button variant="primary">Shared</Button>
          <StatusLabel tone="warning">Shared label</StatusLabel>
        </div>
      </div>,
    );
    const old = screen.getByTestId("old");
    const nu = screen.getByTestId("new");
    // No new class and no .ui-next ancestor in the old subtree.
    for (const el of old.querySelectorAll("*")) {
      expect(el.closest(".ui-next")).toBeNull();
      expect(el.getAttribute("class") ?? "").not.toMatch(/\bnx-|\bui-next\b/);
    }
    // Shared primitives render the same classes in both: the new look comes only from the scoped variables.
    const oldBtn = old.querySelector("button")!;
    const newBtn = nu.querySelector("button")!;
    expect(newBtn.className).toBe(oldBtn.className);
    expect(nu.querySelector("[data-status-label]")!.className).toBe(old.querySelector("[data-status-label]")!.className);
    // The variables themselves: defined on the new root, absent on the old one.
    expect(getComputedStyle(nu).getPropertyValue("--nx-page").trim()).toBe("255 255 255");
    expect(getComputedStyle(old).getPropertyValue("--nx-page").trim()).toBe("");
    expect(getComputedStyle(old).getPropertyValue("--action-primary").trim()).toBe("");
    style.remove();
  });

  it("with the preview off, a versioned route renders today's page and nothing of the new UI", () => {
    render(
      <MemoryRouter initialEntries={["/scorecard?pin=1"]}>
        <UiVersionProvider enabled>
          <PreviewBadge />
          <VersionedRoute id="profile" old={<p data-testid="old-page">old</p>} />
        </UiVersionProvider>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("old-page")).toBeTruthy();
    expect(document.querySelector(".ui-next")).toBeNull();
    expect(document.head.querySelector('meta[name="robots"]')).toBeNull();
    expect(localStorage.getItem(UI_FLAG_KEY)).toBeNull();
  });

  it("with the build switch off, even ?ui=next renders today's page", () => {
    render(
      <MemoryRouter initialEntries={["/scorecard?ui=next"]}>
        <UiVersionProvider enabled={false}>
          <PreviewBadge />
          <VersionedRoute id="profile" old={<p data-testid="old-page">old</p>} />
        </UiVersionProvider>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("old-page")).toBeTruthy();
    expect(document.querySelector(".ui-next")).toBeNull();
  });
});
