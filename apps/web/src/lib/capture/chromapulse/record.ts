// Bản ghi một lần thử ChromaPulse (JSON tải về máy, đầu vào của PRES-01).
// KHÔNG chứa ảnh hay khung hình: chỉ số màu và thời gian. Tên trường `color_events` và `frame_times`
// bám hợp đồng `Signals` (packages/contracts/schemas/session.schema.json) để CAP-04 dùng lại.

import { chromaPulseConfig } from "./config";
import { REGION_DEFS, type RegionName, type RegionStat } from "./regions";
import type { SequenceStep, Timeline } from "./sequence";

export const RECORD_SCHEMA_VERSION = 1;
export const SCENARIOS = ["real", "replay", "obs"] as const;
export type Scenario = (typeof SCENARIOS)[number];

export const PRIVACY_NOTE =
  "Không có ảnh hay khung hình: chỉ số màu và thời gian. Không gửi lên máy chủ.";

export type FrameRecord = {
  index: number;
  /** `now` của requestVideoFrameCallback, cùng đồng hồ performance.now(). */
  now: number;
  media_time: number;
  presented_frames: number;
  /** Chỉ một số trình duyệt có; null nếu không. */
  capture_time: number | null;
  expected_display_time: number | null;
  receive_time: number | null;
  processing_duration: number | null;
  width: number;
  height: number;
  face_found: boolean;
  regions: Partial<Record<RegionName, RegionStat>> | null;
};

export type ColorEvent = { index: number; rgb: string; painted_at: number };
/** Màu thực sự vẽ ở mỗi khung rAF: [t (performance.now), r, g, b]. */
export type DisplaySample = [number, number, number, number];

export type DeviceInfo = {
  label: string;
  user_agent: string;
  platform: string;
  language: string;
  screen: { width: number; height: number; device_pixel_ratio: number };
  hardware_concurrency: number | null;
  camera_label: string | null;
};

export type LabRecord = {
  schema_version: number;
  kind: "chromapulse_lab";
  created_at: string;
  scenario: Scenario;
  take: number;
  note: string;
  privacy: string;
  device: DeviceInfo;
  support: {
    request_video_frame_callback: boolean;
    has_capture_time: boolean;
    frame_metadata_keys: string[];
    landmarker_delegate: string | null;
    clock: "performance.now";
  };
  camera: { settings: Record<string, unknown>; applied_constraints_error: string | null };
  config: {
    palette: readonly string[];
    baseline_color: string;
    baseline_ms: number;
    tail_ms: number;
    transition_ms: number;
    hold_ms: { min: number; max: number };
  };
  sequence: { index: number; rgb: string; hold_ms: number; transition_ms: number }[];
  timeline: { total_ms: number; tail_start_ms: number; start_performance_now: number };
  /** painted_at = thời điểm rAF đầu tiên vẽ bước này (bắt đầu chuyển sang màu mới). */
  color_events: ColorEvent[];
  display_samples: DisplaySample[];
  frame_times: FrameRecord[];
  region_defs: typeof REGION_DEFS;
  /** Chất lượng lần thử: giật, tab ẩn, lỗi lấy mẫu. */
  quality?: { max_raf_gap_ms: number; hidden_during_trial: boolean; sample_errors: number };
};

/** Khoảng cách rAF vượt ngưỡng này (ms) nghĩa là trình duyệt bị đóng băng: dữ liệu không dùng được. */
export const MAX_RAF_GAP_MS = 250;

export function sequenceToRecord(steps: readonly SequenceStep[]): LabRecord["sequence"] {
  return steps.map((s) => ({
    index: s.index,
    rgb: s.rgb,
    hold_ms: s.holdMs,
    transition_ms: s.transitionMs,
  }));
}

export function configToRecord(): LabRecord["config"] {
  const c = chromaPulseConfig;
  return {
    palette: c.palette,
    baseline_color: c.baselineColor,
    baseline_ms: c.baselineMs,
    tail_ms: c.tailMs,
    transition_ms: c.transitionMs,
    hold_ms: { min: c.holdMinMs, max: c.holdMaxMs },
  };
}

export function timelineToRecord(
  timeline: Timeline,
  startPerformanceNow: number,
): LabRecord["timeline"] {
  return {
    total_ms: timeline.totalMs,
    tail_start_ms: timeline.tailStartMs,
    start_performance_now: startPerformanceNow,
  };
}

/** Các khóa metadata mà trình duyệt thực sự trả về cho khung hình (để biết trình duyệt nào có captureTime). */
export function frameMetadataKeys(metadata: object): string[] {
  return Object.keys(metadata).sort();
}

export function summarizeSupport(frames: readonly FrameRecord[]): {
  has_capture_time: boolean;
} {
  return { has_capture_time: frames.some((f) => f.capture_time !== null) };
}

/** Tên file an toàn: <máy>_<trình-duyệt>_<tình-huống>_<lần>.json, chữ thường a-z 0-9 và gạch ngang. */
export function slugify(text: string): string {
  const slug = text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/gi, "d")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "x";
}

export function buildFileName(args: {
  device: string;
  browser: string;
  scenario: Scenario;
  take: number;
}): string {
  const n = Number.isFinite(args.take) ? Math.floor(args.take) : 1;
  const take = String(Math.max(1, n)).padStart(2, "0");
  return `${slugify(args.device)}_${slugify(args.browser)}_${args.scenario}_${take}.json`;
}

/** Danh sách vấn đề của bản ghi (rỗng = dùng được cho PRES-01). */
export function recordProblems(record: LabRecord): string[] {
  const problems: string[] = [];
  if (record.color_events.length !== chromaPulseConfig.steps) {
    problems.push(`Chỉ ghi được ${record.color_events.length}/${chromaPulseConfig.steps} màu`);
  }
  if (record.frame_times.length === 0) problems.push("Không có khung hình nào");
  const found = record.frame_times.filter((f) => f.face_found).length;
  if (record.frame_times.length > 0 && found / record.frame_times.length < 0.8) {
    problems.push(`Chỉ thấy mặt ở ${found}/${record.frame_times.length} khung`);
  }
  const times = record.color_events.map((e) => e.painted_at);
  if (times.some((t, i) => i > 0 && t <= times[i - 1])) {
    problems.push("Nhiều màu có cùng thời điểm vẽ (trình duyệt bị đóng băng), nên thử lại");
  }
  const q = record.quality;
  if (q?.hidden_during_trial) problems.push("Tab bị ẩn hoặc màn hình khóa trong lúc thử");
  if (q && q.max_raf_gap_ms > MAX_RAF_GAP_MS) {
    problems.push(
      `Trình duyệt bị giật: khoảng cách lớn nhất giữa hai lần vẽ ${Math.round(q.max_raf_gap_ms)} ms`,
    );
  }
  if (q && q.sample_errors > 0) problems.push(`${q.sample_errors} khung lấy mẫu bị lỗi`);
  if (!record.support.has_capture_time) problems.push("Trình duyệt này không có captureTime");
  return problems;
}

export function serializeRecord(record: LabRecord): string {
  return JSON.stringify(record);
}
