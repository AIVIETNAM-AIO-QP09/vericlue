// Vùng đo màu trên khuôn mặt: 5 vùng da (trán, má trái, má phải, mũi, cằm) và vùng nền.
// Hàm thuần: nhận landmark chuẩn hóa (0..1) và mảng điểm ảnh RGBA; việc đọc canvas nằm ở nơi khác.
// Định nghĩa vùng được ghi vào mọi file JSON (`region_defs`) để PRES-01 biết đo ở đâu.

export type SkinRegion = "forehead" | "left_cheek" | "right_cheek" | "nose" | "chin";
export type RegionName = SkinRegion | "background";

export const SKIN_REGIONS: readonly SkinRegion[] = [
  "forehead",
  "left_cheek",
  "right_cheek",
  "nose",
  "chin",
];
export const REGION_NAMES: readonly RegionName[] = [...SKIN_REGIONS, "background"];

/** Chỉ số landmark MediaPipe Face Landmarker (478 điểm) quanh mỗi vùng. "Trái/phải" theo khung hình. */
export const REGION_LANDMARKS: Record<SkinRegion, readonly number[]> = {
  forehead: [10, 109, 338, 67, 297, 103, 332, 151],
  left_cheek: [50, 101, 118, 117, 123, 205, 187],
  right_cheek: [280, 330, 347, 346, 352, 425, 411],
  nose: [1, 4, 5, 6, 195, 197, 98, 327],
  chin: [152, 175, 199, 200, 377, 148, 176],
};

/** Co hộp bao của các landmark vào trong mỗi cạnh 20% để tránh mép (tóc, môi, mắt). */
export const REGION_SHRINK = 0.2;
/** Vùng nền: hai ô vuông ở hai góc trên của khung hình, cạnh = 12% chiều rộng, ngoài hộp khuôn mặt. */
export const BACKGROUND_SIZE_FRACTION = 0.12;
/** Lề thêm quanh hộp khuôn mặt (10% mỗi cạnh) khi kiểm ô nền có chạm mặt không. */
export const FACE_MARGIN_FRACTION = 0.1;
/** Điểm ảnh có độ sáng (luma) ≤ 55 hoặc ≥ 200 bị loại ở bản `rgb_trim` (đồng bộ với PRES-02). */
export const LUMA_EXCLUDE_LOW = 55;
export const LUMA_EXCLUDE_HIGH = 200;

export type Point = { x: number; y: number };
export type Rect = { x: number; y: number; w: number; h: number };

export const REGION_DEFS = {
  landmarks: REGION_LANDMARKS,
  shrink_fraction: REGION_SHRINK,
  skin_region_rule:
    "Hộp bao các landmark liệt kê, co vào mỗi cạnh `shrink_fraction`; trái/phải theo khung hình (ảnh gương của người)",
  background_rule: `Hai ô vuông ở góc trên-trái và trên-phải, cạnh ${BACKGROUND_SIZE_FRACTION} chiều rộng khung hình; ô nào chạm hộp khuôn mặt (cộng lề ${FACE_MARGIN_FRACTION}) bị bỏ; nền = trung vị gộp các ô còn lại`,
  rgb_all: "Trung vị từng kênh trên mọi điểm ảnh của vùng",
  rgb_trim: `Trung vị từng kênh sau khi bỏ điểm ảnh có luma (0.299R+0.587G+0.114B) <= ${LUMA_EXCLUDE_LOW} hoặc >= ${LUMA_EXCLUDE_HIGH}; null nếu không còn điểm nào`,
  excluded_fraction: "Tỉ lệ điểm ảnh bị bỏ ở rgb_trim (0..1)",
} as const;

function bounds(points: readonly Point[], width: number, height: number): Rect {
  const xs = points.map((p) => p.x * width);
  const ys = points.map((p) => p.y * height);
  const x0 = Math.min(...xs);
  const y0 = Math.min(...ys);
  return { x: x0, y: y0, w: Math.max(...xs) - x0, h: Math.max(...ys) - y0 };
}

