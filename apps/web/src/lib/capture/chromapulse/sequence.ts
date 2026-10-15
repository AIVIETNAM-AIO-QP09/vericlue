// Chuỗi màu ChromaPulse: bộ sinh, kiểm an toàn (ADR-0011) và đường thời gian để vẽ.
// Hàm thuần, không đọc đồng hồ: thời gian do người gọi truyền vào (performance.now()).

import { type ChromaPulseConfig, type Rgb, chromaPulseConfig, hexToRgb } from "./config";

export type SequenceStep = {
  index: number;
  rgb: string;
  holdMs: number;
  transitionMs: number;
};

/** Độ chói tương đối theo WCAG (cùng công thức với services/api/.../challenge.py). */
export function relativeLuminance(hex: string): number {
  const lin = hexToRgb(hex).map((v) => {
    const c = v / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
}

/** R / (R + G + B): đo độ "đỏ bão hòa". */
export function redShare(hex: string): number {
  const [r, g, b] = hexToRgb(hex);
  const sum = r + g + b;
  return sum === 0 ? 0 : r / sum;
}

/** Kiểm bảng màu theo giới hạn an toàn; trả danh sách lỗi (rỗng = đạt). */
export function paletteProblems(
  palette: readonly string[],
  cfg: ChromaPulseConfig = chromaPulseConfig,
): string[] {
  const problems: string[] = [];
  if (palette.length < 2) problems.push("Bảng màu cần ít nhất 2 màu");
  const lum = palette.map(relativeLuminance);
  if (lum.length && Math.max(...lum) - Math.min(...lum) > cfg.maxLuminanceSpread) {
    problems.push(`Chênh độ chói vượt ${cfg.maxLuminanceSpread}`);
  }
  if (palette.some((c) => redShare(c) >= cfg.maxRedShare)) {
    problems.push(`Có màu với R/(R+G+B) >= ${cfg.maxRedShare}`);
  }
  return problems;
}

/** Số lần đổi màu/giây tối đa của một chuỗi (bước ngắn nhất quyết định). */
export function maxChangesPerSecond(steps: readonly SequenceStep[]): number {
  const shortest = Math.min(...steps.map((s) => s.holdMs + s.transitionMs));
  return 1000 / shortest;
}

/**
 * Sinh chuỗi màu: `steps` bước, hai màu liền kề khác nhau, hold ngẫu nhiên trong khoảng cấu hình.
 * `random` mặc định là Math.random (đủ cho trang lab; thử thách thật do server sinh).
 */
export function generateSequence(
  random: () => number = Math.random,
  cfg: ChromaPulseConfig = chromaPulseConfig,
): SequenceStep[] {
  const problems = paletteProblems(cfg.palette, cfg);
  if (problems.length) throw new Error(problems.join("; "));

  const steps: SequenceStep[] = [];
  let previous: string | null = null;
  for (let index = 0; index < cfg.steps; index += 1) {
    const choices = cfg.palette.filter((c) => c !== previous);
    const rgb = choices[Math.floor(random() * choices.length)];
    const holdMs = cfg.holdMinMs + Math.floor(random() * (cfg.holdMaxMs - cfg.holdMinMs + 1));
    steps.push({ index, rgb, holdMs, transitionMs: cfg.transitionMs });
    previous = rgb;
  }
  return steps;
}

export type TimelineSegment = {
  index: number;
  rgb: string;
  /** Mốc (ms kể từ lúc bắt đầu) bắt đầu chuyển sang màu này. */
  startMs: number;
  /** Hết chuyển màu, bắt đầu giữ nguyên. */
  holdStartMs: number;
  /** Hết giữ, bước kế tiếp bắt đầu. */
  endMs: number;
};

export type Timeline = {
  segments: TimelineSegment[];
  /** Mốc bắt đầu chuyển về màu nền sau bước cuối. */
  tailStartMs: number;
  totalMs: number;
  baselineMs: number;
  tailMs: number;
  baselineColor: string;
};

/** Nền xám `baselineMs` → từng bước (chuyển `transitionMs` rồi giữ `holdMs`) → nền xám `tailMs`. */
export function buildTimeline(
  steps: readonly SequenceStep[],
  cfg: ChromaPulseConfig = chromaPulseConfig,
): Timeline {
  let cursor = cfg.baselineMs;
  const segments = steps.map((s) => {
    const seg: TimelineSegment = {
      index: s.index,
      rgb: s.rgb,
      startMs: cursor,
      holdStartMs: cursor + s.transitionMs,
      endMs: cursor + s.transitionMs + s.holdMs,
    };
    cursor = seg.endMs;
    return seg;
  });
  return {
    segments,
    tailStartMs: cursor,
    totalMs: cursor + cfg.tailMs,
    baselineMs: cfg.baselineMs,
    tailMs: cfg.tailMs,
    baselineColor: cfg.baselineColor,
  };
}

function mix(a: Rgb, b: Rgb, t: number): Rgb {
  return [0, 1, 2].map((i) => Math.round(a[i] + (b[i] - a[i]) * t)) as unknown as Rgb;
}

export type ColorAt = {
  rgb: Rgb;
  /** Chỉ số bước đang chiếm ưu thế (-1: nền đầu; steps.length: nền cuối). */
  stepIndex: number;
  done: boolean;
};

/** Màu cần vẽ tại `elapsedMs` kể từ lúc bắt đầu; chuyển màu tuyến tính trong `transitionMs`. */
export function colorAt(
  timeline: Timeline,
  elapsedMs: number,
  transitionMs: number = chromaPulseConfig.transitionMs,
): ColorAt {
  const base = hexToRgb(timeline.baselineColor);
  const first = timeline.segments[0];
  if (elapsedMs >= timeline.totalMs) {
    return { rgb: base, stepIndex: timeline.segments.length, done: true };
  }
  if (!first || elapsedMs < first.startMs) return { rgb: base, stepIndex: -1, done: false };

  if (elapsedMs >= timeline.tailStartMs) {
    const last = timeline.segments[timeline.segments.length - 1];
    const t = Math.min(1, (elapsedMs - timeline.tailStartMs) / transitionMs);
    return {
      rgb: mix(hexToRgb(last.rgb), base, t),
      stepIndex: timeline.segments.length,
      done: false,
    };
  }

  const i = timeline.segments.findIndex((s) => elapsedMs >= s.startMs && elapsedMs < s.endMs);
  const seg = timeline.segments[i];
  const from = i === 0 ? base : hexToRgb(timeline.segments[i - 1].rgb);
  const t = Math.min(1, (elapsedMs - seg.startMs) / Math.max(1, seg.holdStartMs - seg.startMs));
  return { rgb: mix(from, hexToRgb(seg.rgb), t), stepIndex: seg.index, done: false };
}
