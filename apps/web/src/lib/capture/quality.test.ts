import { describe, expect, it } from "vitest";

import type { Point, Rect } from "./chromapulse/regions";
import { faceBox } from "./chromapulse/regions";
import {
  BLOWN_FRACTION_MAX,
  BLOWN_LUMA,
  CENTER_TOLERANCE_FRACTION,
  DARK_FRACTION_MAX,
  DARK_LUMA,
  FACE_WIDTH_MAX_FRACTION,
  FACE_WIDTH_MIN_FRACTION,
  GUIDANCE_PRIORITY,
  MEAN_LUMA_MAX,
  MEAN_LUMA_MIN,
  MIN_FPS,
  MIN_LONG_SIDE,
  MIN_SHORT_SIDE,
  MOVEMENT_MAX_FRACTION,
  OVAL_ASPECT,
  OVAL_IOU_MIN,
  OVAL_MAX_HEIGHT_FRACTION,
  OVAL_WIDTH_FRACTION,
  SHARPNESS_MIN,
  YAW_MAX_DEG,
  analyzeFrame,
  cropRectForFace,
  estimateFps,
  isFpsTooLow,
  isResolutionTooLow,
  laplacianVariance,
  lumaOf,
  lumaStats,
  movementFraction,
  ovalRect,
  pickGuidance,
  rectIou,
  yawDegrees,
  type FrameAnalysisInput,
  type PixelCrop,
  type QualityGuidance,
  type QualityMetrics,
} from "./quality";

// --- Trợ giúp dựng dữ liệu --------------------------------------------------------------------------

const FRAME = { width: 480, height: 853 };

/** 478 điểm mặc định ở giữa khung (0.5, 0.5); mỗi điểm là đối tượng riêng. */
function blankLandmarks(): Point[] {
  return Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5 }));
}

/** Landmark chỉ dùng cho yaw: hai mép mặt ở x=0.3 và 0.7, mũi ở noseX. */
function yawLandmarks(noseX: number): Point[] {
  const lm = blankLandmarks();
  lm[234] = { x: 0.3, y: 0.5 };
  lm[454] = { x: 0.7, y: 0.5 };
  lm[1] = { x: noseX, y: 0.5 };
  return lm;
}

/** Mảng RGBA đồng màu xám `v`, n điểm. */
function grayRgba(n: number, v: number): number[] {
  return Array.from({ length: n }, () => [v, v, v, 255]).flat();
}

/** Luma n điểm đồng giá trị. */
function flatLuma(n: number, v: number): number[] {
  return Array.from({ length: n }, () => v);
}

/** Ảnh bàn cờ luma xen kẽ lo/hi. */
function checker(w: number, h: number, lo: number, hi: number): number[] {
  const out: number[] = [];
  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) out.push((x + y) % 2 === 0 ? hi : lo);
  }
  return out;
}

function checkerRgba(w: number, h: number, lo: number, hi: number): number[] {
  return checker(w, h, lo, hi)
    .map((v) => [v, v, v, 255])
    .flat();
}

const OVAL = ovalRect(FRAME.width, FRAME.height);

/** Hộp mặt rộng `frac` chiều rộng khung, cao bằng oval, đặt giữa khung. */
function centeredFace(frac: number, height: number = OVAL.h): Rect {
  const w = frac * FRAME.width;
  return { x: (FRAME.width - w) / 2, y: (FRAME.height - height) / 2, w, h: height };
}

/** Số đo HỢP LỆ ĐẠT mọi tiêu chí. */
function goodMetrics(): QualityMetrics {
  return {
    faceCount: 1,
    frame: { ...FRAME },
    face: centeredFace(0.5),
    yawDeg: 3,
    sharpness: SHARPNESS_MIN * 3,
    meanLuma: 120,
    blownFraction: 0,
    darkFraction: 0,
    movement: 0.01,
  };
}

function guide(over: Partial<QualityMetrics>): QualityGuidance | null {
  return pickGuidance({ ...goodMetrics(), ...over });
}

// --- 1. Hằng số và thứ tự ưu tiên ------------------------------------------------------------------

describe("hằng số theo tài liệu", () => {
  it("mặt chiếm 35% đến 60% chiều rộng khung", () => {
    expect(FACE_WIDTH_MIN_FRACTION).toBe(0.35);
    expect(FACE_WIDTH_MAX_FRACTION).toBe(0.6);
  });

  it("IoU oval tối thiểu 0,6 và quay đầu tối đa 20 độ", () => {
    expect(OVAL_IOU_MIN).toBe(0.6);
    expect(YAW_MAX_DEG).toBe(20);
  });

  it("FPS tối thiểu 15 và độ phân giải tối thiểu 640x480", () => {
    expect(MIN_FPS).toBe(15);
    expect(MIN_SHORT_SIDE).toBe(480);
    expect(MIN_LONG_SIDE).toBe(640);
  });
});

