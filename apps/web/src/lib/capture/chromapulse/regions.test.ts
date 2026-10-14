import { describe, expect, it } from "vitest";

import {
  REGION_DEFS,
  REGION_LANDMARKS,
  REGION_NAMES,
  SKIN_REGIONS,
  type Point,
  type SkinRegion,
  backgroundRects,
  faceBox,
  skinRegionRects,
  summarizePixels,
} from "./regions";

/** Dựng mảng RGBA từ danh sách [r, g, b] (alpha mặc định 255). */
function rgba(pixels: readonly (readonly [number, number, number])[], alpha = 255): number[] {
  return pixels.flatMap(([r, g, b]) => [r, g, b, alpha]);
}

describe("summarizePixels", () => {
  it("mảng đồng màu: rgb_all = rgb_trim, không loại điểm nào", () => {
    const data = new Uint8ClampedArray(
      rgba(Array.from({ length: 100 }, () => [180, 140, 120] as const)),
    );
    const s = summarizePixels([data]);
    expect(s.rgb_all).toEqual([180, 140, 120]);
    expect(s.rgb_trim).toEqual([180, 140, 120]);
    expect(s.excluded_fraction).toBe(0);
    expect(s.pixels).toBe(100);
  });

  it("trung vị với số điểm lẻ, từng kênh độc lập", () => {
    const s = summarizePixels([
      rgba([
        [100, 200, 90],
        [120, 100, 130],
        [110, 150, 110],
      ]),
    ]);
    expect(s.rgb_all).toEqual([110, 150, 110]);
  });

  it("trung vị với số điểm chẵn là trung bình hai giá trị giữa", () => {
    const s = summarizePixels([
      rgba([
        [100, 200, 90],
        [120, 100, 130],
        [110, 150, 110],
        [140, 160, 100],
      ]),
    ]);
    // r: 100,110,120,140 -> 115; g: 100,150,160,200 -> 155; b: 90,100,110,130 -> 105
    expect(s.rgb_all).toEqual([115, 155, 105]);
  });

  it("bỏ qua kênh alpha", () => {
    const a = summarizePixels([rgba([[150, 130, 110]], 255)]);
    const b = summarizePixels([rgba([[150, 130, 110]], 0)]);
    expect(b).toEqual(a);
  });

  it("điểm đen và cháy sáng bị loại khỏi rgb_trim, vẫn đếm trong pixels", () => {
    const s = summarizePixels([
      rgba([
        [0, 0, 0],
        [255, 255, 255],
        [150, 130, 110],
        [150, 130, 110],
      ]),
    ]);
    expect(s.pixels).toBe(4);
    expect(s.rgb_trim).toEqual([150, 130, 110]);
    expect(s.excluded_fraction).toBe(0.5);
  });

  it("rgb_all khác rgb_trim khi điểm bị loại làm lệch trung vị", () => {
    const s = summarizePixels([
      rgba([
        [0, 0, 0],
        [0, 0, 0],
        [0, 0, 0],
        [150, 130, 110],
      ]),
    ]);
    expect(s.rgb_all).toEqual([0, 0, 0]);
    expect(s.rgb_trim).toEqual([150, 130, 110]);
    expect(s.excluded_fraction).toBe(0.75);
  });

  it("toàn bộ điểm bị loại: rgb_trim null, excluded_fraction 1", () => {
    const s = summarizePixels([
      rgba([
        [0, 0, 0],
        [255, 255, 255],
      ]),
    ]);
    expect(s.rgb_trim).toBeNull();
    expect(s.excluded_fraction).toBe(1);
    expect(s.rgb_all).not.toBeNull();
  });

  it("mảng rỗng: rgb_all null, pixels 0, excluded_fraction 0", () => {
    const s = summarizePixels([[]]);
    expect(s).toEqual({ rgb_all: null, rgb_trim: null, excluded_fraction: 0, pixels: 0 });
    expect(summarizePixels([])).toEqual(s);
  });

  it("gộp nhiều buffer bằng với buffer nối", () => {
    const a = rgba([
      [100, 120, 140],
      [160, 100, 90],
    ]);
    const b = rgba([
      [0, 0, 0],
      [130, 150, 110],
      [200, 180, 160],
    ]);
    expect(summarizePixels([a, b])).toEqual(summarizePixels([[...a, ...b]]));
    expect(summarizePixels([a, b]).pixels).toBe(5);
  });

  it("biên luma: xám 55 và xám 200 bị loại (điều kiện giữ là > 55 và < 200)", () => {
    // Xám đều v: luma = (0.299 + 0.587 + 0.114) * v ~ v. Nếu số thực lệch nhẹ thì test này lộ ra.
    expect(summarizePixels([rgba([[55, 55, 55]])]).rgb_trim).toBeNull();
    expect(summarizePixels([rgba([[200, 200, 200]])]).rgb_trim).toBeNull();
  });

  it("ngay trong ngưỡng thì giữ, ngay ngoài ngưỡng thì loại", () => {
    expect(summarizePixels([rgba([[56, 56, 56]])]).rgb_trim).toEqual([56, 56, 56]);
    expect(summarizePixels([rgba([[54, 54, 54]])]).rgb_trim).toBeNull();
    expect(summarizePixels([rgba([[199, 199, 199]])]).rgb_trim).toEqual([199, 199, 199]);
    expect(summarizePixels([rgba([[201, 201, 201]])]).rgb_trim).toBeNull();
  });

  it("luma tính theo trọng số kênh: xanh lá đóng góp nhiều nhất", () => {
    // luma([0,100,0]) = 58.7 giữ; luma([0,0,100]) = 11.4 loại
    expect(summarizePixels([rgba([[0, 100, 0]])]).rgb_trim).toEqual([0, 100, 0]);
    expect(summarizePixels([rgba([[0, 0, 100]])]).rgb_trim).toBeNull();
  });
});

