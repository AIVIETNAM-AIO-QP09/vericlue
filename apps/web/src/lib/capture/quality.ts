// Cổng chất lượng ảnh chạy NGAY trong trình duyệt, trước khi gửi bất cứ gì lên máy chủ (architecture §6 bước 2).
// Hàm thuần: nhận số liệu và mảng điểm ảnh, không DOM, không đồng hồ; test bằng số liệu tổng hợp.
//
// Nguyên tắc:
//  - mỗi lần chỉ MỘT chỉ dẫn, theo thứ tự ưu tiên cố định (`pickGuidance`);
//  - chỉ dẫn chỉ nói về CHẤT LƯỢNG ảnh, không bao giờ nói về giả mạo;
//  - không đo được thì KHÔNG bao giờ coi là đạt (số không hữu hạn, thiếu landmark, ...);
//  - QUÁ SÁNG (nắng chiếu thẳng, nhiều điểm ảnh cháy sáng) không bao giờ được coi là đạt;
//  - đạt phải liên tục `QUALITY_REQUIRED_FRAMES` khung; một khung kém đặt lại bộ đếm (xem flow.ts).
//
// Bảng ngưỡng: mỗi hằng số ghi NGUỒN. "tài liệu" = có số trong docs/plan/epics/E2-capture.md (CAP-02);
// "TẠM" = tài liệu chưa có số, nhóm đặt tạm, CHỈNH KHI THỬ MÁY THẬT (không chỉnh theo dữ liệu test).

import { type Point, type Rect, faceBox } from "./chromapulse/regions";

// --- Ngưỡng có trong tài liệu (CAP-02) -------------------------------------------------------------
/** Mặt chiếm tối thiểu chừng này chiều rộng khung (tài liệu: 35%). Dưới mức này là xa. */
export const FACE_WIDTH_MIN_FRACTION = 0.35;
/** Mặt chiếm tối đa chừng này chiều rộng khung (tài liệu: 60%). Trên mức này là gần. */
export const FACE_WIDTH_MAX_FRACTION = 0.6;
/** IoU tối thiểu giữa hộp mặt và oval (tài liệu: >= 0,6). */
export const OVAL_IOU_MIN = 0.6;
/** Góc quay đầu tối đa, tính bằng độ (tài liệu: <= 20). */
export const YAW_MAX_DEG = 20;
/** Số khung hình mỗi giây tối thiểu của camera (tài liệu: >= 15). */
export const MIN_FPS = 15;
/** Độ phân giải tối thiểu (tài liệu: từ 640x480 trở lên); so theo cạnh ngắn và cạnh dài, không phụ thuộc hướng. */
export const MIN_SHORT_SIDE = 480;
export const MIN_LONG_SIDE = 640;

// --- Ngưỡng TẠM (tài liệu chưa có số; chỉnh khi thử máy thật) -------------------------------------
/** TẠM — chỉnh khi thử máy thật. Số khung LIÊN TỤC đạt trước khi cho đi tiếp (khoảng 1 giây ở ~8 lần đo/giây). */
export const QUALITY_REQUIRED_FRAMES = 8;
/** TẠM — chỉnh khi thử máy thật. Oval rộng chừng này chiều rộng khung. */
export const OVAL_WIDTH_FRACTION = 0.55;
/** TẠM — chỉnh khi thử máy thật. Chiều cao oval = chiều rộng nhân hệ số này. */
export const OVAL_ASPECT = 1.3;
/** TẠM — chỉnh khi thử máy thật. Oval không cao quá chừng này chiều cao khung (khung ngang như laptop). */
export const OVAL_MAX_HEIGHT_FRACTION = 0.9;
/** TẠM — chỉnh khi thử máy thật. Tâm mặt lệch khỏi tâm khung quá chừng này (theo từng chiều) là chưa vào giữa. */
export const CENTER_TOLERANCE_FRACTION = 0.15;
/** TẠM — chỉnh khi thử máy thật. Độ sáng trung bình (0-255) của vùng mặt thấp hơn mức này là thiếu sáng. */
export const MEAN_LUMA_MIN = 70;
/** TẠM — chỉnh khi thử máy thật. Độ sáng trung bình cao hơn mức này là quá sáng. */
export const MEAN_LUMA_MAX = 190;
/** TẠM — chỉnh khi thử máy thật. Điểm ảnh có độ sáng từ mức này trở lên là "cháy sáng". */
export const BLOWN_LUMA = 250;
/** TẠM — chỉnh khi thử máy thật. Quá chừng này tỉ lệ điểm ảnh cháy sáng là quá sáng (nắng chiếu thẳng). */
export const BLOWN_FRACTION_MAX = 0.12;
/** TẠM — chỉnh khi thử máy thật. Điểm ảnh có độ sáng thấp hơn mức này là "quá tối". */
export const DARK_LUMA = 40;
/** TẠM — chỉnh khi thử máy thật. Quá chừng này tỉ lệ điểm ảnh quá tối là thiếu sáng. */
export const DARK_FRACTION_MAX = 0.5;
/** TẠM — chỉnh khi thử máy thật. Phương sai Laplacian (thang 0-255) thấp hơn mức này là mờ. */
export const SHARPNESS_MIN = 50;
/** TẠM — chỉnh khi thử máy thật. Tâm mặt dịch quá chừng này (tính theo chiều rộng mặt) giữa hai lần đo là chưa yên. */
export const MOVEMENT_MAX_FRACTION = 0.08;
/** TẠM — chỉnh khi thử máy thật. Số lần gọi khung hình dùng để ước lượng FPS. */
export const FPS_WINDOW = 30;
/** TẠM — chỉnh khi thử máy thật. Bỏ qua chừng này lần gọi khung hình đầu (camera đang chỉnh phơi sáng, khởi động). */
export const FPS_WARMUP_CALLBACKS = 15;
/** TẠM — chỉnh khi thử máy thật. Cần chừng này cửa sổ FPS thấp LIÊN TIẾP mới báo "thiết bị chưa đáp ứng". */
export const FPS_LOW_WINDOWS_REQUIRED = 2;

