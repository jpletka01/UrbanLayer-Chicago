// Sibling JSX elements must never share a `key` expression. React cannot tell two
// same-keyed siblings apart, and on re-render it may duplicate one: on 2026-10-31 the
// Profile's WhatIfCard and CapacityMap both used `key={data.resolved_pin ?? data.address}`
// and the what-if card stacked 7-13 times as the page re-rendered on scroll. Neither
// card's own test could see it, so this checks the page source itself.

import { globSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import ts from "typescript";

// Every component under src/ (the Profile is where it bit; the rule holds everywhere).
// vitest runs from frontend/ (import.meta.url is the dev-server path here, not a file path).
const SRC = join(process.cwd(), "src");
const FILES = globSync("**/*.tsx", { cwd: SRC }).filter((f) => !f.endsWith(".test.tsx")).sort();

type El = ts.JsxElement | ts.JsxSelfClosingElement;

// The element(s) a JSX child expression can render: `cond && <X/>`, `a ? <X/> : <Y/>`, `(<X/>)`.
function elementsOf(node: ts.Node): El[] {
  if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) return [node];
  if (ts.isJsxExpression(node) && node.expression) return elementsOf(node.expression);
  if (ts.isParenthesizedExpression(node)) return elementsOf(node.expression);
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) return elementsOf(node.right);
  if (ts.isConditionalExpression(node)) return [...elementsOf(node.whenTrue), ...elementsOf(node.whenFalse)];
  return [];
}

function keyText(el: El, src: ts.SourceFile): string | null {
  const attrs = ts.isJsxElement(el) ? el.openingElement.attributes : el.attributes;
  for (const a of attrs.properties) {
    if (ts.isJsxAttribute(a) && a.name.getText(src) === "key" && a.initializer) return a.initializer.getText(src);
  }
  return null;
}

function duplicateSiblingKeys(file: string): string[] {
  const path = join(SRC, file);
  const src = ts.createSourceFile(file, readFileSync(path, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const found: string[] = [];
  const visit = (node: ts.Node) => {
    if (ts.isJsxElement(node) || ts.isJsxFragment(node)) {
      const seen = new Map<string, number>();
      for (const child of node.children) {
        // The branches of one `a ? <X/> : <Y/>` never render together, so they may share a key.
        const keys = new Map<string, number>();
        for (const el of elementsOf(child)) {
          const k = keyText(el, src);
          if (k !== null && !keys.has(k)) keys.set(k, src.getLineAndCharacterOfPosition(el.getStart(src)).line + 1);
        }
        for (const [k, line] of keys) {
          if (seen.has(k)) found.push(`${file}:${line} repeats key ${k} from line ${seen.get(k)}`);
          else seen.set(k, line);
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(src);
  return found;
}

describe("sibling JSX keys", () => {
  it("finds the component files", () => {
    expect(FILES).toContain("components/ScorecardPage.tsx");
  });

  it.each(FILES)("%s has no two siblings with the same key", (file) => {
    expect(duplicateSiblingKeys(file)).toEqual([]);
  });
});
