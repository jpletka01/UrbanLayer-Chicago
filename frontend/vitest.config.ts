import { defineConfig } from "vitest/config";

// Unit/component tests for the Property Discovery frontend. jsdom for the chips component
// test; automatic JSX runtime so test TSX needs no explicit React import.
export default defineConfig({
  esbuild: { jsx: "automatic" },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test-setup.ts"],
    // 5 s default is too tight for the render + axe tests under load: NeighborhoodTab took 6.7 s with four
    // suites at once, and its axe run then leaked into the next test ("Axe is already running").
    testTimeout: 20_000,
  },
});
