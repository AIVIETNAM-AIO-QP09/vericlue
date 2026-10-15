import { describe, expect, it } from "vitest";

import { vi } from "@/i18n/vi";

import type { UnsupportedReason } from "./flow";
import { qualityMessage, unsupportedReason } from "./messages";
import { GUIDANCE_PRIORITY, type QualityGuidance } from "./quality";

// Cùng danh sách chữ cấm với messages.test.ts: người dân không thấy điểm số hay chữ nói về giả mạo.
const FORBIDDEN = [
  /giả mạo/,
  /deepfake/,
  /score/,
  /xác suất/,
  /điểm\s*(số|tin cậy|rủi ro)/,
  /fake/,
  /spoof/,
  /attack/,
  /tấn công/,
  /gian lận/,
  /prob/,
  /từ chối/,
  /thất bại/,
];

const REASONS: UnsupportedReason[] = ["low_fps", "low_resolution", "no_frame_callback"];

describe("chỉ dẫn của cổng chất lượng", () => {
  it("mỗi chỉ dẫn có đúng một câu, không rỗng, không trùng nhau", () => {
    const texts = GUIDANCE_PRIORITY.map((g) => qualityMessage(g));
    for (const text of texts) expect(text.trim().length).toBeGreaterThan(0);
    expect(new Set(texts).size).toBe(GUIDANCE_PRIORITY.length);
  });

  it("vi.verify.quality có đúng các khóa của danh sách chỉ dẫn (không thừa, không thiếu)", () => {
    expect(Object.keys(vi.verify.quality).sort()).toEqual([...GUIDANCE_PRIORITY].sort());
  });

  it("chỉ nói về chất lượng: không có chữ cấm nào", () => {
    const texts = [
      ...GUIDANCE_PRIORITY.map((g) => qualityMessage(g)),
      qualityMessage(null),
      vi.verify.framing.loading,
    ];
    for (const text of texts) {
      for (const pattern of FORBIDDEN) expect(text.toLowerCase()).not.toMatch(pattern);
    }
  });

  it("hai câu có trong tài liệu đúng nguyên văn", () => {
    expect(qualityMessage("MOVE_CLOSER")).toBe("Lại gần hơn");
    expect(qualityMessage("LOW_LIGHT")).toBe("Ra chỗ sáng hơn");
  });

  it("quá sáng KHÔNG bị nói thành 'ra chỗ sáng hơn' (chỉ dẫn ngược nghĩa)", () => {
    const tooBright = qualityMessage("TOO_BRIGHT");
    expect(tooBright).toBe("Tránh nắng chiếu thẳng vào mặt");
    expect(tooBright).not.toBe(qualityMessage("LOW_LIGHT"));
    expect(tooBright.toLowerCase()).not.toContain("sáng hơn");
  });

  it("khung đạt (null) có câu riêng, khác mọi chỉ dẫn", () => {
    const ok = qualityMessage(null);
    expect(ok.length).toBeGreaterThan(0);
    for (const g of GUIDANCE_PRIORITY as readonly QualityGuidance[]) {
      expect(ok).not.toBe(qualityMessage(g));
    }
  });
});

describe("thiết bị hoặc trình duyệt chưa đáp ứng", () => {
  it("mỗi lý do có một câu riêng, không rỗng", () => {
    const texts = REASONS.map((r) => unsupportedReason(r));
    for (const text of texts) expect(text.trim().length).toBeGreaterThan(0);
    expect(new Set(texts).size).toBe(REASONS.length);
  });

  it("nêu đúng các con số của tài liệu (15 khung/giây, 640 x 480)", () => {
    expect(unsupportedReason("low_fps")).toContain("15");
    expect(unsupportedReason("low_resolution")).toContain("640");
    expect(unsupportedReason("low_resolution")).toContain("480");
  });

  it("không đổ lỗi cho người dùng và khuyên thử thiết bị/trình duyệt khác", () => {
    expect(vi.verify.deviceUnsupported.title).toContain("Thiết bị hoặc trình duyệt chưa đáp ứng");
    expect(vi.verify.deviceUnsupported.body).toContain("trình duyệt hoặc thiết bị khác");
    const all = [
      vi.verify.deviceUnsupported.title,
      vi.verify.deviceUnsupported.body,
      ...REASONS.map((r) => unsupportedReason(r)),
    ];
    for (const text of all) {
      for (const pattern of FORBIDDEN) expect(text.toLowerCase()).not.toMatch(pattern);
    }
  });
});
