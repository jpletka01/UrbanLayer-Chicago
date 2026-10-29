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

  it("without onEdit the label is plain text; with it the label is a button that opens that filter's editor", () => {
    const { unmount } = render(<Chips items={items} registry={REG} onRemove={noop} onRestore={noop} />);
    expect(screen.queryByRole("button", { name: /^Edit / })).toBeNull();
    unmount();
    const onEdit = vi.fn();
    render(<Chips items={items} registry={REG} onRemove={noop} onRestore={noop} onEdit={onEdit} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit TIF district" }));
    expect(onEdit).toHaveBeenCalledWith("tif");
  });

  it("clicking the label edits; clicking the x still removes, and neither triggers the other", () => {
    const onEdit = vi.fn();
    const onRemove = vi.fn();
    render(<Chips items={items} registry={REG} onRemove={onRemove} onRestore={noop} onEdit={onEdit} />);
    fireEvent.click(screen.getByLabelText("Remove TIF district filter"));
    expect(onRemove).toHaveBeenCalledWith("tif");
    expect(onEdit).not.toHaveBeenCalled();
  });

  it("a removed (struck-through) chip restores instead of editing", () => {
    const onRestore = vi.fn();
    const onEdit = vi.fn();
    render(
      <Chips
        items={[{ id: "tif", predicate: { kind: "flag", value: true }, state: "removed" }]}
        registry={REG} onRemove={noop} onRestore={onRestore} onEdit={onEdit}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Restore TIF district filter/ }));
    expect(onRestore).toHaveBeenCalledWith("tif");
    expect(onEdit).not.toHaveBeenCalled();
  });

  it("renders trailing content (the Add filter button) in the same row, even with no chips", () => {
    render(<Chips items={[]} registry={REG} onRemove={noop} onRestore={noop}><button type="button">+ Add</button></Chips>);
    expect(screen.getByRole("button", { name: "+ Add" })).toBeTruthy();
  });

  it("the upside chip says it is a heuristic (unless it is pending, when the pending note wins)", () => {
    const upside: ChipItem = { id: "upside_score", predicate: { kind: "range", min: 40 }, state: "applied" };
    const { container, rerender } = render(<Chips items={[upside]} registry={REG} onRemove={noop} onRestore={noop} />);
    expect(container.querySelector('[title*="not an appraisal"]')).not.toBeNull();
    rerender(<Chips items={[{ ...upside, state: "added" }]} registry={REG} onRemove={noop} onRestore={noop} />);
    expect(container.querySelector('[title*="not an appraisal"]')).toBeNull();
    expect(container.querySelector('[title*="Not applied yet"]')).not.toBeNull();
  });
});
