import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Chips } from "./chips";
import { REG } from "./_fixtures";
import type { ChipItem } from "./draftModel";

afterEach(cleanup);

const items: ChipItem[] = [
  { id: "land_use", predicate: { kind: "enum", values: ["multi_family"] }, state: "applied" },
  { id: "tif", predicate: { kind: "flag", value: true }, state: "applied" },
];

const noop = () => {};

describe("Chips (a control surface rendered from the draft)", () => {
  it("renders one chip per filter", () => {
    render(<Chips items={items} registry={REG} onRemove={noop} onRestore={noop} />);
    expect(screen.getByText("Property use: Multifamily")).toBeTruthy();
    expect(screen.getByText("TIF district")).toBeTruthy();
  });

  it("remove fires with the filterId", () => {
    const onRemove = vi.fn();
    render(<Chips items={items} registry={REG} onRemove={onRemove} onRestore={noop} />);
    fireEvent.click(screen.getByLabelText("Remove TIF district filter"));
    expect(onRemove).toHaveBeenCalledWith("tif");
  });

  it("renders neighborhood regions by community-area name, not raw id", () => {
    render(
      <Chips
        items={[{ id: "neighborhood", predicate: { kind: "region", regions: ["neighborhood:24"] }, state: "applied" }]}
        registry={REG}
        onRemove={noop}
        onRestore={noop}
      />,
    );
    expect(screen.getByText(/West Town/)).toBeTruthy();
    expect(screen.queryByText(/neighborhood:24/)).toBeNull();
  });

  it("renders nothing when there are no filters", () => {
    const { container } = render(<Chips items={[]} registry={REG} onRemove={noop} onRestore={noop} />);
    expect(container.firstChild).toBeNull();
  });

  it("marks an unapplied chip with a dashed outline and a screen-reader note", () => {
    render(
      <Chips
        items={[
          { id: "tif", predicate: { kind: "flag", value: true }, state: "added" },
          { id: "land_use", predicate: { kind: "enum", values: ["residential"] }, state: "applied" },
        ]}
        registry={REG}
        onRemove={noop}
        onRestore={noop}
      />,
    );
    const pending = screen.getByText("TIF district").closest("span.rounded-full")!;
    const applied = screen.getByText("Property use: Residential").closest("span.rounded-full")!;
    expect(pending.className).toContain("border-dashed");
    expect(applied.className).not.toContain("border-dashed");
    expect(screen.getByText(/not applied yet/)).toBeTruthy();
  });

  it("keeps a removed chip visible, struck through, and restores it with one click", () => {
    const onRestore = vi.fn();
    const onRemove = vi.fn();
    render(
      <Chips
        items={[{ id: "tif", predicate: { kind: "flag", value: true }, state: "removed" }]}
        registry={REG}
        onRemove={onRemove}
        onRestore={onRestore}
      />,
    );
    const restore = screen.getByRole("button", { name: "Restore TIF district filter" });
    expect(restore.className).toContain("line-through");
    expect(screen.queryByLabelText("Remove TIF district filter")).toBeNull();
    fireEvent.click(restore);
    expect(onRestore).toHaveBeenCalledWith("tif");
    expect(onRemove).not.toHaveBeenCalled();
  });
});
