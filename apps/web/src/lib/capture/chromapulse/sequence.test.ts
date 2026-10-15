import { describe, expect, it } from "vitest";

import { chromaPulseConfig, hexToRgb } from "./config";
import {
  buildTimeline,
  colorAt,
  generateSequence,
  maxChangesPerSecond,
  paletteProblems,
  redShare,
  relativeLuminance,
} from "./sequence";

// Bộ sinh số ngẫu nhiên có hạt giống, để test lặp lại được.
function seeded(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

const SEEDS = Array.from({ length: 200 }, (_, i) => i + 1);

describe("chromapulse.json (nguồn chung với API)", () => {
  it("giữ các giới hạn an toàn của ADR-0011", () => {
    const c = chromaPulseConfig;
    expect(c.steps).toBe(8);
    expect(c.maxChangesPerSecond).toBeLessThanOrEqual(2.5);
    expect(c.maxLuminanceSpread).toBeLessThanOrEqual(0.064);
    expect(c.maxRedShare).toBeLessThanOrEqual(0.8);
    expect(c.holdMinMs + c.transitionMs).toBeGreaterThanOrEqual(550);
    expect(paletteProblems(c.palette)).toEqual([]);
  });

  it("nền xám và bảng màu là mã hex hợp lệ", () => {
    for (const hex of [chromaPulseConfig.baselineColor, ...chromaPulseConfig.palette]) {
      expect(hexToRgb(hex)).toHaveLength(3);
    }
  });
});

describe("paletteProblems", () => {
  it("từ chối bảng màu chênh độ chói quá lớn, đỏ bão hòa hoặc quá ít màu", () => {
    expect(paletteProblems(["#000000", "#ffffff"]).length).toBeGreaterThan(0);
    expect(paletteProblems(["#ff1010", "#ff1111"]).length).toBeGreaterThan(0);
    expect(paletteProblems(["#ffcc73"]).length).toBeGreaterThan(0);
  });

  it("chấp nhận bảng màu an toàn", () => {
    expect(paletteProblems(["#ffcc73", "#80e09e"])).toEqual([]);
  });

  it("công thức độ chói và độ đỏ khớp giá trị tay tính", () => {
    expect(relativeLuminance("#ffffff")).toBeCloseTo(1, 6);
    expect(relativeLuminance("#000000")).toBe(0);
    expect(redShare("#ff0000")).toBe(1);
    expect(redShare("#000000")).toBe(0);
    expect(redShare("#ffcc73")).toBeCloseTo(255 / (255 + 204 + 115), 6);
  });
});

describe.each(SEEDS)("generateSequence (hạt giống %i)", (seed) => {
  const steps = generateSequence(seeded(seed));

  it("đúng 8 màu, hai màu liền kề khác nhau, nằm trong bảng màu", () => {
    expect(steps).toHaveLength(chromaPulseConfig.steps);
    steps.slice(1).forEach((s, i) => expect(s.rgb).not.toBe(steps[i].rgb));
    for (const s of steps) expect(chromaPulseConfig.palette).toContain(s.rgb);
  });

  it("nhịp an toàn: hold 400–650, chuyển 150, <= 2,5 lần đổi/giây", () => {
    for (const s of steps) {
      expect(s.holdMs).toBeGreaterThanOrEqual(chromaPulseConfig.holdMinMs);
      expect(s.holdMs).toBeLessThanOrEqual(chromaPulseConfig.holdMaxMs);
      expect(s.transitionMs).toBe(chromaPulseConfig.transitionMs);
    }
    expect(maxChangesPerSecond(steps)).toBeLessThanOrEqual(2.5);
  });

  it("chênh độ chói <= 0,064 và không màu nào có R/(R+G+B) >= 0,8", () => {
    const lum = steps.map((s) => relativeLuminance(s.rgb));
    expect(Math.max(...lum) - Math.min(...lum)).toBeLessThanOrEqual(0.064);
    for (const s of steps) expect(redShare(s.rgb)).toBeLessThan(0.8);
  });
});

describe("buildTimeline và colorAt", () => {
  const steps = generateSequence(seeded(7));
  const timeline = buildTimeline(steps);

  it("tổng thời gian = nền đầu + các bước + nền cuối (khoảng 4,4–6,4 s cho 8 bước)", () => {
    const stepsTotal = steps.reduce((a, s) => a + s.holdMs + s.transitionMs, 0);
    expect(timeline.totalMs).toBe(
      chromaPulseConfig.baselineMs + stepsTotal + chromaPulseConfig.tailMs,
    );
    expect(stepsTotal).toBeGreaterThanOrEqual(4400);
    expect(stepsTotal).toBeLessThanOrEqual(6400);
  });

  it("các bước nối liền nhau, bước đầu bắt đầu sau nền đầu", () => {
    expect(timeline.segments[0].startMs).toBe(chromaPulseConfig.baselineMs);
    timeline.segments.slice(1).forEach((seg, i) => {
      expect(seg.startMs).toBe(timeline.segments[i].endMs);
    });
    expect(timeline.tailStartMs).toBe(timeline.segments[7].endMs);
  });

  it("nền xám trước bước đầu và sau khi hết", () => {
    const gray = hexToRgb(chromaPulseConfig.baselineColor);
    expect(colorAt(timeline, 0).rgb).toEqual(gray);
    expect(colorAt(timeline, chromaPulseConfig.baselineMs - 1).stepIndex).toBe(-1);
    const end = colorAt(timeline, timeline.totalMs);
    expect(end.done).toBe(true);
    expect(end.rgb).toEqual(gray);
  });

  it("đạt đúng màu đích sau khi hết chuyển và giữ nguyên trong lúc giữ", () => {
    for (const seg of timeline.segments) {
      const target = hexToRgb(seg.rgb);
      expect(colorAt(timeline, seg.holdStartMs).rgb).toEqual(target);
      expect(colorAt(timeline, seg.endMs - 1).rgb).toEqual(target);
      expect(colorAt(timeline, seg.startMs).stepIndex).toBe(seg.index);
    }
  });

  it("chuyển màu tuyến tính: giữa đoạn chuyển nằm giữa màu cũ và màu mới", () => {
    const seg = timeline.segments[1];
    const from = hexToRgb(timeline.segments[0].rgb);
    const to = hexToRgb(seg.rgb);
    const mid = colorAt(timeline, seg.startMs + chromaPulseConfig.transitionMs / 2).rgb;
    for (let i = 0; i < 3; i += 1) {
      expect(mid[i]).toBeGreaterThanOrEqual(Math.min(from[i], to[i]));
      expect(mid[i]).toBeLessThanOrEqual(Math.max(from[i], to[i]));
    }
  });
});
