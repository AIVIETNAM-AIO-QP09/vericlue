import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { chromaPulseConfig } from "./config";

// Cùng file mà API đọc (services/api/.../core/chromapulse_config.py): nguồn duy nhất.
const FILE = path.resolve(
  import.meta.dirname,
  "../../../../../../packages/contracts/chromapulse.json",
);
const raw = JSON.parse(readFileSync(FILE, "utf-8"));

describe("chromaPulseConfig đọc đúng packages/contracts/chromapulse.json", () => {
  it("mọi trường khớp file", () => {
    expect(chromaPulseConfig).toEqual({
      version: raw.version,
      palette: raw.palette,
      baselineColor: raw.baseline_color,
      steps: raw.steps,
      baselineMs: raw.baseline_ms,
      tailMs: raw.tail_ms,
      holdMinMs: raw.hold_ms.min,
      holdMaxMs: raw.hold_ms.max,
      transitionMs: raw.transition_ms,
      maxChangesPerSecond: raw.limits.max_changes_per_second,
      maxLuminanceSpread: raw.limits.max_luminance_spread,
      maxRedShare: raw.limits.max_red_share,
    });
  });

  it("không có bảng màu hay nhịp nào chép cứng ngoài file chung", () => {
    // config.ts phải import file chung, không tự khai báo hex hay số nhịp.
    const source = readFileSync(path.resolve(import.meta.dirname, "config.ts"), "utf-8");
    expect(source).toContain("@contracts/chromapulse.json");
    expect(source).not.toMatch(/#[0-9a-f]{6}/i);
  });
});
