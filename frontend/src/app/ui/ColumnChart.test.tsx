// The column chart's on-demand value (decision Item 99): this lot's column speaks by default, a hovered column shows
// its own value, a click keeps it until the same column is clicked again, Escape unpins, and every column is a named
// button for keyboards and screen readers.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe";
import { ColumnChart } from "./ColumnChart";

afterEach(() => cleanup());

const chart = () => render(
  <div className="ui-next">
    <ColumnChart ariaLabel="Assessor's value by year" top={1_000_000} scale={["$1M", "$500K", "$0"]} columns={[
      { key: "2022", tick: "’22", label: "2022", value: 613_340, valueText: "$613K" },
      { key: "2024", tick: "’24", label: "2024", value: 619_000, valueText: "$619K" },
      { key: "2026", tick: "’26", label: "2026", value: 619_000, valueText: "$619K", highlight: true },
    ]} />
  </div>,
);
const callout = () => screen.getByTestId("column-callout").textContent;
const pointer = (el: Element, type: "pointerEnter" | "pointerLeave") => fireEvent[type](el, { pointerType: "mouse" });

describe("ColumnChart", () => {
  it("shows this lot's latest value by default and a hovered column's value on hover", async () => {
    const { container } = chart();
    expect(callout()).toBe("2026 $619K");
    pointer(screen.getByRole("button", { name: "2022: $613K" }), "pointerEnter");
    expect(callout()).toBe("2022 $613K");
    pointer(screen.getByRole("group"), "pointerLeave");
    expect(callout()).toBe("2026 $619K");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("keeps a clicked column's value until the same column is clicked again, or Escape", () => {
    chart();
    const col = screen.getByRole("button", { name: "2022: $613K" });
    fireEvent.click(col);
    expect(col.getAttribute("aria-pressed")).toBe("true");
    pointer(screen.getByRole("button", { name: "2024: $619K" }), "pointerEnter");
    pointer(screen.getByRole("group"), "pointerLeave");
    expect(callout()).toBe("2022 $613K");
    fireEvent.click(col);
    expect(col.getAttribute("aria-pressed")).toBe("false");
    expect(callout()).toBe("2026 $619K");
    fireEvent.click(col);
    fireEvent.keyDown(col, { key: "Escape" });
    expect(col.getAttribute("aria-pressed")).toBe("false");
  });
});