describe("GUIDANCE_PRIORITY", () => {
  it("có đúng 10 chỉ dẫn, không trùng", () => {
    expect(GUIDANCE_PRIORITY).toHaveLength(10);
    expect(new Set(GUIDANCE_PRIORITY).size).toBe(10);
  });

  it("NO_FACE đứng đầu, BLURRY đứng cuối", () => {
    expect(GUIDANCE_PRIORITY[0]).toBe("NO_FACE");
    expect(GUIDANCE_PRIORITY[GUIDANCE_PRIORITY.length - 1]).toBe("BLURRY");
  });

  it("TOO_BRIGHT đứng trước LOW_LIGHT", () => {
    expect(GUIDANCE_PRIORITY.indexOf("TOO_BRIGHT")).toBeLessThan(
      GUIDANCE_PRIORITY.indexOf("LOW_LIGHT"),
    );
  });

  it("không có chỉ dẫn FPS trong danh sách", () => {
    const names: readonly string[] = GUIDANCE_PRIORITY;
    expect(names.some((n) => n.includes("FPS"))).toBe(false);
  });
});

// --- 2. Hình học ------------------------------------------------------------------------------------

describe("ovalRect", () => {
  it("khung dọc 480x853: oval ở giữa, đối xứng, rộng và cao theo hằng số", () => {
    const o = ovalRect(480, 853);
    expect(o.w).toBeCloseTo(OVAL_WIDTH_FRACTION * 480, 6);
    expect(o.h).toBeCloseTo(OVAL_ASPECT * o.w, 6);
    expect(o.x).toBeCloseTo(480 - (o.x + o.w), 6);
    expect(o.y).toBeCloseTo(853 - (o.y + o.h), 6);
  });

  it("khung ngang 640x360: cao không vượt trần, tỉ lệ giữ nguyên, nằm giữa", () => {
    const o = ovalRect(640, 360);
    expect(o.h).toBeLessThanOrEqual(OVAL_MAX_HEIGHT_FRACTION * 360 + 1e-9);
    expect(o.h / o.w).toBeCloseTo(OVAL_ASPECT, 6);
    expect(o.x).toBeGreaterThanOrEqual(0);
    expect(o.y).toBeGreaterThanOrEqual(0);
    expect(o.x + o.w).toBeLessThanOrEqual(640);
    expect(o.y + o.h).toBeLessThanOrEqual(360);
    expect(o.x).toBeCloseTo(640 - (o.x + o.w), 6);
    expect(o.y).toBeCloseTo(360 - (o.y + o.h), 6);
  });

  it("mọi kích thước khung: oval nằm trọn trong khung", () => {
    const sizes: [number, number][] = [
      [480, 853],
      [640, 480],
      [1280, 720],
      [720, 1280],
      [640, 360],
      [300, 300],
      [1920, 1080],
    ];
    for (const [w, h] of sizes) {
      const o = ovalRect(w, h);
      expect(o.x).toBeGreaterThanOrEqual(-1e-9);
      expect(o.y).toBeGreaterThanOrEqual(-1e-9);
      expect(o.x + o.w).toBeLessThanOrEqual(w + 1e-9);
      expect(o.y + o.h).toBeLessThanOrEqual(h + 1e-9);
    }
  });
});

describe("rectIou", () => {
  const a: Rect = { x: 0, y: 0, w: 10, h: 10 };

  it("hai hộp trùng nhau cho 1", () => {
    expect(rectIou(a, { ...a })).toBeCloseTo(1, 9);
  });

  it("hai hộp không giao nhau cho 0", () => {
    expect(rectIou(a, { x: 20, y: 0, w: 10, h: 10 })).toBe(0);
  });

  it("hai hộp chỉ chạm cạnh cho 0", () => {
    expect(rectIou(a, { x: 10, y: 0, w: 10, h: 10 })).toBe(0);
  });

  it("hai hình 10x10 lệch 5 theo x: 50/150", () => {
    expect(rectIou(a, { x: 5, y: 0, w: 10, h: 10 })).toBeCloseTo(50 / 150, 9);
  });

  it("diện tích 0 cho 0", () => {
    const zero: Rect = { x: 3, y: 3, w: 0, h: 0 };
    expect(rectIou(zero, zero)).toBe(0);
    expect(rectIou(a, zero)).toBe(0);
  });

  it("giá trị NaN cho 0", () => {
    expect(rectIou(a, { x: 0, y: 0, w: Number.NaN, h: 10 })).toBe(0);
  });

  it("đối xứng: IoU(a,b) = IoU(b,a)", () => {
    const b: Rect = { x: 3, y: 4, w: 12, h: 7 };
    expect(rectIou(a, b)).toBeCloseTo(rectIou(b, a), 12);
  });
});

describe("cropRectForFace", () => {
  const frame = { width: 480, height: 853 };

  it("làm tròn ra ngoài: floor góc trên-trái, ceil góc dưới-phải", () => {
    const r = cropRectForFace({ x: 10.4, y: 20.6, w: 30.2, h: 40.1 }, frame);
    expect(r).toEqual({ x: 10, y: 20, w: 31, h: 41 });
  });

  it("kẹp trong khung ở cả bốn phía", () => {
    expect(cropRectForFace({ x: -10, y: -5, w: 30, h: 30 }, frame)).toEqual({
      x: 0,
      y: 0,
      w: 20,
      h: 25,
    });
    expect(cropRectForFace({ x: 450, y: 830, w: 100, h: 100 }, frame)).toEqual({
      x: 450,
      y: 830,
      w: 30,
      h: 23,
    });
  });

  it("hộp nằm hoàn toàn ngoài khung cho null", () => {
    expect(cropRectForFace({ x: 500, y: 10, w: 20, h: 20 }, frame)).toBeNull();
    expect(cropRectForFace({ x: -50, y: 10, w: 20, h: 20 }, frame)).toBeNull();
    expect(cropRectForFace({ x: 10, y: 900, w: 20, h: 20 }, frame)).toBeNull();
  });

  it("hộp rỗng (rộng 0 hoặc cao 0 tại điểm nguyên) cho null", () => {
    expect(cropRectForFace({ x: 10, y: 10, w: 0, h: 20 }, frame)).toBeNull();
    expect(cropRectForFace({ x: 10, y: 10, w: 20, h: 0 }, frame)).toBeNull();
  });
});

