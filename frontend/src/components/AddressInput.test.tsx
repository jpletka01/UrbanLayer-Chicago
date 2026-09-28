import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/api", () => ({
  getAutocomplete: vi.fn(async () => [{ address: "2130 N HOYNE AVE, CHICAGO, IL, 60647" }]),
}));

import { AddressInput } from "./AddressInput";

async function typeAndEnter(text: string, onSubmit: (a: string) => void) {
  render(<AddressInput onSubmit={onSubmit} placeholder="Enter an address" />);
  const input = screen.getByPlaceholderText("Enter an address");
  fireEvent.change(input, { target: { value: text } });
  await waitFor(() => expect(screen.getByText(/HOYNE AVE/)).toBeTruthy(), { timeout: 2000 });
  fireEvent.keyDown(input, { key: "Enter" });
}

describe("AddressInput Enter with the dropdown open", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(cleanup);

  it("takes the top suggestion when it's the same house number (typo fix)", async () => {
    const onSubmit = vi.fn();
    await typeAndEnter("2130 N Hoyn Ave", onSubmit);
    expect(onSubmit).toHaveBeenCalledWith("2130 N HOYNE AVE, CHICAGO, IL, 60647");
  });

  it("keeps what was typed when the top suggestion is a different address", async () => {
    const onSubmit = vi.fn();
    await typeAndEnter("2140 N Hoyne Ave", onSubmit);
    // keyDown alone doesn't submit the form in jsdom; the typed text is only sent
    // on form submit, so the suggestion must NOT have been taken.
    expect(onSubmit).not.toHaveBeenCalledWith("2130 N HOYNE AVE, CHICAGO, IL, 60647");
  });
});
