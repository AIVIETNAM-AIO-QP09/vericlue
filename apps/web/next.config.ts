import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  /* config options here */
  // Cho phép điện thoại cùng Wi-Fi và đường hầm cloudflared mở trang dev (runbook chromapulse-lab).
  allowedDevOrigins: ["*.trycloudflare.com", "192.168.*.*", "10.*.*.*", "172.*.*.*"],
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    // Gốc monorepo: cho phép import packages/contracts/chromapulse.json (nguồn chung với API).
    root: path.resolve(import.meta.dirname, "../.."),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