// --- 3. Quay đầu và chuyển động --------------------------------------------------------------------

describe("yawDegrees", () => {
  it("mũi ở giữa hai mép mặt: gần 0 độ", () => {
    expect(yawDegrees(yawLandmarks(0.5))).toBeCloseTo(0, 6);
  });

  it("mũi lệch tương ứng sin(20 độ): khoảng 20 độ", () => {
    const x = 0.5 + 0.2 * Math.sin((20 * Math.PI) / 180);
    const yaw = yawDegrees(yawLandmarks(x));
    expect(yaw).not.toBeNull();
    expect(Math.abs((yaw ?? 0) - 20)).toBeLessThan(0.5);
  });

  it("lệch hai phía cho cùng độ lớn khác dấu", () => {
    const d = 0.2 * Math.sin((15 * Math.PI) / 180);
    const right = yawDegrees(yawLandmarks(0.5 + d));
    const left = yawDegrees(yawLandmarks(0.5 - d));
    expect(right).not.toBeNull();
    expect(left).not.toBeNull();
    expect(right ?? 0).toBeGreaterThan(0);
    expect(left ?? 0).toBeLessThan(0);
    expect(Math.abs(right ?? 0)).toBeCloseTo(Math.abs(left ?? 0), 9);
  });

  it("mũi ở mép mặt: khoảng 90 độ, không NaN", () => {
    const yaw = yawDegrees(yawLandmarks(0.7));
    expect(yaw).not.toBeNull();
    expect(Number.isNaN(yaw)).toBe(false);
    expect(yaw ?? 0).toBeCloseTo(90, 3);
  });

  it("mũi vượt ngoài mép mặt: kẹp ở 90 độ", () => {
    expect(yawDegrees(yawLandmarks(0.95))).toBeCloseTo(90, 6);
    expect(yawDegrees(yawLandmarks(0.05))).toBeCloseTo(-90, 6);
  });

  it("thiếu landmark (mảng ngắn hơn 455) cho null", () => {
    expect(yawDegrees(blankLandmarks().slice(0, 454))).toBeNull();
    expect(yawDegrees([])).toBeNull();
  });

  it("hai mép mặt trùng x cho null", () => {
    const lm = blankLandmarks();
    lm[234] = { x: 0.5, y: 0.5 };
    lm[454] = { x: 0.5, y: 0.5 };
    expect(yawDegrees(lm)).toBeNull();
  });
});

describe("movementFraction", () => {
  const cur: Rect = { x: 100, y: 100, w: 200, h: 250 };

  it("chưa có lần trước cho null", () => {
    expect(movementFraction(null, cur)).toBeNull();
  });

  it("cùng hộp cho 0", () => {
    expect(movementFraction({ ...cur }, cur)).toBe(0);
  });

  it("dịch ngang bằng nửa chiều rộng mặt cho 0,5", () => {
    expect(movementFraction({ ...cur, x: cur.x + cur.w / 2 }, cur)).toBeCloseTo(0.5, 9);
  });

  it("dịch dọc cũng được tính (khoảng cách Euclid)", () => {
    expect(movementFraction({ ...cur, x: cur.x + 30, y: cur.y + 40 }, cur)).toBeCloseTo(
      50 / 200,
      9,
    );
  });

  it("hộp hiện tại rộng 0 cho null", () => {
    expect(movementFraction({ ...cur }, { ...cur, w: 0 })).toBeNull();
  });
});

// --- 5. Điểm ảnh ------------------------------------------------------------------------------------

describe("lumaOf", () => {
  it("trắng cho 255, đen cho 0", () => {
    expect(lumaOf([255, 255, 255, 255])[0]).toBeCloseTo(255, 3);
    expect(lumaOf([0, 0, 0, 255])[0]).toBe(0);
  });

  it("đỏ thuần cho khoảng 0,299 x 255", () => {
    expect(lumaOf([255, 0, 0, 255])[0]).toBeCloseTo(0.299 * 255, 3);
  });

  it("xanh lá và xanh dương dùng đúng hệ số", () => {
    expect(lumaOf([0, 255, 0, 255])[0]).toBeCloseTo(0.587 * 255, 3);
    expect(lumaOf([0, 0, 255, 255])[0]).toBeCloseTo(0.114 * 255, 3);
  });

  it("bỏ qua alpha", () => {
    expect(lumaOf([100, 150, 200, 0])[0]).toBeCloseTo(lumaOf([100, 150, 200, 255])[0], 6);
  });

  it("độ dài không chia hết 4 không ném lỗi, bỏ phần dư", () => {
    const out = lumaOf([10, 20, 30, 255, 1, 2, 3]);
    expect(out).toHaveLength(1);
    expect(() => lumaOf([1, 2])).not.toThrow();
    expect(lumaOf([1, 2])).toHaveLength(0);
  });
});

