import { describe, expect, it } from "vitest";

import { vi } from "@/i18n/vi";

import { RETRY_HINTS, type CameraProblem, type ErrorKind } from "./flow";
import { cameraMessage, errorMessage, retryMessage } from "./messages";

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
];

const ALL_KINDS: ErrorKind[] = [
  "network",
  "session",
  "conflict",
  "tooLarge",
  "invalid",
  "server",
  "unexpected",
  "stopped",
  "interrupted",
];

function collectStrings(value: unknown, out: string[] = []): string[] {
  if (typeof value === "string") out.push(value);
  else if (Array.isArray(value)) for (const item of value) collectStrings(item, out);
  else if (typeof value === "object" && value !== null) {
    for (const item of Object.values(value)) collectStrings(item, out);
  }
  return out;
}

describe("quét chuỗi vi.verify", () => {
  const strings = collectStrings(vi.verify);

  it("gom được nhiều chuỗi (quét không rỗng)", () => {
    expect(strings.length).toBeGreaterThan(40);
  });

  it("bộ quét bắt được chữ cấm (kiểm chứng chính nó)", () => {
    const blocked = (s: string) => FORBIDDEN.some((p) => p.test(s.toLowerCase()));
    expect(blocked("Điểm số của bạn")).toBe(true);
    expect(blocked("Ảnh giả mạo")).toBe(true);
    expect(blocked("Fake face")).toBe(true);
    expect(blocked("chọn địa điểm sáng")).toBe(false);
  });

  it("không chuỗi nào khớp mẫu cấm", () => {
    const hits = strings.filter((s) => FORBIDDEN.some((p) => p.test(s.toLowerCase())));
    expect(hits).toEqual([]);
  });
});

describe("errorMessage", () => {
  it("có đủ 9 loại", () => {
    expect(ALL_KINDS).toHaveLength(9);
  });

  it.each(ALL_KINDS)("%s có câu không rỗng", (kind) => {
    expect(errorMessage(kind).trim().length).toBeGreaterThan(0);
  });

  it("mỗi loại có câu khác nhau", () => {
    const messages = ALL_KINDS.map(errorMessage);
    expect(new Set(messages).size).toBe(ALL_KINDS.length);
  });
});

describe("retryMessage", () => {
  const FORBIDDEN_IN_HINT = ["giả", "xác minh thất bại", "từ chối"];

  it.each(RETRY_HINTS.map((h) => [h]))("%s có câu không rỗng", (hint) => {
    expect(retryMessage(hint).trim().length).toBeGreaterThan(0);
  });

  it("hint null dùng câu chung", () => {
    expect(retryMessage(null)).toBe(vi.verify.retryHintFallback);
    expect(retryMessage(null).length).toBeGreaterThan(0);
  });

  it("mỗi hint có câu riêng, khác câu chung", () => {
    const messages = RETRY_HINTS.map(retryMessage);
    expect(new Set(messages).size).toBe(RETRY_HINTS.length);
    expect(messages).not.toContain(retryMessage(null));
  });

  it("câu gợi ý chỉ nói về chất lượng, không có từ cấm", () => {
    const all = [...RETRY_HINTS.map(retryMessage), retryMessage(null)];
    for (const text of all) {
      for (const word of FORBIDDEN_IN_HINT) {
        expect(text.toLowerCase()).not.toContain(word);
      }
    }
  });

  it("hai câu có trong tài liệu đúng nguyên văn", () => {
    expect(retryMessage("MORE_LIGHT")).toBe("Ra chỗ sáng hơn");
    expect(retryMessage("MOVE_CLOSER")).toBe("Lại gần hơn");
  });
});

describe("cameraMessage", () => {
  const problems: (CameraProblem | null)[] = [null, "denied", "unavailable", "insecure"];

  it.each(problems.map((p) => [String(p), p] as const))(
    "%s có câu không rỗng",
    (_name, problem) => {
      expect(cameraMessage(problem).trim().length).toBeGreaterThan(0);
    },
  );

  it("bốn tình huống cho bốn câu khác nhau", () => {
    expect(new Set(problems.map(cameraMessage)).size).toBe(4);
  });
});

describe("màn đồng ý", () => {
  const c = vi.verify.consent;
  const text = collectStrings(c).join("\n");

  it("có các câu lấy từ tài liệu", () => {
    expect(text).toContain("Dữ liệu sinh trắc học là dữ liệu nhạy cảm");
    expect(text).toContain("24 giờ");
    expect(text).toContain("30 ngày");
    expect(text).toContain("Bạn có thể dừng bất cứ lúc nào");
  });

  it("không có cụm tự đặt chưa có trong tài liệu", () => {
    expect(text).not.toContain("rút lại");
    expect(text).not.toContain("xóa sớm");
  });
});

describe("màn kết quả", () => {
  const r = vi.verify.result;

  it("tiêu đề đúng nguyên văn", () => {
    expect(r.passTitle).toBe("Xác minh thành công");
    expect(r.retryTitle).toBe("Vui lòng thử lại");
    expect(r.reviewTitle).toBe("Hồ sơ đang được kiểm tra");
  });

  it("review không hiện như đạt", () => {
    expect(r.reviewTitle.toLowerCase()).not.toContain("thành công");
    expect(r.reviewBody.toLowerCase()).not.toContain("thành công");
  });

  it("tiêu đề pass khác tiêu đề review", () => {
    expect(r.passTitle).not.toBe(r.reviewTitle);
  });
});
