import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.{test,spec}.?(c|m)[jt]s?(x)", "tests/**/test_*.?(c|m)[jt]s?(x)"],
    testTimeout: 120_000,  // LLM calls can be slow with some models/providers
    hookTimeout: 30_000,
  },
});