// --- Kiểu dữ liệu ----------------------------------------------------------------------------------

/** Chỉ dẫn của cổng chất lượng. KHÔNG phải RetryHint của API (hợp đồng): đây là chỉ dẫn cục bộ ở web. */
export type QualityGuidance =
  | "NO_FACE"
  | "MULTIPLE_FACES"
  | "FACE_CENTER"
  | "MOVE_CLOSER"
  | "MOVE_BACK"
  | "TURN_STRAIGHT"
  | "TOO_BRIGHT"
  | "LOW_LIGHT"
  | "HOLD_STILL"
  | "BLURRY";

/** Thứ tự ưu tiên (đầu danh sách = quan trọng nhất). FPS thấp KHÔNG nằm đây: có màn báo riêng (flow.ts). */
export const GUIDANCE_PRIORITY: readonly QualityGuidance[] = [
  "NO_FACE",
  "MULTIPLE_FACES",
  "FACE_CENTER",
  "MOVE_CLOSER",
  "MOVE_BACK",
  "TURN_STRAIGHT",
  "TOO_BRIGHT",
  "LOW_LIGHT",
  "HOLD_STILL",
  "BLURRY",
];

export type FrameSize = { width: number; height: number };

/** Số đo của một khung (đơn vị điểm ảnh của khung đã đo). Số không hữu hạn nghĩa là không đo được. */
export type QualityMetrics = {
  faceCount: number;
  frame: FrameSize;
  /** Hộp bao khuôn mặt dựng từ landmark; null nếu không thấy mặt. */
  face: Rect | null;
  /** Góc quay đầu ước lượng (độ, giá trị tuyệt đối); null nếu không tính được. */
  yawDeg: number | null;
  /** Phương sai Laplacian của độ sáng vùng mặt (càng cao càng nét). */
  sharpness: number;
  /** Độ sáng trung bình 0-255 của vùng mặt. */
  meanLuma: number;
  /** Tỉ lệ điểm ảnh cháy sáng (độ sáng >= BLOWN_LUMA), 0-1. */
  blownFraction: number;
  /** Tỉ lệ điểm ảnh quá tối (độ sáng < DARK_LUMA), 0-1. */
  darkFraction: number;
  /** Dịch tâm mặt so với lần đo trước, tính theo chiều rộng mặt; null nếu chưa có lần đo trước. */
  movement: number | null;
};

/** Điểm ảnh RGBA của vùng mặt đã cắt (chỉ để tính số đo, không bao giờ được lưu hay gửi đi). */
export type PixelCrop = { data: ArrayLike<number>; width: number; height: number };

// --- Hình học --------------------------------------------------------------------------------------

/**
 * Oval hướng dẫn đặt mặt, tính bằng điểm ảnh của khung: giữa khung, rộng `OVAL_WIDTH_FRACTION` chiều
 * rộng, cao `OVAL_ASPECT` lần chiều rộng nhưng không quá `OVAL_MAX_HEIGHT_FRACTION` chiều cao khung
 * (khung ngang). Trả về hộp bao của oval.
 */