/** Dựng 478 landmark ở (0.5, 0.5), rồi đặt hộp [x0,x1]x[y0,y1] cho một vùng. */
function makeLandmarks(
  region: SkinRegion,
  box: { x0: number; x1: number; y0: number; y1: number },
): Point[] {
  const pts: Point[] = Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5 }));
  const idx = REGION_LANDMARKS[region];
  pts[idx[0]] = { x: box.x0, y: box.y0 };
  pts[idx[1]] = { x: box.x1, y: box.y1 };
  for (const i of idx.slice(2)) pts[i] = { x: (box.x0 + box.x1) / 2, y: (box.y0 + box.y1) / 2 };
  return pts;
}

describe("skinRegionRects", () => {
  it("hộp bằng hộp bao co 20% mỗi cạnh, làm tròn số nguyên", () => {
    const lm = makeLandmarks("forehead", { x0: 0.4, x1: 0.6, y0: 0.1, y1: 0.2 });
    const r = skinRegionRects(lm, 100, 100);
    // bao: x 40..60, y 10..20; co: dx=4, dy=2
    expect(r.forehead).toEqual({ x: 44, y: 12, w: 12, h: 6 });
  });

  it("width/height khác nhau nhân đúng trục", () => {
    const lm = makeLandmarks("forehead", { x0: 0.4, x1: 0.6, y0: 0.1, y1: 0.2 });
    const r = skinRegionRects(lm, 640, 480);
    // x: 256..384 co 25.6 -> 282..358; y: 48..96 co 9.6 -> 58..86
    expect(r.forehead).toEqual({ x: 282, y: 58, w: 76, h: 28 });
  });

  it("shrink = 0 trả hộp bao nguyên", () => {
    const lm = makeLandmarks("chin", { x0: 0.3, x1: 0.7, y0: 0.6, y1: 0.9 });
    const r = skinRegionRects(lm, 200, 100, 0);
    expect(r.chin).toEqual({ x: 60, y: 60, w: 80, h: 30 });
  });

  it("vùng chỉ có landmark trùng một điểm thì hộp suy biến thành null", () => {
    const lm = makeLandmarks("forehead", { x0: 0.4, x1: 0.6, y0: 0.1, y1: 0.2 });
    const r = skinRegionRects(lm, 100, 100);
    expect(r.nose).toBeNull();
    expect(r.chin).toBeNull();
  });

  it("vùng ra ngoài khung hình hoàn toàn thì null", () => {
    const lm = makeLandmarks("nose", { x0: 1.2, x1: 1.5, y0: 0.2, y1: 0.4 });
    expect(skinRegionRects(lm, 100, 100, 0).nose).toBeNull();
  });

  it("hộp bị kẹp trong khung hình", () => {
    const lm = makeLandmarks("nose", { x0: -0.2, x1: 0.3, y0: 0.7, y1: 1.4 });
    expect(skinRegionRects(lm, 100, 100, 0).nose).toEqual({ x: 0, y: 70, w: 30, h: 30 });
  });

  it("landmark thiếu thì vùng đó null, không ném lỗi", () => {
    const lm = makeLandmarks("forehead", { x0: 0.4, x1: 0.6, y0: 0.1, y1: 0.2 });
    const short = lm.slice(0, 340); // thiếu chỉ số >= 340 (má phải, cằm; trán dùng tối đa 338)
    let r: ReturnType<typeof skinRegionRects> | undefined;
    expect(() => {
      r = skinRegionRects(short, 100, 100);
    }).not.toThrow();
    expect(r?.right_cheek).toBeNull();
    expect(r?.chin).toBeNull();
    expect(r?.forehead).not.toBeNull();
    expect(skinRegionRects([], 100, 100).forehead).toBeNull();
  });
});

