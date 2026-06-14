import { defineConfig } from "vitest/config";

// Unit/component tests for the Property Discovery frontend. jsdom for the chips component
// test; automatic JSX runtime so test TSX needs no explicit React import.
export default defineConfig({
  esbuild: { jsx: "automatic" },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test-setup.ts"],
  },
});
