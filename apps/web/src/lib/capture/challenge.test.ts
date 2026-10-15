import { describe, expect, it } from "vitest";

import type { Challenge } from "@/lib/api/client";

import { chromaPulseConfig } from "./chromapulse/config";
import { challengeToSteps, configForChallenge, flashProblems } from "./challenge";

function makeChallenge(overrides: Partial<Challenge> = {}): Challenge {
  const palette = chromaPulseConfig.palette;
  return {
    challenge_id: "ch_1",
    baseline_ms: 1000,
    color_sequence: Array.from({ length: 8 }, (_, i) => ({
      rgb: palette[i % 2],
      hold_ms: 500,
      transition_ms: 150 as const,
    })),
    ...overrides,
  };
}

describe("challengeToSteps", () => {
  it("đổi snake_case của máy chủ thành bước nháy, giữ thứ tự và chỉ số", () => {
    const steps = challengeToSteps(makeChallenge());
    expect(steps).toHaveLength(8);
    expect(steps?.[0]).toEqual({
      index: 0,
      rgb: chromaPulseConfig.palette[0],
      holdMs: 500,
      transitionMs: 150,
    });
    expect(steps?.map((s) => s.index)).toEqual([0, 1, 2, 3, 4, 5, 6, 7]);
  });

  it.each([
    ["rỗng", { color_sequence: [] }],
    [
      "màu sai dạng",
      { color_sequence: [{ rgb: "đỏ", hold_ms: 500, transition_ms: 150 as const }] },
    ],
    [
      "hold_ms không phải số",
      { color_sequence: [{ rgb: "#ffcc73", hold_ms: Number.NaN, transition_ms: 150 as const }] },
    ],
  ])("dữ liệu %s trả null (không nháy)", (_name, patch) => {
    expect(challengeToSteps(makeChallenge(patch as Partial<Challenge>))).toBeNull();
  });
});

describe("flashProblems: web không nháy nếu thử thách vi phạm giới hạn an toàn", () => {
  const steps = () => challengeToSteps(makeChallenge()) ?? [];

  it("thử thách hợp lệ không có vấn đề", () => {
    expect(flashProblems(steps())).toEqual([]);
  });

  it("đổi màu quá nhanh (> 2,5 lần mỗi giây) bị chặn", () => {
    const fast = steps().map((s) => ({ ...s, holdMs: 100, transitionMs: 100 }));
    expect(flashProblems(fast).join(" ")).toContain("quá nhanh");
  });

  it("sai số bước bị chặn", () => {
    expect(flashProblems(steps().slice(0, 7)).join(" ")).toContain("Cần 8 bước");
  });

  it("hai bước liền kề cùng màu bị chặn", () => {
    const same = steps().map((s, i) => (i === 3 ? { ...s, rgb: steps()[2].rgb } : s));
    expect(flashProblems(same).join(" ")).toContain("cùng màu");
  });

  it("màu đỏ bão hòa hoặc chênh độ chói lớn bị chặn", () => {
    const red = steps().map((s, i) =>
      i % 2 ? { ...s, rgb: "#ff1010" } : { ...s, rgb: "#ffffff" },
    );
    expect(flashProblems(red).length).toBeGreaterThan(0);
  });
});

describe("configForChallenge", () => {
  it("lấy nền đầu từ máy chủ nếu có", () => {
    expect(configForChallenge(makeChallenge({ baseline_ms: 1500 })).baselineMs).toBe(1500);
  });

  it("thiếu hoặc sai thì dùng cấu hình chung", () => {
    expect(configForChallenge(makeChallenge({ baseline_ms: undefined })).baselineMs).toBe(
      chromaPulseConfig.baselineMs,
    );
    expect(configForChallenge(makeChallenge({ baseline_ms: -5 })).baselineMs).toBe(
      chromaPulseConfig.baselineMs,
    );
  });
});
