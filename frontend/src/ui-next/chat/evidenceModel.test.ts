import { describe, expect, it } from "vitest";
import type { CodeChunk, Message } from "../../lib/types";
import { citingSentence, codeTable, numberForData, passageFor, recordsIn, sourcesFor } from "./evidenceModel";

const ADU: CodeChunk = {
  text: "17-7-0570-A Purpose. The ADU overlay allows additional dwelling units. 17-7-0570-C Coach houses. On a zoning lot in an RS district within an ADU-eligible area, one coach house containing one dwelling unit may be established in a detached accessory building. 17-7-0570-E Owner occupancy. The owner must live on the lot.",
  source_document: "", section: "17-7-0570", section_title: "Additional dwelling units", subsection: null, score: 1, cross_references: [],
};
const BULK: CodeChunk = {
  text: "Bulk and density standards\n| District | Min lot area per unit (sq ft) | Max FAR | Max height (ft) |\n|---|---|---|---|\n| RS-2 | 5,000 | 0.65 | 30 |\n| RS-3 | 2,500 | 0.9 | 30 |\n| RT-4 | 1,000 | 1.2 | 38 |",
  source_document: "", section: "17-2-0300", section_title: "Bulk and density", subsection: null, score: 1, cross_references: [],
};
const ANSWER: Message = {
  role: "assistant",
  content: "**RS-3, so two units fit.** RS-3 needs 2,500 sq ft of lot per unit [1]. It's in an ADU-eligible area, so a coach house could add one dwelling unit [2]. Crime is about average [data:crime].",
  context: { code_chunks: [BULK, ADU], resolved_address: "2541 N Spaulding Ave", property: { pin14: "13264210060000" }, crime_last_90d: { total: 386, arrest_rate: 0.1, by_type: {} } } as never,
};

describe("the sources list", () => {
  it("numbers code as cited, then the records the answer has, in a fixed order", () => {
    expect(sourcesFor(ANSWER).map((s) => `${s.n}:${s.kind}`)).toEqual(["1:code", "2:code", "3:lot", "4:facts", "5:crime"]);
  });
  it("sends a data citation to its record", () => {
    const items = sourcesFor(ANSWER);
    expect(numberForData(items, "crime")).toBe(5);
    expect(numberForData(items, "311")).toBeNull();
  });
  it("lists only records the answer carries", () => {
    expect(recordsIn(undefined, undefined)).toEqual([]);
    expect(recordsIn({ violations: { total: 1 } } as never, undefined)).toEqual(["violations"]);
  });
});

describe("the passage the answer used", () => {
  it("finds the citing sentence without markup or citation marks", () => {
    expect(citingSentence(ANSWER.content, 2)).toBe("It's in an ADU-eligible area, so a coach house could add one dwelling unit");
    expect(citingSentence(ANSWER.content, 9)).toBeNull();
  });
  it("lights up the section's best-matching sentence", () => {
    const [s, e] = passageFor(ADU.text, citingSentence(ANSWER.content, 2))!;
    expect(ADU.text.slice(s, e)).toContain("one coach house containing one dwelling unit");
    expect(ADU.text.slice(s, e)).not.toContain("Owner occupancy");
  });
  it("highlights nothing when nothing matches strongly", () => {
    expect(passageFor(ADU.text, "Parking is reduced near transit")).toBeNull();
    expect(passageFor(ADU.text, null)).toBeNull();
  });
});

describe("a code table", () => {
  it("reads the table and marks the district the answer used", () => {
    const t = codeTable(BULK.text, citingSentence(ANSWER.content, 1))!;
    expect(t.header).toEqual(["District", "Min lot area per unit (sq ft)", "Max FAR", "Max height (ft)"]);
    expect(t.rows[t.hit!]).toEqual(["RS-3", "2,500", "0.9", "30"]);
  });
  it("is null for prose", () => {
    expect(codeTable(ADU.text, null)).toBeNull();
  });
});
