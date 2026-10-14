import { describe, expect, it } from "vitest";

import { vi } from "./vi";

describe("vi messages", () => {
  it("không để chữ nhạy cảm trong khu vực người dân", () => {
    const text = JSON.stringify(vi.verify).toLowerCase();
    for (const word of ["giả mạo", "deepfake", "điểm", "score"]) {
      expect(text).not.toContain(word);
    }
  });

  it("mỗi khu vực đều có tiêu đề", () => {
    for (const area of [vi.verify, vi.review, vi.forensic]) {
      expect(area.title.length).toBeGreaterThan(0);
    }
  });
});
