import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { SourceDetailDrawer } from "./SourceDetailDrawer";
import { lawrence, tod } from "./scorecard/amendments.fixtures";
import type { CodeChunk } from "../lib/types";

afterEach(cleanup);

const chunk: CodeChunk = {
  text: "17-3-0503 Pedestrian streets.", source_document: "Municipal Code", section: "17-3-0500", section_title: "Pedestrian streets",
  subsection: null, score: 1, cross_references: [], amended_since: [lawrence],
};

describe("SourceDetailDrawer — the chat sources panel's section viewer (WS1 M3)", () => {
  it("shows the amended-since banner above the text", () => {
    render(<SourceDetailDrawer view={{ loading: false, chunk }} onClose={() => {}} />);
    expect(screen.getByTestId("amended-since").textContent).toContain("O2026-0026042");
    expect(screen.getByText(/17-3-0503 Pedestrian streets/)).toBeTruthy();
  });

  it("no banner for an untouched section", () => {
    render(<SourceDetailDrawer view={{ loading: false, chunk: { ...chunk, amended_since: [] } }} onClose={() => {}} />);
    expect(screen.queryByTestId("amended-since")).toBeNull();
  });

  it("explains a section an amendment added (404 → notice) instead of 'could not be retrieved'", () => {
    render(
      <SourceDetailDrawer
        view={{ loading: false, chunk: null, notice: { not_in_published_code: true, section_id: "17-3-0600", message: "x", added_by: [tod] } }}
        onClose={() => {}}
      />,
    );
    expect(screen.getByTestId("not-codified").textContent).toContain("SO2026-0025391");
    expect(screen.queryByText(/couldn't be retrieved/)).toBeNull();
  });

  it("still says it couldn't be retrieved when there is no notice", () => {
    render(<SourceDetailDrawer view={{ loading: false, chunk: null }} onClose={() => {}} />);
    expect(screen.getByText(/couldn't be retrieved/)).toBeTruthy();
  });
});