export function ovalRect(width: number, height: number): Rect {
  const maxHeight = OVAL_MAX_HEIGHT_FRACTION * height;
  const h = Math.min(OVAL_ASPECT * OVAL_WIDTH_FRACTION * width, maxHeight);
  const w = Math.min(OVAL_WIDTH_FRACTION * width, h / OVAL_ASPECT);
  return { x: (width - w) / 2, y: (height - h) / 2, w, h };
}

/** Tỉ lệ giao trên hợp (IoU) của hai hình chữ nhật; 0 nếu không giao hoặc diện tích không hợp lệ. */
export function rectIou(a: Rect, b: Rect): number {
  const x1 = Math.max(a.x, b.x);
  const y1 = Math.max(a.y, b.y);
  const x2 = Math.min(a.x + a.w, b.x + b.w);
  const y2 = Math.min(a.y + a.h, b.y + b.h);
  const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  const union = a.w * a.h + b.w * b.h - inter;
  return union > 0 && Number.isFinite(union) ? inter / union : 0;
}

/** Vùng cần cắt điểm ảnh quanh mặt: hộp mặt làm tròn và kẹp trong khung; null nếu rỗng. */
export function cropRectForFace(face: Rect, frame: FrameSize): Rect | null {
  if (!(face.w > 0 && face.h > 0)) return null; // hộp rỗng không có điểm ảnh để đo
  const x = Math.max(0, Math.floor(face.x));
  const y = Math.max(0, Math.floor(face.y));
  const x2 = Math.min(frame.width, Math.ceil(face.x + face.w));
  const y2 = Math.min(frame.height, Math.ceil(face.y + face.h));
  return x2 - x >= 1 && y2 - y >= 1 ? { x, y, w: x2 - x, h: y2 - y } : null;
}

// Chỉ số landmark MediaPipe (478 điểm): đầu mũi và hai mép ngoài của khuôn mặt.
const LANDMARK_NOSE = 1;
const LANDMARK_FACE_LEFT = 234;
const LANDMARK_FACE_RIGHT = 454;

/**
 * Góc quay đầu ước lượng (độ, trị tuyệt đối) từ vị trí đầu mũi so với hai mép mặt:
 * sin(yaw) = (x mũi − x giữa) / nửa chiều rộng mặt. Gần đúng, đủ để chặn mặt nghiêng nhiều.
 * Null nếu thiếu landmark hoặc hình học vô lý.
 */
export function yawDegrees(landmarks: readonly Point[]): number | null {
  const nose = landmarks[LANDMARK_NOSE];
  const left = landmarks[LANDMARK_FACE_LEFT];
  const right = landmarks[LANDMARK_FACE_RIGHT];
  if (!nose || !left || !right) return null;
  const half = Math.abs(right.x - left.x) / 2;
  if (!(half > 0) || !Number.isFinite(half)) return null;
  const mid = (left.x + right.x) / 2;
  const s = (nose.x - mid) / half;
  if (!Number.isFinite(s)) return null;
  return (Math.asin(Math.max(-1, Math.min(1, s))) * 180) / Math.PI;
}

/** Dịch tâm hộp mặt so với lần trước, chia cho chiều rộng mặt hiện tại; null nếu chưa có lần trước. */
export function movementFraction(prev: Rect | null, cur: Rect): number | null {
  if (!prev || !(cur.w > 0)) return null;
  const dx = prev.x + prev.w / 2 - (cur.x + cur.w / 2);
  const dy = prev.y + prev.h / 2 - (cur.y + cur.h / 2);
  return Math.hypot(dx, dy) / cur.w;
}

// --- Điểm ảnh --------------------------------------------------------------------------------------

/** Độ sáng (luma) của từng điểm ảnh RGBA, công thức 0,299R + 0,587G + 0,114B (alpha bị bỏ qua). */
export function lumaOf(rgba: ArrayLike<number>): Float32Array {
  const n = Math.floor(rgba.length / 4);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i += 1) {
    out[i] = 0.299 * rgba[i * 4] + 0.587 * rgba[i * 4 + 1] + 0.114 * rgba[i * 4 + 2];
  }
  return out;
}

/**
 * Phương sai của Laplacian 4 láng giềng trên các điểm ảnh bên trong; càng cao càng nét.
 * Ảnh nhỏ hơn 3x3 hoặc kích thước không khớp dữ liệu trả 0 (coi là không nét).
 */
