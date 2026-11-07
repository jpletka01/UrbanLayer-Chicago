// Component accessibility check for the new UI (decision Item 75: component axe checks run in CI). jsdom can't
// compute colors, so color-contrast is checked by tokens.contrast.test.ts instead and disabled here.
import axe from "axe-core";

export async function axeViolations(root: Element): Promise<string[]> {
  const result = await axe.run(root, {
    rules: { "color-contrast": { enabled: false }, region: { enabled: false } },
  });
  return result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}
