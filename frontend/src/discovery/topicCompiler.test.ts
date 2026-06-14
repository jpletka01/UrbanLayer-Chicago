import { describe, expect, it } from "vitest";
import { expandTopic } from "./topicCompiler";
import { REG } from "./_fixtures";

describe("expandTopic", () => {
  it("returns the topic's preset predicates (pure copy)", () => {
    const out = expandTopic("vacant_mf", REG);
    expect(out).toEqual({
      land_use: { kind: "enum", values: ["multi_family"] },
      tif: { kind: "flag", value: true },
    });
    // a copy, not the registry object itself
    expect(out).not.toBe(REG.topics[0].presets);
  });

  it("returns {} for an unknown topic", () => {
    expect(expandTopic("nope", REG)).toEqual({});
  });
});
