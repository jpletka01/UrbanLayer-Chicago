import { describe, expect, it } from "vitest";
import i18n from "./i18n";
import { answerSentence, blockersFor } from "./answerSentence";
import type { ScorecardVerdict, VerdictSignals } from "./scorecardVerdict";
import type { ScorecardResponse } from "./api";

const t = (key: string, opts?: Record<string, unknown>) => i18n.t(key, { ns: "pages", ...opts }) as string;

function verdict(signals: Partial<VerdictSignals>, category: ScorecardVerdict["category"] = "constrained"): ScorecardVerdict {
  return {
    category, headline: "x", reasons: [], nextStep: { kind: "chat", label: "x" }, confidence: "high", caveats: [],
    signals: {
      allowedFar: null, existingFar: null, capacityRatio: null, capacityBand: "unknown", bldgAreaLowConfidence: false,
      incentiveStrength: "none", incentiveCount: 0, tifBalance: 0, bonusFlags: [], todBenefits: null, adu: null,
      frictionFlags: [], frictionLevel: "low", neutralFlags: [], zoneClass: null, flagSignals: [],
      appealNearbyWins: 0, appealNearbyMedianPct: null,
      ...signals,
    },
  };
}
const data = (over: Record<string, unknown> = {}) => ({ context: { unit_yield: null, property: null, ...over } }) as unknown as ScorecardResponse;

describe("answer sentence", () => {
  it("states headroom, units and the biggest blocker in one sentence (1601 N Milwaukee)", () => {
    const v = verdict({ zoneClass: "B3-2", allowedFar: 2.2, existingFar: 1.31, capacityRatio: 2.2 / 1.31, capacityBand: "modest", frictionFlags: ["historic", "landmark_dist"] });
    expect(answerSentence(data({ unit_yield: { units: 11 } }), v, t)).toBe(
      "B3-2 allows about 1.7× today's floor area, up to 11 units by lot area; it is in a landmark district, so new construction needs Commission approval.",
    );
  });

  it("never states a ratio the verdict doesn't trust", () => {
    const v = verdict({ zoneClass: "RS-3", allowedFar: 0.9, existingFar: 0.5, capacityRatio: 1.8, capacityBand: "unknown", bldgAreaLowConfidence: true });
    expect(answerSentence(data(), v, t)).toBe("RS-3 allows a floor-area ratio of 0.9.");
  });

  it("says a planned development has no table maximum", () => {
    const v = verdict({ zoneClass: "PD 853" }, "entitlement_defined");
    expect(answerSentence(data(), v, t)).toBe("PD 853 sets its own rules by ordinance; there is no table maximum.");
  });

  it("names a nominal assessment first, before any overlay", () => {
    const v = verdict({ zoneClass: "PD 853", frictionFlags: ["pd_overlay"] }, "entitlement_defined");
    const d = data({ property: { nominal_assessment: true } });
    expect(blockersFor(d, v)).toEqual(["nominal", "pd_overlay"]);
    expect(answerSentence(d, v, t)).toMatch(/; it carries a nominal assessment, so it may not be a buildable lot on its own\.$/);
  });

  it("covers a lot that is mostly unbuilt, one at its limit, and a missing district", () => {
    expect(answerSentence(data({ unit_yield: { units: 1 } }), verdict({ zoneClass: "RT-4", allowedFar: 1.2, existingFar: 0.1, capacityBand: "vacant_or_teardown" }), t))
      .toBe("RT-4 allows a floor-area ratio of 1.2 on a lot that is mostly unbuilt, up to 1 unit by lot area.");
    expect(answerSentence(data(), verdict({ zoneClass: "DC-16", allowedFar: 16, existingFar: 15.2, capacityRatio: 16 / 15.2, capacityBand: "at_cap" }), t))
      .toBe("DC-16 is built to about its limit (95% of the allowed floor area).");
    expect(answerSentence(data(), verdict({}), t)).toBe("The zoning district couldn't be checked today.");
  });

  it("never says 'you can build'", () => {
    const v = verdict({ zoneClass: "B3-2", allowedFar: 2.2, existingFar: 1, capacityRatio: 2.2, capacityBand: "high" });
    expect(answerSentence(data({ unit_yield: { units: 11 } }), v, t).toLowerCase()).not.toContain("you can build");
  });
});
