import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PieSlice } from "../../lib/analytics";
import { DateRangeSlider } from "./DateRangeSlider";
import { PieChart } from "./PieChart";

// Regression: both components returned early on empty data *before* some of
// their hooks, so going from empty to populated threw "Rendered more hooks
// than during the previous render" and took down the panel.

describe("charts that mount empty and then receive data", () => {
  it("PieChart", () => {
    const slices = [
      { label: "Theft", value: 10, color: "#f90" },
      { label: "Battery", value: 5, color: "#999" },
    ] as PieSlice[];
    const { rerender, container } = render(<PieChart slices={[]} />);
    expect(() => rerender(<PieChart slices={slices} />)).not.toThrow();
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("DateRangeSlider", () => {
    const noop = () => {};
    const { rerender, container } = render(
      <DateRangeSlider minDate={0} maxDate={0} startDate={0} endDate={0} onChange={noop} />,
    );
    expect(() =>
      rerender(
        <DateRangeSlider minDate={0} maxDate={1000} startDate={0} endDate={1000} onChange={noop} />,
      ),
    ).not.toThrow();
    expect(container.querySelectorAll('input[type="range"]').length).toBe(2);
  });
});