function clampRect(r: Rect, width: number, height: number): Rect | null {
  const x = Math.max(0, Math.round(r.x));
  const y = Math.max(0, Math.round(r.y));
  const x1 = Math.min(width, Math.round(r.x + r.w));
  const y1 = Math.min(height, Math.round(r.y + r.h));
  return x1 - x >= 1 && y1 - y >= 1 ? { x, y, w: x1 - x, h: y1 - y } : null;
}

/** Hộp bao toàn bộ khuôn mặt (mọi landmark), đơn vị điểm ảnh. */
export function faceBox(landmarks: readonly Point[], width: number, height: number): Rect {
  return bounds(landmarks, width, height);
}

/** Hộp điểm ảnh của 5 vùng da; vùng nào ra ngoài khung hình hoàn toàn thì là null. */
export function skinRegionRects(
  landmarks: readonly Point[],
  width: number,
  height: number,
  shrink: number = REGION_SHRINK,
): Record<SkinRegion, Rect | null> {
  const out = {} as Record<SkinRegion, Rect | null>;
  for (const name of SKIN_REGIONS) {
    const pts = REGION_LANDMARKS[name].map((i) => landmarks[i]);
    if (pts.some((p) => !p)) {
      out[name] = null;
      continue;
    }
    const b = bounds(pts, width, height);
    const dx = b.w * shrink;
    const dy = b.h * shrink;
    out[name] = clampRect(
      { x: b.x + dx, y: b.y + dy, w: b.w - 2 * dx, h: b.h - 2 * dy },
      width,
      height,
    );
  }
  return out;
}

function intersects(a: Rect, b: Rect): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

/** Hai ô nền ở góc trên; ô chạm hộp khuôn mặt (kèm lề) bị bỏ. */
export function backgroundRects(face: Rect | null, width: number, height: number): Rect[] {
  const size = Math.round(width * BACKGROUND_SIZE_FRACTION);
  const candidates: Rect[] = [
    { x: 0, y: 0, w: size, h: size },
    { x: width - size, y: 0, w: size, h: size },
  ];
  const guard: Rect | null = face
    ? {
        x: face.x - face.w * FACE_MARGIN_FRACTION,
        y: face.y - face.h * FACE_MARGIN_FRACTION,
        w: face.w * (1 + 2 * FACE_MARGIN_FRACTION),
        h: face.h * (1 + 2 * FACE_MARGIN_FRACTION),
      }
    : null;
  return candidates
    .map((r) => clampRect(r, width, height))
    .filter((r): r is Rect => r !== null && (guard === null || !intersects(r, guard)));
}

export type RegionStat = {
  rgb_all: [number, number, number] | null;
  rgb_trim: [number, number, number] | null;
  excluded_fraction: number;
  pixels: number;
};

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function medianRgb(r: number[], g: number[], b: number[]): [number, number, number] | null {
  return r.length ? [median(r), median(g), median(b)] : null;
}

/** Thống kê màu của một hoặc nhiều mảng điểm ảnh RGBA (alpha bị bỏ qua). */
export function summarizePixels(buffers: readonly ArrayLike<number>[]): RegionStat {
  const all: [number[], number[], number[]] = [[], [], []];
  const kept: [number[], number[], number[]] = [[], [], []];
  for (const data of buffers) {
    for (let i = 0; i + 3 < data.length; i += 4) {
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      all[0].push(r);
      all[1].push(g);
      all[2].push(b);
      const luma = 0.299 * r + 0.587 * g + 0.114 * b;
      if (luma > LUMA_EXCLUDE_LOW && luma < LUMA_EXCLUDE_HIGH) {
        kept[0].push(r);
        kept[1].push(g);
        kept[2].push(b);
      }
    }
  }
  const pixels = all[0].length;
  return {
    rgb_all: medianRgb(...all),
    rgb_trim: medianRgb(...kept),
    excluded_fraction: pixels === 0 ? 0 : (pixels - kept[0].length) / pixels,
    pixels,
  };
}
