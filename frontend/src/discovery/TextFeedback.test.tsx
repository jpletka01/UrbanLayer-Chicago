import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TextFeedback } from "./TextFeedback";
import { REG } from "./_fixtures";
import type { CQS } from "./types";

afterEach(cleanup);

const cqs = (filters: CQS["filters"], textResidual: string[] = []): CQS => ({
  filters, sort: REG.defaultSort, scope: { mode: "all" }, meta: { textResidual },
});
const TIF_FROM_TEXT = { tif: { predicate: { kind: "flag" as const, value: true }, source: "text" as const } };
const TIF_FROM_USER = { tif: { predicate: { kind: "flag" as const, value: true }, source: "user" as const } };

describe("TextFeedback", () => {
  it("says no search was run, names the words, and offers an example that works", () => {
    render(<TextFeedback registry={REG} notice={{ text: "teardown in logan square", words: ["teardown", "logan", "square"] }} applied={null} />);
    const note = screen.getByTestId("discovery-text-feedback");
    expect(note.getAttribute("data-kind")).toBe("none");
    expect(note.textContent).toContain("I couldn't turn “teardown in logan square” into filters, so no search was run.");
    expect(note.textContent).toContain("Not understood: teardown, logan, square.");
    expect(note.textContent).toContain("“multifamily built before 1950 with a TIF”");
  });

  it("after a search, names what the evaluated query took from the text and what it ignored", () => {
    render(<TextFeedback registry={REG} notice={null} applied={{ cqs: cqs(TIF_FROM_TEXT, ["l"]), text: "tif near the L" }} />);
    const note = screen.getByTestId("discovery-text-feedback");
    expect(note.textContent).toBe("From “tif near the L” I understood: TIF district. Not understood: l.");
  });

  it("stays quiet when the whole phrase was understood (the chips already say it)", () => {
    render(<TextFeedback registry={REG} notice={null} applied={{ cqs: cqs(TIF_FROM_TEXT), text: "tif" }} />);
    expect(screen.queryByTestId("discovery-text-feedback")).toBeNull();
  });

  it("says the text did nothing when the search ran on other filters only", () => {
    render(<TextFeedback registry={REG} notice={null} applied={{ cqs: cqs(TIF_FROM_USER, ["teardown"]), text: "teardown" }} />);
    expect(screen.getByTestId("discovery-text-feedback").textContent).toBe(
      "I couldn't turn “teardown” into filters; the search used only the other filters. Not understood: teardown.",
    );
  });

  it("shows nothing before a search or when there was no text", () => {
    const { container, rerender } = render(<TextFeedback registry={REG} notice={null} applied={null} />);
    expect(container.textContent).toBe("");
    rerender(<TextFeedback registry={REG} notice={null} applied={{ cqs: cqs({}), text: "  " }} />);
    expect(container.textContent).toBe("");
  });
});
