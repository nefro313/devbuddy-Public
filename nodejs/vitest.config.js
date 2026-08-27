import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.{test,spec}.?(c|m)[jt]s?(x)", "tests/**/test_*.?(c|m)[jt]s?(x)"],
    testTimeout: 30_000,  // LLM calls can be slow
    hookTimeout: 30_000,
  },
});
