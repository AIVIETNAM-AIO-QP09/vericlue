import { readFileSync, readdirSync, statSync } from "node:fs";
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

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    const isCode = /\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name);
    return isCode && name !== "schema.d.ts" ? [full] : [];
  });
}

describe("không chép cứng màu của bảng ra ngoài config", () => {
  it("mã nguồn trong src/ không chứa hex của bảng màu hay màu nền xám", () => {
    const hexes = [...raw.palette, raw.baseline_color].map((h: string) => h.toLowerCase());
    const src = path.resolve(import.meta.dirname, "../../..");
    const offenders = sourceFiles(src).filter((file) => {
      const text = readFileSync(file, "utf-8").toLowerCase();
      return hexes.some((hex: string) => text.includes(hex));
    });
    expect(offenders.map((f) => path.relative(src, f))).toEqual([]);
  });
});
