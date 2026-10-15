import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

// Chữ hiển thị tiếng Việt phải nằm trong src/i18n/vi.ts (apps/web/AGENTS.md). Component không được viết thẳng.
const VIETNAMESE = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

/** Bỏ chú thích (// và /* *​/, kể cả {/* *​/} trong JSX) để chỉ còn mã và chuỗi. */
export function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "")
    .replace(/\s\/\/ .*$/gm, "");
}

describe("VerifyFlow.tsx không viết thẳng chữ tiếng Việt", () => {
  const file = path.resolve(import.meta.dirname, "VerifyFlow.tsx");
  const source = readFileSync(file, "utf-8");

  it("ngoài chú thích, không còn chữ tiếng Việt có dấu nào", () => {
    const code = stripComments(source);
    const offenders = code
      .split("\n")
      .map((line, i) => ({ line: i + 1, text: line.trim() }))
      .filter(({ text }) => VIETNAMESE.test(text));
    expect(offenders).toEqual([]);
  });

  it("bộ quét tự kiểm: bắt chữ viết thẳng trong JSX và chuỗi, bỏ qua chú thích", () => {
    const bad = stripComments(
      'const a = "Xác minh";\n<p>Hồ sơ</p>\n// Tiếng Việt trong chú thích\n/* đ */',
    );
    expect(bad.split("\n").filter((l) => VIETNAMESE.test(l))).toHaveLength(2);
    const ok = stripComments("// Chú thích có dấu\n{/* nháy màu */}\nconst b = t.flash.start;");
    expect(VIETNAMESE.test(ok)).toBe(false);
  });

  it("mọi chữ hiển thị đi qua đối tượng t (vi.verify)", () => {
    expect(source).toContain("const t = vi.verify;");
    expect(source).toMatch(/\{t\.[a-zA-Z.]+\}/);
  });
});