describe("laplacianVariance", () => {
  it("ảnh phẳng cho 0", () => {
    expect(laplacianVariance(flatLuma(64, 120), 8, 8)).toBe(0);
  });

  it("ảnh bàn cờ 0/255 lớn hơn nhiều ngưỡng nét", () => {
    expect(laplacianVariance(checker(8, 8, 0, 255), 8, 8)).toBeGreaterThan(SHARPNESS_MIN * 100);
  });

  it("ảnh mờ (gradient tuyến tính) gần 0 và dưới ngưỡng nét", () => {
    const w = 16;
    const h = 16;
    const grad: number[] = [];
    for (let y = 0; y < h; y += 1) {
      for (let x = 0; x < w; x += 1) grad.push(x * 10);
    }
    const v = laplacianVariance(grad, w, h);
    expect(v).toBeCloseTo(0, 6);
    expect(v).toBeLessThan(SHARPNESS_MIN);
  });

  it("ảnh nhỏ hơn 3x3 cho 0", () => {
    expect(laplacianVariance(checker(2, 2, 0, 255), 2, 2)).toBe(0);
    expect(laplacianVariance(checker(8, 2, 0, 255), 8, 2)).toBe(0);
    expect(laplacianVariance(checker(2, 8, 0, 255), 2, 8)).toBe(0);
  });

  it("mảng ngắn hơn width x height cho 0", () => {
    expect(laplacianVariance(checker(8, 8, 0, 255).slice(0, 40), 8, 8)).toBe(0);
  });

  it("cùng bố cục nhưng tương phản thấp hơn cho phương sai nhỏ hơn", () => {
    const high = laplacianVariance(checker(8, 8, 0, 255), 8, 8);
    const low = laplacianVariance(checker(8, 8, 100, 110), 8, 8);
    expect(low).toBeGreaterThan(0);
    expect(low).toBeLessThan(high);
  });
});

describe("lumaStats", () => {
  it("toàn 255: mean 255, cháy sáng 1, tối 0", () => {
    const s = lumaStats(flatLuma(100, 255));
    expect(s.mean).toBe(255);
    expect(s.blownFraction).toBe(1);
    expect(s.darkFraction).toBe(0);
  });

  it("toàn 10: tối hoàn toàn", () => {
    const s = lumaStats(flatLuma(100, 10));
    expect(s.mean).toBe(10);
    expect(s.blownFraction).toBe(0);
    expect(s.darkFraction).toBe(1);
  });

  it("nửa 255 nửa 10: 0,5 và 0,5", () => {
    const s = lumaStats([...flatLuma(50, 255), ...flatLuma(50, 10)]);
    expect(s.blownFraction).toBe(0.5);
    expect(s.darkFraction).toBe(0.5);
    expect(s.mean).toBeCloseTo(132.5, 9);
  });

  it("điểm đúng bằng BLOWN_LUMA tính là cháy sáng", () => {
    expect(lumaStats([BLOWN_LUMA]).blownFraction).toBe(1);
    expect(lumaStats([BLOWN_LUMA - 1]).blownFraction).toBe(0);
  });

  it("điểm đúng bằng DARK_LUMA KHÔNG tính là tối", () => {
    expect(lumaStats([DARK_LUMA]).darkFraction).toBe(0);
    expect(lumaStats([DARK_LUMA - 1]).darkFraction).toBe(1);
  });

  it("mảng rỗng cho NaN cả ba số", () => {
    const s = lumaStats([]);
    expect(s.mean).toBeNaN();
    expect(s.blownFraction).toBeNaN();
    expect(s.darkFraction).toBeNaN();
  });
});

// --- 6. FPS và thiết bị ----------------------------------------------------------------------------

function evenTimes(count: number, gapMs: number): number[] {
  return Array.from({ length: count }, (_, i) => 1000 + i * gapMs);
}

describe("estimateFps", () => {
  it("ít hơn 10 mốc cho null", () => {
    expect(estimateFps(evenTimes(9, 33.3))).toBeNull();
    expect(estimateFps([])).toBeNull();
  });

  it("đúng 10 mốc thì đã kết luận được", () => {
    expect(estimateFps(evenTimes(10, 100))).toBeCloseTo(10, 6);
  });

  it("30 mốc cách 33,3 ms cho khoảng 30", () => {
    expect(estimateFps(evenTimes(30, 33.3)) ?? 0).toBeCloseTo(30, 0);
  });

  it("cách 16,67 ms cho khoảng 60", () => {
    expect(estimateFps(evenTimes(30, 16.67)) ?? 0).toBeCloseTo(60, 0);
  });

  it("cách đều 100 ms cho 10", () => {
    expect(estimateFps(evenTimes(30, 100))).toBeCloseTo(10, 9);
  });

  it("vài khung trễ lớn (ngoại lệ) mà trung vị vẫn khoảng 30", () => {
    const times: number[] = [];
    let t = 0;
    for (let i = 0; i < 30; i += 1) {
      t += i === 7 || i === 15 || i === 22 ? 500 : 33.3;
      times.push(t);
    }
    expect(estimateFps(times) ?? 0).toBeCloseTo(30, 0);
  });

  it("mốc trùng nhau hoặc đi lùi không gây NaN", () => {
    const times = [0, 0, 33, 33, 66, 60, 99, 132, 165, 165, 198, 231];
    const fps = estimateFps(times);
    expect(fps).not.toBeNull();
    expect(Number.isFinite(fps)).toBe(true);
    expect(fps ?? 0).toBeGreaterThan(0);
  });

  it("tất cả mốc bằng nhau cho null", () => {
    expect(estimateFps(Array.from({ length: 20 }, () => 500))).toBeNull();
  });
});

