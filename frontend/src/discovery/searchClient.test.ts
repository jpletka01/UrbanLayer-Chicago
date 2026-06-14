import { describe, expect, it } from "vitest";
import { buildRequest } from "./searchClient";
import { REG } from "./_fixtures";
import type { PanelState } from "./types";

describe("buildRequest", () => {
  it("compiles the panel and attaches the registry version; omits empties", () => {
    const panelState: PanelState = {
      land_use: { kind: "enum", values: ["residential"] },
      overlay: { kind: "enum", values: [] }, // invalid → dropped by compilePanel
    };
    const req = buildRequest(
      { panelState, text: "   ", sort: { key: "pin", dir: "asc" }, scope: { mode: "all" } },
      REG,
    );
    expect(req).toEqual({
      userFilters: { land_use: { kind: "enum", values: ["residential"] } },
      registryVersion: "v1",
      sort: { key: "pin", dir: "asc" },
    });
    expect(req.text).toBeUndefined(); // blank text omitted
    expect(req.scope).toBeUndefined(); // mode:"all" omitted
  });

  it("carries text and topicId when present", () => {
    const req = buildRequest({ panelState: {}, text: "tif", topicId: "vacant_mf" }, REG);
    expect(req.text).toBe("tif");
    expect(req.topicId).toBe("vacant_mf");
  });
});
