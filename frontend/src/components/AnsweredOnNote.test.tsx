import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { AnsweredOnNote } from "./AnsweredOnNote";
import type { SinceThenResult } from "../lib/types";

afterEach(cleanup);

const CREATED = Date.UTC(2026, 9, 2, 17);
const base: SinceThenResult = { status: "none", changes: [], unchecked: [] };

describe("AnsweredOnNote (WS6 M9)", () => {
  it("shows only the date until the check has answered", () => {
    render(<AnsweredOnNote createdAt={CREATED} />);
    expect(screen.getByTestId("since-then").textContent).toBe("Answered Oct 2, 2026");
  });

  it("says no material change when the recheck found none", () => {
    render(<AnsweredOnNote createdAt={CREATED} note={base} />);
    expect(screen.getByTestId("since-then").textContent).toContain("rechecked today: no material change");
  });

  it("never says no change for something it could not read", () => {
    render(<AnsweredOnNote createdAt={CREATED} note={{ ...base, status: "unavailable", unchecked: ["everything"] }} />);
    const text = screen.getByTestId("since-then").textContent ?? "";
    expect(text).toContain("couldn't re-check today");
    expect(text).not.toContain("no material change");
  });

  it("a partial recheck says what it could not read", () => {
    render(<AnsweredOnNote createdAt={CREATED} note={{ ...base, status: "partial", unchecked: ["district"] }} />);
    expect(screen.getByTestId("since-then").textContent).toContain("couldn't re-check the district");
  });

  it("an answer under a day old, or past the parcel cap, says only its date", () => {
    for (const status of ["too_soon", "skipped"] as const) {
      render(<AnsweredOnNote createdAt={CREATED} note={{ ...base, status }} />);
      expect(screen.getByTestId("since-then").textContent).toBe("Answered Oct 2, 2026");
      cleanup();
    }
  });

  it("a change shows the callout with the ordinance link, the Profile link and, for the owner, Ask again", () => {
    const onAskAgain = vi.fn();
    render(
      <AnsweredOnNote
        createdAt={CREATED}
        profileHref="/scorecard?pin=14313320180000"
        onAskAgain={onAskAgain}
        note={{
          status: "changes", unchecked: [],
          changes: [{ kind: "district", old: "B3-2", new: "B2-3", record: "O2026-7", passed_on: "2026-09-23", url: "https://clerk.example/o" }],
        }}
      />,
    );
    const box = screen.getByTestId("since-then-changes");
    expect(box.textContent).toContain("Since this answer (Oct 2, 2026)");
    expect(box.textContent).toContain("now shows B2-3, not B3-2");
    expect(screen.getByRole("link", { name: /O2026-7/ }).getAttribute("href")).toBe("https://clerk.example/o");
    expect(screen.getByRole("link", { name: /Property Profile/ }).getAttribute("href")).toBe("/scorecard?pin=14313320180000");
    fireEvent.click(screen.getByRole("button", { name: /Ask again/ }));
    expect(onAskAgain).toHaveBeenCalled();
  });

  it("the shared view has no Ask again", () => {
    render(
      <AnsweredOnNote
        createdAt={CREATED}
        note={{ status: "changes", unchecked: [], changes: [{ kind: "overlay", change: "added", layer: "planned_development", name: "PD 12" }] }}
      />,
    );
    expect(screen.queryByRole("button", { name: /Ask again/ })).toBeNull();
    expect(screen.getByTestId("since-then-changes").textContent).toContain("a Planned Development");
  });

  it("says each kind of change in words", () => {
    render(
      <AnsweredOnNote
        createdAt={CREATED}
        note={{
          status: "changes", unchecked: ["overlay:aro_zone"],
          changes: [
            { kind: "standards", field: "far", old: 2.2, new: 3, zone_class: "B3-2" },
            { kind: "amendment", phase: "before_answer", record: "O2026-1", passed_on: "2026-03-25", sections: ["17-3-0400"] },
            { kind: "map_amendment", record: "O2026-9", passed_on: "2026-10-14" },
            { kind: "designation", record: "O2026-3", passed_on: "2026-09-01" },
            { kind: "text_refresh", current_through: "2026-06-17", sections: ["17-3-0400"] },
            { kind: "correction", id: "x", date: "2026-10-02", summary: "We corrected something." },
          ],
        }}
      />,
    );
    const text = screen.getByTestId("since-then-changes").textContent ?? "";
    for (const bit of ["Floor area ratio for B3-2 changed from 2.2 to 3", "did not include that change", "not on the City's zoning map yet",
      "not on the City's landmark map yet", "updated through Jun 17, 2026", "We corrected something.", "couldn't re-check some map layers"]) {
      expect(text).toContain(bit);
    }
  });
});