describe("isFpsTooLow", () => {
  it("chưa biết FPS thì không coi là chậm", () => {
    expect(isFpsTooLow(null)).toBe(false);
  });

  it("14,9 là chậm, 15 thì không", () => {
    expect(isFpsTooLow(14.9)).toBe(true);
    expect(isFpsTooLow(15)).toBe(false);
    expect(isFpsTooLow(30)).toBe(false);
  });
});

describe("isResolutionTooLow", () => {
  it("640x480 và 480x640 đủ (không phụ thuộc hướng)", () => {
    expect(isResolutionTooLow(640, 480)).toBe(false);
    expect(isResolutionTooLow(480, 640)).toBe(false);
  });

  it("1280x720 và 720x1280 đủ", () => {
    expect(isResolutionTooLow(1280, 720)).toBe(false);
    expect(isResolutionTooLow(720, 1280)).toBe(false);
  });

  it("thiếu một cạnh là thấp", () => {
    expect(isResolutionTooLow(639, 480)).toBe(true);
    expect(isResolutionTooLow(640, 479)).toBe(true);
  });

  it("320x240, 0x0 và NaN là thấp", () => {
    expect(isResolutionTooLow(320, 240)).toBe(true);
    expect(isResolutionTooLow(0, 0)).toBe(true);
    expect(isResolutionTooLow(Number.NaN, 480)).toBe(true);
    expect(isResolutionTooLow(Number.NaN, Number.NaN)).toBe(true);
  });
});

// --- 7. pickGuidance --------------------------------------------------------------------------------

describe("pickGuidance: khung đạt", () => {
  it("số đo hợp lệ đạt mọi tiêu chí cho null", () => {
    expect(pickGuidance(goodMetrics())).toBeNull();
  });

  it("khung mẫu thực sự khớp oval (IoU đủ lớn, chiều rộng trong khoảng cho phép)", () => {
    const m = goodMetrics();
    expect(m.face).not.toBeNull();
    if (m.face) {
      expect(rectIou(m.face, OVAL)).toBeGreaterThanOrEqual(OVAL_IOU_MIN);
      const ratio = m.face.w / FRAME.width;
      expect(ratio).toBeGreaterThanOrEqual(FACE_WIDTH_MIN_FRACTION);
      expect(ratio).toBeLessThanOrEqual(FACE_WIDTH_MAX_FRACTION);
    }
  });

  it("kết quả luôn là chuỗi hoặc null, không phải mảng", () => {
    const r = guide({ faceCount: 2, sharpness: 0, meanLuma: 5, blownFraction: 0.9 });
    expect(typeof r).toBe("string");
    expect(Array.isArray(r)).toBe(false);
    expect(Array.isArray(pickGuidance(goodMetrics()))).toBe(false);
  });
});

