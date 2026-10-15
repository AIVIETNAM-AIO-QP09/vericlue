import path from "node:path";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@contracts": path.resolve(import.meta.dirname, "../../packages/contracts"),
      "@": path.resolve(import.meta.dirname, "src"),
    },
  },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
