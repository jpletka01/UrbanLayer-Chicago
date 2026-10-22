import { afterEach, describe, expect, it } from "vitest";
import i18n from "./i18n";
import { dataDatePhrase, type DataDate } from "./dataDates";

const t = i18n.getFixedT("en", "common");

afterEach(async () => {
  await i18n.changeLanguage("en");
});

describe("dataDatePhrase — the Profile words the same dates the chat footer and the PDF do", () => {
  it("words each kind", () => {
    const d = (over: Partial<DataDate>): DataDate => ({ key: "crime", kind: "through", as_of: "2026-10-14", ...over });
    expect(dataDatePhrase(d({}), t)).toBe("Crime through Oct 14, 2026");
    expect(dataDatePhrase(d({ key: "zoning_map", kind: "record", as_of: "2021-12-15" }), t)).toBe("Zoning map record edited Dec 15, 2021");
    expect(dataDatePhrase(d({ key: "acs_tract", kind: "period", period: "2020–2024", as_of: "2024-12-31" }), t)).toBe("ACS (tract) 2020–2024");
    expect(dataDatePhrase(d({ key: "c311", kind: "checked", as_of: "2026-10-22" }), t)).toBe("Open 311 requests checked Oct 22, 2026");
  });

  it("says what Council has passed since the code text, by how recently that was checked", () => {
    const code: DataDate = { key: "code_text", kind: "through", as_of: "2026-06-17", since: 10, since_state: "fresh" };
    expect(dataDatePhrase(code, t)).toBe("Code text current through Jun 17, 2026 (+10 later zoning amendments)");
    expect(dataDatePhrase({ ...code, since: 1 }, t)).toBe("Code text current through Jun 17, 2026 (+1 later zoning amendment)");
    expect(dataDatePhrase({ ...code, since: 3, since_state: "aging", since_checked_at: "2026-10-15" }, t))
      .toBe("Code text current through Jun 17, 2026 (+3 later zoning amendments as of Oct 15, 2026)");
    const unknown = dataDatePhrase({ ...code, since: undefined, since_state: "unknown" }, t);
    expect(unknown).toBe("Code text current through Jun 17, 2026 (couldn't check recently for later amendments)");
    expect(dataDatePhrase({ ...code, since: undefined, since_state: undefined }, t)).toBe("Code text current through Jun 17, 2026");
  });

  it("an unknown key still reads (the key stands in for its noun)", () => {
    expect(dataDatePhrase({ key: "new_source", kind: "through", as_of: "2026-10-14" }, t)).toBe("new_source through Oct 14, 2026");
  });

  it("in Spanish the words are English for now but the date is the reader's", async () => {
    await i18n.changeLanguage("es");
    const es = i18n.getFixedT("es", "common");
    expect(dataDatePhrase({ key: "crime", kind: "through", as_of: "2026-10-14" }, es)).toMatch(/^Crime through .*14.*2026/);
  });
});