describe("pickGuidance: từng chỉ dẫn", () => {
  it("NO_FACE khi faceCount 0", () => {
    expect(guide({ faceCount: 0 })).toBe("NO_FACE");
  });

  it("NO_FACE khi face là null", () => {
    expect(guide({ face: null })).toBe("NO_FACE");
  });

  it("NO_FACE khi một số đo ánh sáng hoặc độ nét là NaN", () => {
    expect(guide({ sharpness: Number.NaN })).toBe("NO_FACE");
    expect(guide({ meanLuma: Number.NaN })).toBe("NO_FACE");
    expect(guide({ blownFraction: Number.NaN })).toBe("NO_FACE");
    expect(guide({ darkFraction: Number.NaN })).toBe("NO_FACE");
  });

  it("MULTIPLE_FACES khi có 2 mặt", () => {
    expect(guide({ faceCount: 2 })).toBe("MULTIPLE_FACES");
  });

  it("FACE_CENTER khi tâm mặt lệch quá dung sai ngang", () => {
    const f = centeredFace(0.5);
    const shift = (CENTER_TOLERANCE_FRACTION + 0.05) * FRAME.width;
    expect(guide({ face: { ...f, x: f.x + shift } })).toBe("FACE_CENTER");
  });

  it("FACE_CENTER khi tâm mặt lệch quá dung sai dọc", () => {
    const f = centeredFace(0.5);
    const shift = (CENTER_TOLERANCE_FRACTION + 0.05) * FRAME.height;
    expect(guide({ face: { ...f, y: f.y - shift } })).toBe("FACE_CENTER");
  });

  it("tâm mặt lệch nhỏ hơn dung sai thì không bị FACE_CENTER", () => {
    const f = centeredFace(0.5);
    const shift = (CENTER_TOLERANCE_FRACTION / 3) * FRAME.width;
    expect(guide({ face: { ...f, x: f.x + shift } })).not.toBe("FACE_CENTER");
  });

  it("MOVE_CLOSER khi mặt rộng dưới 35% khung", () => {
    expect(guide({ face: centeredFace(0.3) })).toBe("MOVE_CLOSER");
  });

  it("mặt rộng 0,38 khung nhưng IoU dưới 0,6: MOVE_CLOSER, không phải FACE_CENTER", () => {
    const f = centeredFace(0.38, OVAL.h * (0.38 / 0.5));
    expect(rectIou(f, OVAL)).toBeLessThan(OVAL_IOU_MIN);
    expect(guide({ face: f })).toBe("MOVE_CLOSER");
  });

  it("MOVE_BACK khi mặt rộng trên 60% khung", () => {
    expect(guide({ face: centeredFace(0.7) })).toBe("MOVE_BACK");
  });

  it("mặt rộng đúng 35% và 60% khung (qua cổng khác) không bị chỉ dẫn khoảng cách", () => {
    expect(guide({ face: centeredFace(FACE_WIDTH_MIN_FRACTION) })).toBeNull();
    expect(guide({ face: centeredFace(FACE_WIDTH_MAX_FRACTION) })).toBeNull();
  });

  it("TURN_STRAIGHT khi yaw 21 độ", () => {
    expect(guide({ yawDeg: YAW_MAX_DEG + 1 })).toBe("TURN_STRAIGHT");
  });

  it("yaw đúng 20 độ không bị TURN_STRAIGHT (chỉ > 20 mới nghiêng)", () => {
    expect(guide({ yawDeg: YAW_MAX_DEG })).toBeNull();
  });

  it("yaw null thì TURN_STRAIGHT", () => {
    expect(guide({ yawDeg: null })).toBe("TURN_STRAIGHT");
  });

  it("TOO_BRIGHT khi tỉ lệ cháy sáng vượt ngưỡng", () => {
    expect(guide({ blownFraction: BLOWN_FRACTION_MAX + 0.05 })).toBe("TOO_BRIGHT");
  });

  it("TOO_BRIGHT khi độ sáng trung bình vượt trần", () => {
    expect(guide({ meanLuma: MEAN_LUMA_MAX + 5 })).toBe("TOO_BRIGHT");
  });

  it("LOW_LIGHT khi độ sáng trung bình dưới sàn", () => {
    expect(guide({ meanLuma: MEAN_LUMA_MIN - 5 })).toBe("LOW_LIGHT");
  });

  it("LOW_LIGHT khi tỉ lệ điểm tối vượt ngưỡng", () => {
    expect(guide({ darkFraction: DARK_FRACTION_MAX + 0.1 })).toBe("LOW_LIGHT");
  });

  it("HOLD_STILL khi chuyển động vượt ngưỡng", () => {
    expect(guide({ movement: MOVEMENT_MAX_FRACTION + 0.05 })).toBe("HOLD_STILL");
  });

  it("HOLD_STILL khi chưa có lần đo trước (movement null)", () => {
    expect(guide({ movement: null })).toBe("HOLD_STILL");
  });

  it("BLURRY khi độ nét dưới ngưỡng", () => {
    expect(guide({ sharpness: SHARPNESS_MIN - 1 })).toBe("BLURRY");
  });
});

describe("pickGuidance: giá trị đúng bằng ngưỡng không bị chỉ dẫn", () => {
  it("sharpness = SHARPNESS_MIN", () => {
    expect(guide({ sharpness: SHARPNESS_MIN })).toBeNull();
  });

  it("meanLuma = MEAN_LUMA_MIN và = MEAN_LUMA_MAX", () => {
    expect(guide({ meanLuma: MEAN_LUMA_MIN })).toBeNull();
    expect(guide({ meanLuma: MEAN_LUMA_MAX })).toBeNull();
  });

  it("blownFraction = BLOWN_FRACTION_MAX", () => {
    expect(guide({ blownFraction: BLOWN_FRACTION_MAX })).toBeNull();
  });

  it("darkFraction = DARK_FRACTION_MAX", () => {
    expect(guide({ darkFraction: DARK_FRACTION_MAX })).toBeNull();
  });

  it("movement = MOVEMENT_MAX_FRACTION", () => {
    expect(guide({ movement: MOVEMENT_MAX_FRACTION })).toBeNull();
  });
});

// --- Thứ tự ưu tiên ---------------------------------------------------------------------------------

