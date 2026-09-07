import { afterEach, describe, it, expect, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";

import { RangeSlider } from "./RangeSlider";

afterEach(cleanup);

const labels = { minAria: "minimum lot size", maxAria: "maximum lot size" };

function setup(over: Partial<React.ComponentProps<typeof RangeSlider>> = {}) {
  const onChange = vi.fn();
  render(
    <RangeSlider
      domain={[0, 50000]}
      step={100}
      display="number"
      name="lot_size"
      labels={labels}
      onChange={onChange}
      {...over}
    />,
  );
  return { onChange };
}

describe("RangeSlider", () => {
  it("exposes both thumbs as real sliders with distinct labels", () => {
    setup();
    // Native inputs, so they are sliders to the a11y tree for free.
    expect(screen.getAllByRole("slider")).toHaveLength(2);
    expect(screen.getByLabelText("minimum lot size")).toBeTruthy();
    expect(screen.getByLabelText("maximum lot size")).toBeTruthy();
  });

  it("rests unset thumbs at the domain ends", () => {
    setup();
    expect((screen.getByLabelText("minimum lot size") as HTMLInputElement).value).toBe("0");
    expect((screen.getByLabelText("maximum lot size") as HTMLInputElement).value).toBe("50000");
  });

  it("announces formatted values via aria-valuetext, not raw numbers", () => {
    setup({ display: "usd", domain: [0, 5000000], step: 1000, min: 250000 });
    expect(
      screen.getByLabelText("minimum lot size").getAttribute("aria-valuetext"),
    ).toBe("$250,000");
  });

  it("clears a bound that returns to its domain end", () => {
    // "Untouched" must stay distinct from "set to the boundary" — a boundless side is
    // no constraint at all to the evaluator.
    const { onChange } = setup({ min: 5000, max: 40000 });
    fireEvent.change(screen.getByLabelText("minimum lot size"), { target: { value: "0" } });
    expect(onChange).toHaveBeenCalledWith(undefined, 40000);
  });

  it("clamps the min thumb so it cannot cross the max", () => {
    const { onChange } = setup({ min: 1000, max: 20000 });
    fireEvent.change(screen.getByLabelText("minimum lot size"), { target: { value: "45000" } });
    expect(onChange).toHaveBeenCalledWith(20000, 20000);
  });

  it("clamps the max thumb so it cannot cross the min", () => {
    const { onChange } = setup({ min: 10000, max: 20000 });
    fireEvent.change(screen.getByLabelText("maximum lot size"), { target: { value: "500" } });
    expect(onChange).toHaveBeenCalledWith(10000, 10000);
  });

  it("renders one thumb when the filter is bounded on a single side", () => {
    setup({ boundMode: "max" });
    expect(screen.getAllByRole("slider")).toHaveLength(1);
    expect(screen.getByLabelText("maximum lot size")).toBeTruthy();
  });

  it("respects the registry step", () => {
    setup({ step: 0.5, domain: [0, 16], display: "far" });
    expect(screen.getByLabelText("minimum lot size").getAttribute("step")).toBe("0.5");
  });
});
