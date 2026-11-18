// Suggest a correction (decision Item 129 §1, PR 3): the form's rules, the laptop dialog and the phone sheet, the toast,
// the pencil turning into a check, and a 429 keeping what was typed. The server call is mocked; nothing leaves the test.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axeViolations } from "../test/axe";
import { ToastHost, TOAST_MS } from "../ui/Toast";
import {
  EMPTY_FORM, SuggestCorrection, chipsFor, formReady, resetCorrectionsSent, toBody, toggleChip, type CorrectionForm,
} from "./SuggestCorrection";

const api = vi.hoisted(() => ({ sendLotCorrection: vi.fn() }));
vi.mock("../../lib/api", () => ({ sendLotCorrection: api.sendLotCorrection }));

beforeEach(() => { resetCorrectionsSent(); api.sendLotCorrection.mockReset(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

const f = (over: Partial<CorrectionForm>): CorrectionForm => ({ ...EMPTY_FORM, ...over });

describe("the form's rules", () => {
  it("allows several chips; no building now clears stories and floor area, and either clears it", () => {
    let x = toggleChip(toggleChip(EMPTY_FORM, "stories"), "condo");
    expect(x.chips).toEqual(["stories", "condo"]);
    x = toggleChip(toggleChip(x, "area"), "gone");
    expect(x.chips).toEqual(["condo", "gone"]);
    x = toggleChip(x, "stories");
    expect(x.chips).toEqual(["condo", "stories"]);
    expect(toggleChip(x, "stories").chips).toEqual(["condo"]);
  });

  it("sends only once something is picked, with a count for Stories and a direction for Floor area", () => {
    expect(formReady(EMPTY_FORM)).toBe(false);
    expect(formReady(f({ chips: ["other"] }))).toBe(true);
    expect(formReady(f({ chips: ["stories"] }))).toBe(false);
    expect(formReady(f({ chips: ["stories"], stories: "20" }))).toBe(true);
    expect(formReady(f({ chips: ["stories"], stories: "0" }))).toBe(false);
    expect(formReady(f({ chips: ["stories"], stories: "151" }))).toBe(false);
    expect(formReady(f({ chips: ["area"] }))).toBe(false);
    expect(formReady(f({ chips: ["area"], area: "low" }))).toBe(true);
  });

  it("builds the body with only what the chips need, the note trimmed and capped", () => {
    expect(toBody("1433103011", f({ chips: ["condo"], stories: "4", area: "high", note: "   " })))
      .toEqual({ pin: "1433103011", kinds: ["condo"] });
    expect(toBody("1433103011", f({ chips: ["stories", "area", "other"], stories: "20", area: "low", note: `  ${"x".repeat(300)}` })))
      .toEqual({ pin: "1433103011", kinds: ["stories", "area", "other"], stories: 20, area_dir: "low", note: "x".repeat(280) });
  });

  it("asks a lot we show empty whether there's a building, and contradicts what we show about a condo", () => {
    expect(chipsFor({ hasBuilding: true, condo: false }).map(([, k]) => k))
      .toEqual(["chips.stories", "chips.area", "chips.gone", "chips.isCondo", "chips.other"]);
    expect(chipsFor({ hasBuilding: false, condo: true }).map(([c, k]) => `${c}:${k}`))
      .toEqual(["gone:chips.there", "condo:chips.notCondo", "other:chips.other"]);
  });
});

function mount(phone = false) {
  return render(
    <div className="ui-next">
      <SuggestCorrection pin10="1433103011" title="642 W Belden Ave" hasBuilding condo={false} phone={phone} />
      <ToastHost />
    </div>,
  );
}

describe("the laptop dialog", () => {
  it("the pencil is named, opens the question with the address, and passes axe", async () => {
    const { baseElement } = mount();
    const pencil = screen.getByTestId("correction-open");
    expect(pencil.getAttribute("aria-label")).toBe("Suggest a correction");
    fireEvent.click(pencil);
    const dialog = await screen.findByTestId("correction-dialog");
    expect(dialog.textContent).toContain("What's wrong with this building?");
    expect(dialog.textContent).toContain("642 W Belden Ave");
    expect(dialog.hasAttribute("data-sheet")).toBe(false);
    expect(await axeViolations(baseElement)).toEqual([]);
  });

  it("Stories focuses a number field; Send waits for a count; sent = toast, check, and the server got the body", async () => {
    api.sendLotCorrection.mockResolvedValue("sent");
    mount();
    fireEvent.click(screen.getByTestId("correction-open"));
    const send = await screen.findByTestId("correction-send");
    expect((send as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Stories" }));
    const field = screen.getByTestId("correction-stories") as HTMLInputElement;
    expect(document.activeElement).toBe(field);
    expect(field.inputMode).toBe("numeric");
    expect((send as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(field, { target: { value: "2a0" } });
    expect(field.value).toBe("20");
    fireEvent.change(screen.getByTestId("correction-note"), { target: { value: " A 20-story tower. " } });
    fireEvent.click(send);
    await waitFor(() => expect(screen.queryByTestId("correction-dialog")).toBeNull());
    expect(api.sendLotCorrection).toHaveBeenCalledWith({ pin: "1433103011", kinds: ["stories"], stories: 20, note: "A 20-story tower." });
    expect(screen.getByTestId("toast").textContent).toContain("Thanks, we'll review it.");
    expect(screen.getByTestId("correction-sent").querySelector("[aria-label]")!.getAttribute("aria-label")).toBe("Correction sent, in review");
    expect(screen.queryByTestId("correction-open")).toBeNull();
  });

  it("Floor area asks a direction; Other puts the cursor in the note", async () => {
    mount();
    fireEvent.click(screen.getByTestId("correction-open"));
    await screen.findByTestId("correction-dialog");
    fireEvent.click(screen.getByRole("button", { name: "Floor area" }));
    expect((screen.getByTestId("correction-send") as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Too low" }));
    expect(screen.getByRole("button", { name: "Too low" }).getAttribute("aria-pressed")).toBe("true");
    expect((screen.getByTestId("correction-send") as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Other" }));
    expect(document.activeElement).toBe(screen.getByTestId("correction-note"));
  });

  it("a 429 says too many reports today and keeps what was typed", async () => {
    api.sendLotCorrection.mockResolvedValue("too_many");
    mount();
    fireEvent.click(screen.getByTestId("correction-open"));
    await screen.findByTestId("correction-dialog");
    fireEvent.click(screen.getByRole("button", { name: "It's a condo" }));
    fireEvent.change(screen.getByTestId("correction-note"), { target: { value: "Twelve units." } });
    fireEvent.click(screen.getByTestId("correction-send"));
    expect((await screen.findByTestId("correction-error")).textContent).toBe("Too many reports today");
    expect(screen.getByRole("button", { name: "It's a condo" }).getAttribute("aria-pressed")).toBe("true");
    expect((screen.getByTestId("correction-note") as HTMLTextAreaElement).value).toBe("Twelve units.");
    expect(screen.getByTestId("correction-open")).toBeTruthy();
  });

  it("Cancel closes without sending, and focus goes back to the pencil", async () => {
    mount();
    const pencil = screen.getByTestId("correction-open");
    fireEvent.click(pencil);
    await screen.findByTestId("correction-dialog");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByTestId("correction-dialog")).toBeNull());
    expect(api.sendLotCorrection).not.toHaveBeenCalled();
    await waitFor(() => expect(document.activeElement).toBe(pencil));
  });
});

describe("the phone sheet", () => {
  it("opens as a sheet; dragging the handle down past 120 px closes it, less doesn't", async () => {
    const { baseElement } = mount(true);
    fireEvent.click(screen.getByTestId("correction-open"));
    const sheet = await screen.findByTestId("correction-dialog");
    expect(sheet.hasAttribute("data-sheet")).toBe(true);
    expect(await axeViolations(baseElement)).toEqual([]);
    const handle = screen.getByTestId("correction-handle");
    fireEvent.pointerDown(handle, { clientY: 100 });
    fireEvent.pointerMove(handle, { clientY: 180 });
    fireEvent.pointerUp(handle, { clientY: 180 });
    expect(screen.getByTestId("correction-dialog")).toBeTruthy();
    fireEvent.pointerDown(handle, { clientY: 100 });
    fireEvent.pointerUp(handle, { clientY: 240 });
    await waitFor(() => expect(screen.queryByTestId("correction-dialog")).toBeNull());
  });
});

describe("the toast", () => {
  it("goes after 4 seconds", async () => {
    api.sendLotCorrection.mockResolvedValue("sent");
    mount();
    fireEvent.click(screen.getByTestId("correction-open"));
    await screen.findByTestId("correction-dialog");
    fireEvent.click(screen.getByRole("button", { name: "Other" }));
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fireEvent.click(screen.getByTestId("correction-send"));
    await waitFor(() => expect(screen.getByTestId("toast").textContent).toContain("Thanks"));
    act(() => { vi.advanceTimersByTime(TOAST_MS + 50); });
    expect(screen.getByTestId("toast").textContent).toBe("");
  });
});
