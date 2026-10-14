import { describe, expect, it } from "vitest";

import { vi } from "./vi";

// Chặn điểm số và chữ "giả mạo", nhưng không chặn oan từ thường như "địa điểm".
const FORBIDDEN = [/giả mạo/, /deepfake/, /score/, /xác suất/, /điểm\s*(số|tin cậy|rủi ro)/];

describe("vi messages", () => {
  it("không để chữ nhạy cảm trong khu vực người dân", () => {
    const text = JSON.stringify(vi.verify).toLowerCase();
    for (const pattern of FORBIDDEN) {
      expect(text).not.toMatch(pattern);
    }
  });

  it('bộ chặn không chặn oan "địa điểm" nhưng vẫn chặn "điểm số"', () => {
    const blocked = (s: string) => FORBIDDEN.some((p) => p.test(s));
    expect(blocked("chọn địa điểm sáng")).toBe(false);
    expect(blocked("điểm số của bạn")).toBe(true);
    expect(blocked("giả mạo")).toBe(true);
  });

  it("mỗi khu vực đều có tiêu đề", () => {
    for (const area of [vi.verify, vi.review, vi.forensic]) {
      expect(area.title.length).toBeGreaterThan(0);
    }
  });
});
