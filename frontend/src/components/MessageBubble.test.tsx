import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Message } from "../lib/types";
import { MessageBubble } from "./MessageBubble";

// Every [data:x] marker the synthesizer prompt tells the model to emit must
// render as a pill. vacant_buildings and food_inspections used to show up as
// literal "[data:vacant_buildings]" text in answers.
describe("MessageBubble data markers", () => {
  afterEach(cleanup);

  it.each(["crime", "311", "permits", "violations", "business", "vacant_buildings", "food_inspections"])(
    "renders [data:%s] as a pill",
    (source) => {
      const onDataClick = vi.fn();
      const message = { role: "assistant", content: `There were 12 cases [data:${source}] nearby.` } as Message;
      render(<MessageBubble message={message} onDataClick={onDataClick} />);
      expect(screen.queryByText(`[data:${source}]`, { exact: false })).toBeNull();
      fireEvent.click(screen.getByRole("button", { name: "" }));
      expect(onDataClick).toHaveBeenCalledWith(source);
    },
  );
});