describe("faceBox", () => {
  it("là hộp bao mọi landmark, đơn vị điểm ảnh", () => {
    const pts: Point[] = [
      { x: 0.2, y: 0.3 },
      { x: 0.8, y: 0.4 },
      { x: 0.5, y: 0.9 },
    ];
    const b = faceBox(pts, 100, 200);
    expect(b.x).toBeCloseTo(20);
    expect(b.y).toBeCloseTo(60);
    expect(b.w).toBeCloseTo(60);
    expect(b.h).toBeCloseTo(120);
  });
});

describe("backgroundRects", () => {
  const W = 640;
  const H = 480;
  const size = Math.round(W * 0.12);

  it("không có mặt: hai ô góc trên, cạnh = round(width*0.12)", () => {
    expect(size).toBe(77);
    expect(backgroundRects(null, W, H)).toEqual([
      { x: 0, y: 0, w: size, h: size },
      { x: W - size, y: 0, w: size, h: size },
    ]);
  });

  it("mặt ở giữa: giữ cả hai ô", () => {
    expect(backgroundRects({ x: 200, y: 100, w: 240, h: 300 }, W, H)).toHaveLength(2);
  });

  it("mặt chạm góc trái-trên: bỏ ô trái, giữ ô phải", () => {
    const r = backgroundRects({ x: 0, y: 0, w: 300, h: 300 }, W, H);
    expect(r).toEqual([{ x: W - size, y: 0, w: size, h: size }]);
  });

  it("mặt cách ô một khoảng nhỏ hơn lề 10% vẫn bị tính là chạm", () => {
    // ô trái kết thúc ở x=77; mặt bắt đầu x=90, rộng 200 -> lề 20 -> guard bắt đầu x=70 < 77
    const r = backgroundRects({ x: 90, y: 0, w: 200, h: 200 }, W, H);
    expect(r).toEqual([{ x: W - size, y: 0, w: size, h: size }]);
  });

  it("mặt phủ cả hai góc: mảng rỗng", () => {
    expect(backgroundRects({ x: 0, y: 0, w: W, h: H }, W, H)).toEqual([]);
  });

  it("mọi ô nằm trong khung hình", () => {
    for (const r of backgroundRects(null, 100, 50)) {
      expect(r.x).toBeGreaterThanOrEqual(0);
      expect(r.y).toBeGreaterThanOrEqual(0);
      expect(r.x + r.w).toBeLessThanOrEqual(100);
      expect(r.y + r.h).toBeLessThanOrEqual(50);
    }
  });
});

describe("REGION_DEFS và hằng số", () => {
  it("có landmarks cho đủ 5 vùng da, shrink_fraction và background_rule", () => {
    expect(Object.keys(REGION_DEFS.landmarks).sort()).toEqual(
      ["chin", "forehead", "left_cheek", "nose", "right_cheek"].sort(),
    );
    expect(REGION_DEFS.shrink_fraction).toBe(0.2);
    expect(REGION_DEFS.background_rule.length).toBeGreaterThan(0);
  });

  it("REGION_NAMES gồm 6 tên, có background", () => {
    expect(REGION_NAMES).toHaveLength(6);
    expect(new Set(REGION_NAMES).size).toBe(6);
    expect(REGION_NAMES).toContain("background");
    expect(SKIN_REGIONS).toHaveLength(5);
  });

  it("chỉ số landmark là số nguyên 0..477", () => {
    for (const name of SKIN_REGIONS) {
      for (const i of REGION_LANDMARKS[name]) {
        expect(Number.isInteger(i)).toBe(true);
        expect(i).toBeGreaterThanOrEqual(0);
        expect(i).toBeLessThanOrEqual(477);
      }
    }
  });

  it("không trùng chỉ số landmark giữa các vùng da", () => {
    const all = SKIN_REGIONS.flatMap((n) => [...REGION_LANDMARKS[n]]);
    expect(new Set(all).size).toBe(all.length);
  });
});
