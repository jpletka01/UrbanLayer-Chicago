// Every link that opens a page opens it in a NEW tab, never in place of the current one (Jack,
// 2026-11-02). This fails on an <a href> in app code without target="_blank". Allowed in place:
// mailto:/tel: links (they open another app, not a page). In-app navigation uses router <Link>s and
// sign-in / checkout redirects use window.location, so neither is an <a href> here.
import { readFileSync } from "node:fs";
import { globSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = join(__dirname, "..");
const ANCHOR = /<a\b(?:[^>{}]|\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})*?>/gs;

function offenders(source: string, file: string): string[] {
  const out: string[] = [];
  for (const m of source.matchAll(ANCHOR)) {
    const tag = m[0];
    if (!/\bhref=/.test(tag)) continue;
    if (/target="_blank"|target=\{/.test(tag)) continue;
    if (/href="(mailto|tel):/.test(tag)) continue;
    const line = source.slice(0, m.index).split("\n").length;
    out.push(`${file}:${line}`);
  }
  return out;
}

describe("links open in a new tab", () => {
  it("every <a href> in app code has target=\"_blank\"", () => {
    const files = globSync("**/*.tsx", { cwd: ROOT }).filter((f) => !f.includes(".test."));
    const hits = files.flatMap((f) => offenders(readFileSync(join(ROOT, f), "utf8"), f));
    expect(hits).toEqual([]);
  });

  it("would catch one", () => {
    expect(offenders('<a href={url} className="x">go</a>', "f.tsx")).toEqual(["f.tsx:1"]);
    expect(offenders('<a href={url} target="_blank" rel="noopener noreferrer">go</a>', "f.tsx")).toEqual([]);
    expect(offenders('<a href="mailto:x@y.z">mail</a>', "f.tsx")).toEqual([]);
  });
});