export function laplacianVariance(luma: ArrayLike<number>, width: number, height: number): number {
  if (width < 3 || height < 3 || luma.length < width * height) return 0;
  let sum = 0;
  let sumSq = 0;
  let count = 0;
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const i = y * width + x;
      const lap = 4 * luma[i] - luma[i - 1] - luma[i + 1] - luma[i - width] - luma[i + width];
      sum += lap;
      sumSq += lap * lap;
      count += 1;
    }
  }
  const mean = sum / count;
  return sumSq / count - mean * mean;
}

export type LumaStats = { mean: number; blownFraction: number; darkFraction: number };

/** Độ sáng trung bình cùng tỉ lệ điểm ảnh cháy sáng và quá tối. Mảng rỗng cho NaN (không đo được). */
export function lumaStats(luma: ArrayLike<number>): LumaStats {
  const n = luma.length;
  if (n === 0) return { mean: Number.NaN, blownFraction: Number.NaN, darkFraction: Number.NaN };
  let sum = 0;
  let blown = 0;
  let dark = 0;
  for (let i = 0; i < n; i += 1) {
    const v = luma[i];
    sum += v;
    if (v >= BLOWN_LUMA) blown += 1;
    if (v < DARK_LUMA) dark += 1;
  }
  return { mean: sum / n, blownFraction: blown / n, darkFraction: dark / n };
}

// --- FPS và thiết bị -------------------------------------------------------------------------------

/**
 * FPS ước lượng từ các mốc thời gian (ms) của các lần gọi khung hình: lấy trung vị khoảng cách giữa hai
 * khung kề nhau (chống ngoại lệ). Cần ít nhất 10 mốc; ít hơn thì chưa kết luận (null).
 */
export function estimateFps(timesMs: readonly number[]): number | null {
  if (timesMs.length < 10) return null;
  const gaps: number[] = [];
  for (let i = 1; i < timesMs.length; i += 1) {
    const gap = timesMs[i] - timesMs[i - 1];
    if (gap > 0 && Number.isFinite(gap)) gaps.push(gap);
  }
  if (gaps.length === 0) return null;
  gaps.sort((a, b) => a - b);
  const mid = gaps.length >> 1;
  const median = gaps.length % 2 ? gaps[mid] : (gaps[mid - 1] + gaps[mid]) / 2;
  return 1000 / median;
}

export type FpsVerdict = "ok" | "low" | "need_more";

/**
 * Kết luận về FPS từ các cửa sổ đo lần lượt (mỗi phần tử là FPS của một cửa sổ; null = chưa ước lượng được).
 * Chống báo oan: một cửa sổ thấp chưa đủ, phải thấp LIÊN TIẾP `FPS_LOW_WINDOWS_REQUIRED` cửa sổ; một cửa sổ
 * đạt (>= 15) là đủ để coi là ổn. Chưa đủ thông tin thì "need_more" (tiếp tục đo, không kết luận).
 */
export function evaluateFpsWindows(windows: readonly (number | null)[]): FpsVerdict {
  const last = windows[windows.length - 1];
  if (last === undefined || last === null) return "need_more";
  if (!isFpsTooLow(last)) return "ok";
  let lowRun = 0;
  for (let i = windows.length - 1; i >= 0; i -= 1) {
    const w = windows[i];
    if (w !== null && isFpsTooLow(w)) lowRun += 1;
    else break;
  }
  return lowRun >= FPS_LOW_WINDOWS_REQUIRED ? "low" : "need_more";
}

/** Camera dưới 15 khung/giây (chưa biết FPS thì không kết luận là chậm). */
export function isFpsTooLow(fps: number | null): boolean {
  return fps !== null && fps < MIN_FPS;
}

/** Độ phân giải thấp hơn 640x480 (theo cạnh ngắn và cạnh dài, không phụ thuộc hướng dọc/ngang). */
export function isResolutionTooLow(width: number, height: number): boolean {
  const short = Math.min(width, height);
  const long = Math.max(width, height);
  return !(short >= MIN_SHORT_SIDE && long >= MIN_LONG_SIDE);
}

// --- Số đo và chỉ dẫn ------------------------------------------------------------------------------

export type FrameAnalysisInput = {
  faceCount: number;
  /** 478 điểm chuẩn hóa 0..1 của khuôn mặt chính; null nếu không thấy mặt. */
  landmarks: readonly Point[] | null;
  frame: FrameSize;
  /** Điểm ảnh RGBA đúng vùng `cropRectForFace(face, frame)`; null nếu không có. */
  crop: PixelCrop | null;
  /** Hộp mặt của lần đo trước, để tính độ yên. */
  prevFace: Rect | null;
};

