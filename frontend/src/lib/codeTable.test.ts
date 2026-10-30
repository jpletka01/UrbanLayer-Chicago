import { describe, expect, it } from "vitest";
import { parseCodeTable } from "./codeTable";

describe("parseCodeTable (the index's flattened table text)", () => {
  it("parses columns and rows", () => {
    const t = parseCodeTable(
      "Columns: District | Maximum Floor Area Ratio*\nRow 1: District: RS1; Maximum Floor Area Ratio*: 0.50\nRow 2: District: RS2; Maximum Floor Area Ratio*: 0.65",
    );
    expect(t?.columns).toEqual(["District", "Maximum Floor Area Ratio*"]);
    expect(t?.rows).toEqual([["RS1", "0.50"], ["RS2", "0.65"]]);
  });

  it("keeps ';' and ':' inside a value (cuts at the next column's marker, not at punctuation)", () => {
    const t = parseCodeTable(
      "Columns: District | Maximum Floor Area Ratio*\nRow 1: District: RM6; Maximum Floor Area Ratio*: 4.40; premium may apply - See Sec. 17-2-0304-C",
    );
    expect(t?.rows[0]).toEqual(["RM6", "4.40; premium may apply - See Sec. 17-2-0304-C"]);
  });

  it("handles multi-column tables", () => {
    const t = parseCodeTable(
      "Columns: Dash Designation | Maximum Base Floor Area Ratio | FAR Bonuses Allowed?\nRow 1: Dash Designation: 3; Maximum Base Floor Area Ratio: 3.0; FAR Bonuses Allowed?: Yes",
    );
    expect(t?.rows).toEqual([["3", "3.0", "Yes"]]);
  });

  it("returns null for text that isn't a table (the viewer falls back to plain text)", () => {
    expect(parseCodeTable("not a table")).toBeNull();
    expect(parseCodeTable("Columns: A | B\nRow 1: A: x")).toBeNull(); // a column is missing
  });
});
