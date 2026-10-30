import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchCodeSubsection, fetchSection, isNotCodified } from "./api";

// The 404 for a section an amendment added (17-3-0600) carries a body, not just a status:
// the viewers show it instead of "unavailable". Other failures stay null.

function respond(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status })));
}

beforeEach(() => {
  document.cookie = "csrf_token=t; path=/";
});
afterEach(() => vi.unstubAllGlobals());

const detail = {
  message: "Section 17-3-0600 isn't in the published Municipal Code text we use yet.",
  section_id: "17-3-0600", not_in_published_code: true,
  added_by: [{ record: "SO2026-0025391", passed_on: "2026-10-14", title: "t", summary: null, sections: [], url: null, review_status: "unreviewed", product_effect: "pending" }],
};

describe("section fetchers", () => {
  it("a 404 with not_in_published_code resolves to the notice (both endpoints)", async () => {
    respond(404, { detail });
    const a = await fetchSection("17-3-0600");
    expect(isNotCodified(a)).toBe(true);
    expect(isNotCodified(await fetchCodeSubsection("17-3-0600"))).toBe(true);
  });

  it("a plain 404 or a server error is still null", async () => {
    respond(404, { detail: "Section 99-9-9999 not found" });
    expect(await fetchSection("99-9-9999")).toBeNull();
    respond(500, { detail: "boom" });
    expect(await fetchCodeSubsection("17-9-9999")).toBeNull();
  });

  it("a normal section carries amended_since through", async () => {
    respond(200, { text: "t", section: "17-3-0500", amended_since: [{ record: "O1" }] });
    const c = await fetchSection("17-3-0500");
    expect(isNotCodified(c)).toBe(false);
    expect((c as { amended_since: unknown[] }).amended_since).toHaveLength(1);
  });
});