/** Gom số đo của một khung. Thiếu dữ liệu thì các số là NaN/null (pickGuidance sẽ không cho qua). */
export function analyzeFrame(input: FrameAnalysisInput): QualityMetrics {
  const { faceCount, landmarks, frame, crop, prevFace } = input;
  const face =
    landmarks && landmarks.length > 0 ? faceBox(landmarks, frame.width, frame.height) : null;
  const validFace = face && face.w > 0 && face.h > 0 ? face : null;
  const luma = crop ? lumaOf(crop.data) : null;
  const stats = luma ? lumaStats(luma) : null;
  return {
    faceCount,
    frame,
    face: validFace,
    yawDeg: landmarks && validFace ? absOrNull(yawDegrees(landmarks)) : null,
    sharpness: crop && luma ? laplacianVariance(luma, crop.width, crop.height) : Number.NaN,
    meanLuma: stats ? stats.mean : Number.NaN,
    blownFraction: stats ? stats.blownFraction : Number.NaN,
    darkFraction: stats ? stats.darkFraction : Number.NaN,
    movement: validFace ? movementFraction(prevFace, validFace) : null,
  };
}

function absOrNull(value: number | null): number | null {
  return value === null ? null : Math.abs(value);
}

function allFinite(...values: number[]): boolean {
  return values.every((v) => Number.isFinite(v));
}

/**
 * Chọn MỘT chỉ dẫn theo thứ tự `GUIDANCE_PRIORITY`; null nghĩa là khung này đạt mọi tiêu chí.
 * Không đo được (không thấy mặt, số không hữu hạn, thiếu yaw hay độ yên) KHÔNG bao giờ trả null.
 */
export function pickGuidance(m: QualityMetrics): QualityGuidance | null {
  if (m.faceCount > 1) return "MULTIPLE_FACES";
  const { face, frame } = m;
  if (m.faceCount < 1 || !face || !allFinite(frame.width, frame.height) || frame.width <= 0) {
    return "NO_FACE";
  }
  if (!allFinite(m.sharpness, m.meanLuma, m.blownFraction, m.darkFraction)) return "NO_FACE";

  // Vị trí: tâm mặt lệch khỏi tâm khung.
  const dx = Math.abs(face.x + face.w / 2 - frame.width / 2) / frame.width;
  const dy = Math.abs(face.y + face.h / 2 - frame.height / 2) / frame.height;
  if (dx > CENTER_TOLERANCE_FRACTION || dy > CENTER_TOLERANCE_FRACTION) return "FACE_CENTER";

  // Khoảng cách: chiều rộng mặt so với chiều rộng khung (35-60%).
  const ratio = face.w / frame.width;
  if (ratio < FACE_WIDTH_MIN_FRACTION) return "MOVE_CLOSER";
  if (ratio > FACE_WIDTH_MAX_FRACTION) return "MOVE_BACK";

  // Khớp oval (IoU >= 0,6); lệch thì nói theo hướng to/nhỏ hơn oval.
  const oval = ovalRect(frame.width, frame.height);
  if (rectIou(face, oval) < OVAL_IOU_MIN) {
    if (face.w < oval.w) return "MOVE_CLOSER";
    if (face.w > oval.w) return "MOVE_BACK";
    return "FACE_CENTER";
  }

  // Nghiêng đầu (<= 20 độ); không tính được thì không cho qua.
  if (m.yawDeg === null || !Number.isFinite(m.yawDeg) || Math.abs(m.yawDeg) > YAW_MAX_DEG) {
    return "TURN_STRAIGHT";
  }

  // Ánh sáng: quá sáng đứng TRƯỚC thiếu sáng và không bao giờ được coi là đạt.
  if (m.blownFraction > BLOWN_FRACTION_MAX || m.meanLuma > MEAN_LUMA_MAX) return "TOO_BRIGHT";
  if (m.meanLuma < MEAN_LUMA_MIN || m.darkFraction > DARK_FRACTION_MAX) return "LOW_LIGHT";

  // Yên và nét; chưa có lần đo trước thì chưa xác nhận được là yên.
  if (m.movement === null || !Number.isFinite(m.movement) || m.movement > MOVEMENT_MAX_FRACTION) {
    return "HOLD_STILL";
  }
  if (m.sharpness < SHARPNESS_MIN) return "BLURRY";

  return null;
}
