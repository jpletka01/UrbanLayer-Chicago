import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Chips } from "./chips";
import { REG } from "./_fixtures";
import type { CQS } from "./types";

afterEach(cleanup);

const cqs: CQS = {
  filters: {
    land_use: { predicate: { kind: "enum", values: ["multi_family"] }, source: "user" },
    tif: { predicate: { kind: "flag", value: true }, source: "text" },
  },
  sort: { key: "pin", dir: "asc" },
  scope: { mode: "all" },
  meta: {},
};

describe("Chips (renders from response.cqs — INV-4)", () => {
  it("renders one chip per applied filter", () => {
    render(<Chips cqs={cqs} registry={REG} onRemove={() => {}} />);
    expect(screen.getByText("Property use: Multifamily")).toBeTruthy();
    expect(screen.getByText("TIF district")).toBeTruthy();
  });

  it("remove fires the re-issue callback with the canonical filterId", () => {
    const onRemove = vi.fn();
    render(<Chips cqs={cqs} registry={REG} onRemove={onRemove} />);
    fireEvent.click(screen.getByLabelText("Remove TIF district filter"));
    expect(onRemove).toHaveBeenCalledWith("tif");
  });

  it("renders neighborhood regions by community-area name, not raw id", () => {
    const c: CQS = {
      filters: {
        neighborhood: { predicate: { kind: "region", regions: ["neighborhood:24"] }, source: "user" },
      },
      sort: { key: "pin", dir: "asc" },
      scope: { mode: "all" },
      meta: {},
    };
    render(<Chips cqs={c} registry={REG} onRemove={() => {}} />);
    expect(screen.getByText(/West Town/)).toBeTruthy();
    expect(screen.queryByText(/neighborhood:24/)).toBeNull();
  });

  it("renders nothing when there are no filters", () => {
    const { container } = render(
      <Chips
        cqs={{ filters: {}, sort: { key: "pin", dir: "asc" }, scope: { mode: "all" }, meta: {} }}
        registry={REG}
        onRemove={() => {}}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});
