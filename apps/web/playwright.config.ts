// Bài thử trình duyệt thật (Chromium) cho luồng /verify. Chạy: `npm run test:e2e` (xem README web).
// Chromium dùng camera GIẢ (--use-fake-device-for-media-stream), tự cho phép camera. Khởi động hai server:
// API mock (SQLite tạm, không cần Docker/PostgreSQL) và web (next dev), cổng riêng để không tranh cổng 3000/8000/5432.

import os from "node:os";
import path from "node:path";

import { defineConfig } from "@playwright/test";

const WEB_PORT = 3202;
const API_PORT = 8002;
const WEB_URL = `http://localhost:${WEB_PORT}`;
const API_URL = `http://localhost:${API_PORT}`;

// Chạy từ apps/web (npm run test:e2e), nên gốc repo là hai cấp trên.
const repoRoot = path.resolve(process.cwd(), "../..");
const tmp = os.tmpdir();
const sqlitePath = path.join(tmp, "vericlue-e2e.db").split(path.sep).join("/");

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 45_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: WEB_URL,
    browserName: "chromium",
    permissions: ["camera"],
    launchOptions: {
      args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
    },
    trace: "retain-on-failure",
  },
  webServer: [
    {
      // Migration rồi mới chạy API; DB SQLite tạm (README API: SQLite chỉ để thử/test độc lập).
      command: `uv run alembic -c services/api/alembic.ini upgrade head && uv run uvicorn vericlue_api.main:app --app-dir services/api/src --port ${API_PORT}`,
      cwd: repoRoot,
      url: `${API_URL}/healthz`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        ...(process.env as Record<string, string>),
        DATABASE_URL: `sqlite:///${sqlitePath}`,
        USE_MOCK_MODELS: "true",
        API_CORS_ORIGINS: WEB_URL,
        MEDIA_DIR: path.join(tmp, "vericlue-e2e-media"),
      },
    },
    {
      command: `npm run dev -- -p ${WEB_PORT}`,
      cwd: process.cwd(),
      url: `${WEB_URL}/verify`,
      timeout: 180_000,
      reuseExistingServer: false,
      env: {
        ...(process.env as Record<string, string>),
        NEXT_PUBLIC_API_URL: API_URL,
      },
    },
  ],
});