/** Mỗi phép biến đổi làm khung vi phạm ĐÚNG tiêu chí của chỉ dẫn tương ứng. */
const VIOLATE: Record<QualityGuidance, (m: QualityMetrics) => QualityMetrics> = {
  NO_FACE: (m) => ({ ...m, faceCount: 0 }),
  MULTIPLE_FACES: (m) => ({ ...m, faceCount: 2 }),
  FACE_CENTER: (m) =>
    m.face ? { ...m, face: { ...m.face, x: m.face.x + 0.3 * m.frame.width } } : m,
  MOVE_CLOSER: (m) => (m.face ? { ...m, face: resizeAroundCenter(m.face, 0.3) } : m),
  MOVE_BACK: (m) => (m.face ? { ...m, face: resizeAroundCenter(m.face, 0.7) } : m),
  TURN_STRAIGHT: (m) => ({ ...m, yawDeg: 40 }),
  TOO_BRIGHT: (m) => ({ ...m, blownFraction: 0.5 }),
  LOW_LIGHT: (m) => ({ ...m, meanLuma: MEAN_LUMA_MIN - 30, darkFraction: 0.8 }),
  HOLD_STILL: (m) => ({ ...m, movement: 0.5 }),
  BLURRY: (m) => ({ ...m, sharpness: 0 }),
};

function resizeAroundCenter(f: Rect, widthFrac: number): Rect {
  const w = widthFrac * FRAME.width;
  const cx = f.x + f.w / 2;
  return { x: cx - w / 2, y: f.y, w, h: f.h };
}

describe("pickGuidance: thứ tự ưu tiên", () => {
  it("mỗi phép vi phạm riêng lẻ cho đúng chỉ dẫn của nó", () => {
    for (const g of GUIDANCE_PRIORITY) {
      expect(pickGuidance(VIOLATE[g](goodMetrics()))).toBe(g);
    }
  });

  it("vi phạm đồng thời hai tiêu chí i<j: ra chỉ dẫn đứng trước", () => {
    const failures: string[] = [];
    for (let i = 0; i < GUIDANCE_PRIORITY.length; i += 1) {
      for (let j = i + 1; j < GUIDANCE_PRIORITY.length; j += 1) {
        const gi = GUIDANCE_PRIORITY[i];
        const gj = GUIDANCE_PRIORITY[j];
        // Gần và xa loại trừ nhau về hình học.
        if (gi === "MOVE_CLOSER" && gj === "MOVE_BACK") continue;
        if (gi === "NO_FACE" && gj === "MULTIPLE_FACES") continue; // cùng ghi faceCount
        // Hai phép dựng không thể xếp chồng một cách có nghĩa với NO_FACE (face không ảnh hưởng).
        const m = VIOLATE[gj](VIOLATE[gi](goodMetrics()));
        const got = pickGuidance(m);
        if (got !== gi) failures.push(`${gi} > ${gj}: nhận ${String(got)}`);
      }
    }
    expect(failures).toEqual([]);
  });

  it("NO_FACE thắng mọi chỉ dẫn khác dù mọi tiêu chí khác cùng vi phạm", () => {
    let m = goodMetrics();
    for (const g of GUIDANCE_PRIORITY) {
      if (g === "MOVE_BACK") continue;
      m = VIOLATE[g](m);
    }
    expect(pickGuidance(VIOLATE.NO_FACE(m))).toBe("NO_FACE");
  });

  it("vừa cháy sáng nhiều vừa meanLuma thấp bất thường vẫn ra TOO_BRIGHT", () => {
    expect(guide({ blownFraction: 0.5, meanLuma: 20, darkFraction: 0.9 })).toBe("TOO_BRIGHT");
  });

  it("LOW_LIGHT thắng HOLD_STILL, HOLD_STILL thắng BLURRY", () => {
    expect(guide({ meanLuma: 20, movement: 0.9, sharpness: 0 })).toBe("LOW_LIGHT");
    expect(guide({ movement: 0.9, sharpness: 0 })).toBe("HOLD_STILL");
    expect(guide({ sharpness: 0 })).toBe("BLURRY");
  });
});

describe("pickGuidance: an toàn, không đo được thì không bao giờ đạt", () => {
  it("khung quá sáng (cháy sáng 0,5, mọi thứ khác đạt) không bao giờ là null", () => {
    expect(guide({ blownFraction: 0.5 })).not.toBeNull();
    expect(guide({ blownFraction: 0.5 })).toBe("TOO_BRIGHT");
    expect(guide({ blownFraction: 1, meanLuma: 255 })).not.toBeNull();
  });

  it("mọi tổ hợp một số đo NaN hoặc Infinity không bao giờ là null", () => {
    const bad = [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY];
    const keys = ["sharpness", "meanLuma", "blownFraction", "darkFraction"] as const;
    for (const key of keys) {
      for (const v of bad) {
        expect(guide({ [key]: v }), `${key}=${v}`).not.toBeNull();
      }
    }
    for (const v of bad) {
      expect(guide({ yawDeg: v }), `yawDeg=${v}`).not.toBeNull();
      expect(guide({ movement: v }), `movement=${v}`).not.toBeNull();
    }
  });

  it("nhiều số đo hỏng cùng lúc cũng không bao giờ là null", () => {
    expect(
      guide({
        sharpness: Number.NaN,
        meanLuma: Number.POSITIVE_INFINITY,
        blownFraction: Number.NaN,
        darkFraction: Number.NaN,
        yawDeg: null,
        movement: null,
      }),
    ).not.toBeNull();
  });

  it("kích thước khung không hợp lệ không bao giờ là null", () => {
    expect(guide({ frame: { width: Number.NaN, height: 853 } })).not.toBeNull();
    expect(guide({ frame: { width: 0, height: 853 } })).not.toBeNull();
  });
});

