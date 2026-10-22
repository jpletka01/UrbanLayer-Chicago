import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { UncheckedRow } from "./UncheckedRow";

afterEach(cleanup);

describe("UncheckedRow — a module says what it couldn't check instead of going quiet", () => {
  it("names what didn't answer and says it isn't a no", () => {
    render(<UncheckedRow labels={["property records", "incentive zones"]} />);
    const row = screen.getByTestId("module-unchecked");
    expect(row.textContent).toContain("Couldn't check today");
    expect(row.textContent).toContain("property records, incentive zones didn't answer");
    expect(row.textContent).toContain("isn't a \"no\"");
    expect(row.querySelector("a")).toBeNull();
  });

  it("offers the official place to look when there is one", () => {
    render(<UncheckedRow labels={["parcel zoning"]} href="https://gisapps.chicago.gov/ZoningMapWeb/" />);
    expect(screen.getByRole("link", { name: /City zoning map/ }).getAttribute("href")).toBe("https://gisapps.chicago.gov/ZoningMapWeb/");
  });

  it("renders nothing when nothing failed", () => {
    const { container } = render(<UncheckedRow labels={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