// --- analyzeFrame đầu-cuối --------------------------------------------------------------------------

/** 478 điểm của một khuôn mặt rộng 0,5 khung, cao bằng oval, đặt giữa khung 480x853, mũi ở giữa. */
function faceLandmarks(): Point[] {
  const lm = blankLandmarks();
  const top = (FRAME.height - OVAL.h) / 2 / FRAME.height;
  const bottom = top + OVAL.h / FRAME.height;
  lm[10] = { x: 0.5, y: top };
  lm[152] = { x: 0.5, y: bottom };
  lm[234] = { x: 0.25, y: 0.5 };
  lm[454] = { x: 0.75, y: 0.5 };
  lm[1] = { x: 0.5, y: 0.5 };
  return lm;
}

function cropOf(data: number[], size = 16): PixelCrop {
  return { data, width: size, height: size };
}

function baseInput(over: Partial<FrameAnalysisInput> = {}): FrameAnalysisInput {
  const lm = faceLandmarks();
  return {
    faceCount: 1,
    landmarks: lm,
    frame: { ...FRAME },
    crop: cropOf(checkerRgba(16, 16, 100, 180)),
    prevFace: faceBox(lm, FRAME.width, FRAME.height),
    ...over,
  };
}

function analyzedGuidance(over: Partial<FrameAnalysisInput> = {}): QualityGuidance | null {
  return pickGuidance(analyzeFrame(baseInput(over)));
}

describe("analyzeFrame đầu-cuối", () => {
  it("hộp mặt tổng hợp rộng 0,5 khung, ở giữa khung", () => {
    const m = analyzeFrame(baseInput());
    expect(m.face).not.toBeNull();
    expect(m.face?.w).toBeCloseTo(0.5 * FRAME.width, 6);
    expect(m.face ? m.face.x + m.face.w / 2 : Number.NaN).toBeCloseTo(FRAME.width / 2, 6);
    expect(m.yawDeg).toBeCloseTo(0, 6);
    expect(m.movement).toBeCloseTo(0, 9);
  });

  it("(a) da sáng vừa, có chi tiết, mặt đứng yên: đạt (null)", () => {
    expect(analyzedGuidance()).toBeNull();
  });

  it("(b) crop toàn trắng 255: TOO_BRIGHT", () => {
    expect(analyzedGuidance({ crop: cropOf(grayRgba(256, 255)) })).toBe("TOO_BRIGHT");
  });

  it("(c) crop toàn đen: LOW_LIGHT", () => {
    expect(analyzedGuidance({ crop: cropOf(grayRgba(256, 0)) })).toBe("LOW_LIGHT");
  });

  it("(d) crop phẳng xám 120: BLURRY", () => {
    expect(analyzedGuidance({ crop: cropOf(grayRgba(256, 120)) })).toBe("BLURRY");
  });

  it("(e) prevFace null: HOLD_STILL", () => {
    expect(analyzedGuidance({ prevFace: null })).toBe("HOLD_STILL");
  });

  it("(f) prevFace dịch xa: HOLD_STILL", () => {
    const lm = faceLandmarks();
    const box = faceBox(lm, FRAME.width, FRAME.height);
    expect(analyzedGuidance({ prevFace: { ...box, x: box.x + box.w } })).toBe("HOLD_STILL");
  });

  it("(g) crop null: NO_FACE và các số đo ảnh là NaN", () => {
    const m = analyzeFrame(baseInput({ crop: null }));
    expect(m.sharpness).toBeNaN();
    expect(m.meanLuma).toBeNaN();
    expect(m.blownFraction).toBeNaN();
    expect(m.darkFraction).toBeNaN();
    expect(pickGuidance(m)).toBe("NO_FACE");
  });

  it("(h) landmarks null: NO_FACE", () => {
    const m = analyzeFrame(baseInput({ landmarks: null }));
    expect(m.face).toBeNull();
    expect(m.yawDeg).toBeNull();
    expect(m.movement).toBeNull();
    expect(pickGuidance(m)).toBe("NO_FACE");
  });

  it("landmarks rỗng: NO_FACE", () => {
    expect(analyzedGuidance({ landmarks: [] })).toBe("NO_FACE");
  });

  it("(i) faceCount 2: MULTIPLE_FACES", () => {
    expect(analyzedGuidance({ faceCount: 2 })).toBe("MULTIPLE_FACES");
  });

  it("không sửa mảng đầu vào (đóng băng landmark và dữ liệu điểm ảnh)", () => {
    const lm = faceLandmarks().map((p) => Object.freeze({ ...p }));
    Object.freeze(lm);
    const data = Object.freeze(checkerRgba(16, 16, 100, 180));
    const prev = Object.freeze({ ...faceBox(lm, FRAME.width, FRAME.height) });
    const frame = Object.freeze({ ...FRAME });
    const lmBefore = JSON.stringify(lm);
    const dataBefore = JSON.stringify(data);
    expect(() =>
      analyzeFrame({
        faceCount: 1,
        landmarks: lm,
        frame,
        crop: { data, width: 16, height: 16 },
        prevFace: prev,
      }),
    ).not.toThrow();
    expect(JSON.stringify(lm)).toBe(lmBefore);
    expect(JSON.stringify(data)).toBe(dataBefore);
  });
});
