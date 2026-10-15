import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { chromaPulseConfig } from "./config";
import { MAX_RAF_GAP_MS, MIN_FRAMES, type LabRecord, recordProblems } from "./record";
import type { FrameSampler } from "./sampler";
import { generateSequence } from "./sequence";
import { buildTimeline } from "./sequence";
import { runTrial } from "./trial";

// Môi trường node không có DOM: dựng rAF, document và video giả để chạy vòng thử theo thời gian giả.
type FrameCb = (t: number) => void;

function makeEnv() {
  let rafQueue: FrameCb[] = [];
  const listeners = new Map<string, Set<() => void>>();
  const doc = {
    visibilityState: "visible" as string,
    addEventListener: (name: string, fn: () => void) => {
      if (!listeners.has(name)) listeners.set(name, new Set());
      listeners.get(name)?.add(fn);
    },
    removeEventListener: (name: string, fn: () => void) => listeners.get(name)?.delete(fn),
  };
  vi.stubGlobal("document", doc);
  vi.stubGlobal("requestAnimationFrame", (cb: FrameCb) => {
    rafQueue.push(cb);
    return rafQueue.length;
  });

  const videoCallbacks: Array<(now: number, meta: VideoFrameCallbackMetadata) => void> = [];
  const video = {
    requestVideoFrameCallback: (cb: (now: number, meta: VideoFrameCallbackMetadata) => void) => {
      videoCallbacks.push(cb);
      return videoCallbacks.length;
    },
  } as unknown as HTMLVideoElement;

  const sampler: FrameSampler = {
    sample: () => ({
      faceFound: true,
      regions: {},
      rects: {},
      canvasWidth: 480,
      canvasHeight: 360,
    }),
  };

  return {
    doc,
    listeners,
    video,
    sampler,
    /** Chạy một lượt rAF tại thời điểm t. */
    raf(t: number) {
      const queue = rafQueue;
      rafQueue = [];
      for (const cb of queue) cb(t);
    },
    pendingRaf: () => rafQueue.length,
    /** Phát một khung video. */
    frame(now: number, extra: Partial<VideoFrameCallbackMetadata> = {}) {
      const cb = videoCallbacks.shift();
      cb?.(now, {
        mediaTime: now / 1000,
        presentedFrames: Math.round(now / 33),
        width: 640,
        height: 480,
        expectedDisplayTime: now,
        presentationTime: now,
        ...extra,
      } as VideoFrameCallbackMetadata);
    },
    pendingVideo: () => videoCallbacks.length,
  };
}

describe("runTrial", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  const steps = generateSequence(() => 0.5);
  const total = buildTimeline(steps).totalMs;

  it("chạy hết chuỗi: 8 sự kiện màu tăng chặt, có khung video, không hủy", async () => {
    const env = makeEnv();
    const promise = runTrial({ video: env.video, sampler: env.sampler, steps, onColor: () => {} });

    let i = 0;
    for (let t = 1000; t <= 1000 + total + 100; t += 16) {
      env.raf(t);
      if (i % 2 === 0) env.frame(t);
      i += 1;
    }
    const result = await promise;

    expect(result.aborted).toBe(false);
    expect(result.colorEvents).toHaveLength(chromaPulseConfig.steps);
    const times = result.colorEvents.map((e) => e.painted_at);
    expect(times.every((v, i) => i === 0 || v > times[i - 1])).toBe(true);
    expect(result.frames.length).toBeGreaterThan(10);
    expect(result.maxRafGapMs).toBeLessThanOrEqual(16);
    expect(result.hiddenDuringTrial).toBe(false);
    expect(env.listeners.get("visibilitychange")?.size).toBe(0); // đã gỡ listener
    expect(env.pendingRaf()).toBe(0);
  });

  it("bấm Dừng (abort) có tác dụng ngay, kể cả khi rAF không chạy nữa", async () => {
    const env = makeEnv();
    const controller = new AbortController();
    const promise = runTrial({
      video: env.video,
      sampler: env.sampler,
      steps,
      onColor: () => {},
      signal: controller.signal,
    });
    env.raf(1000);
    controller.abort(); // không gọi thêm raf nào

    const result = await promise;
    expect(result.aborted).toBe(true);
  });

  it("đã abort từ trước thì kết thúc ngay và không đăng ký gì thêm", async () => {
    const env = makeEnv();
    const controller = new AbortController();
    controller.abort();
    const result = await runTrial({
      video: env.video,
      sampler: env.sampler,
      steps,
      onColor: () => {},
      signal: controller.signal,
    });
    expect(result.aborted).toBe(true);
    expect(env.pendingRaf()).toBe(0);
    expect(env.pendingVideo()).toBe(0);
  });

  it("tab bị ẩn hủy lần thử và ghi cờ hiddenDuringTrial", async () => {
    const env = makeEnv();
    const promise = runTrial({ video: env.video, sampler: env.sampler, steps, onColor: () => {} });
    env.raf(1000);
    env.doc.visibilityState = "hidden";
    env.listeners.get("visibilitychange")?.forEach((fn) => fn());

    const result = await promise;
    expect(result.aborted).toBe(true);
    expect(result.hiddenDuringTrial).toBe(true);
  });

  it("rAF bị đóng băng rồi chạy lại: ghi khoảng cách lớn nhất", async () => {
    const env = makeEnv();
    const promise = runTrial({ video: env.video, sampler: env.sampler, steps, onColor: () => {} });
    env.raf(1000);
    env.raf(1016);
    env.raf(1016 + 3000); // đứng 3 giây
    const gap = 3000;
    env.raf(1016 + 3000 + total); // kết thúc
    const result = await promise;
    expect(result.maxRafGapMs).toBeGreaterThanOrEqual(gap);
    expect(result.maxRafGapMs).toBeGreaterThan(MAX_RAF_GAP_MS);
  });

  it("lỗi lấy mẫu (landmarker đã đóng) không làm vòng thử ném lỗi và được đếm", async () => {
    const env = makeEnv();
    let calls = 0;
    const flaky: FrameSampler = {
      sample: () => {
        calls += 1;
        throw new Error("landmarker đã đóng");
      },
    };
    const promise = runTrial({ video: env.video, sampler: flaky, steps, onColor: () => {} });
    env.raf(1000); // bắt đầu
    env.frame(1010);
    env.frame(1043);
    for (let t = 1016; t <= 1000 + total + 50; t += 100) env.raf(t);

    const result = await promise;
    expect(calls).toBeGreaterThan(0);
    expect(result.sampleErrors).toBe(calls);
    expect(result.frames).toHaveLength(0);
  });

  it("captureTime có thì ghi lại, không có thì null; khóa metadata được liệt kê", async () => {
    const env = makeEnv();
    const promise = runTrial({ video: env.video, sampler: env.sampler, steps, onColor: () => {} });
    env.raf(1000);
    env.frame(1010);
    env.frame(1043, { captureTime: 1040 } as Partial<VideoFrameCallbackMetadata>);
    env.raf(1000 + total + 50);
    const result = await promise;

    expect(result.frames.map((f) => f.capture_time)).toEqual([null, 1040]);
    expect(result.metadataKeys).toContain("captureTime");
    expect(result.metadataKeys).toContain("mediaTime");
  });
});

describe("runTrial: mốc rAF kế tiếp và khung chưa sẵn sàng", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  const steps = generateSequence(() => 0.5);
  const total = buildTimeline(steps).totalMs;

  it("mỗi sự kiện màu có painted_next_raf là mốc rAF kế tiếp, lớn hơn painted_at", async () => {
    const env = makeEnv();
    const promise = runTrial({ video: env.video, sampler: env.sampler, steps, onColor: () => {} });
    for (let t = 1000; t <= 1000 + total + 100; t += 16) env.raf(t);
    const result = await promise;

    for (const event of result.colorEvents) {
      expect(event.painted_next_raf).not.toBeNull();
      expect(event.painted_next_raf as number).toBeGreaterThan(event.painted_at);
      expect((event.painted_next_raf as number) - event.painted_at).toBeLessThanOrEqual(16);
    }
  });

  it("video chưa có khung (sampler trả null) thì bỏ qua, không ghi và không đếm lỗi", async () => {
    const env = makeEnv();
    const notReady: FrameSampler = { sample: () => null };
    const promise = runTrial({ video: env.video, sampler: notReady, steps, onColor: () => {} });
    env.raf(1000);
    env.frame(1010);
    env.frame(1043);
    env.raf(1000 + total + 50);
    const result = await promise;

    expect(result.frames).toHaveLength(0);
    expect(result.sampleErrors).toBe(0);
  });
});

describe("recordProblems cho chất lượng lần thử", () => {
  function baseRecord(): LabRecord {
    const frames = Array.from({ length: 20 }, (_, i) => ({
      index: i,
      now: i * 33,
      media_time: i / 30,
      presented_frames: i,
      capture_time: i * 33,
      expected_display_time: null,
      receive_time: null,
      processing_duration: null,
      width: 640,
      height: 480,
      face_found: true,
      regions: {},
    }));
    return {
      schema_version: 1,
      kind: "chromapulse_lab",
      created_at: "2026-10-15T00:00:00.000Z",
      scenario: "real",
      take: 1,
      note: "",
      privacy: "x",
      device: {} as LabRecord["device"],
      support: {
        request_video_frame_callback: true,
        has_capture_time: true,
        frame_metadata_keys: [],
        landmarker_delegate: "CPU",
        clock: "performance.now",
      },
      camera: { settings: {}, applied_constraints_error: null },
      config: {} as LabRecord["config"],
      sequence: [],
      timeline: { total_ms: 0, tail_start_ms: 0, start_performance_now: 0 },
      color_events: Array.from({ length: chromaPulseConfig.steps }, (_, i) => ({
        index: i,
        rgb: "#ffcc73",
        painted_at: 1000 + i * 600,
        painted_next_raf: 1000 + i * 600 + 16,
      })),
      display_samples: [],
      frame_times: frames,
      region_defs: {} as LabRecord["region_defs"],
      quality: { max_raf_gap_ms: 17, hidden_during_trial: false, aborted: false, sample_errors: 0 },
    };
  }

  it("bản ghi sạch không có vấn đề", () => {
    expect(recordProblems(baseRecord())).toEqual([]);
  });

  it("tám sự kiện màu cùng một painted_at (rAF đứng rồi chạy lại) bị báo", () => {
    const record = baseRecord();
    record.color_events = record.color_events.map((e) => ({ ...e, painted_at: 5000 }));
    expect(recordProblems(record).join(" ")).toContain("cùng thời điểm vẽ");
  });

  it("tab ẩn, giật rAF và lỗi lấy mẫu đều được báo", () => {
    const record = baseRecord();
    record.quality = {
      max_raf_gap_ms: 900,
      hidden_during_trial: true,
      aborted: true,
      sample_errors: 3,
    };
    const text = recordProblems(record).join(" | ");
    expect(text).toContain("Tab bị ẩn");
    expect(text).toContain("giật");
    expect(text).toContain("3 khung lấy mẫu bị lỗi");
  });

  it("bản ghi cũ không có trường quality vẫn kiểm được", () => {
    const record = baseRecord();
    delete record.quality;
    expect(recordProblems(record)).toEqual([]);
  });
});

describe("recordProblems: khung hình và Dừng", () => {
  const frame = (i: number): LabRecord["frame_times"][number] => ({
    index: i,
    now: i * 33,
    media_time: i / 30,
    presented_frames: i,
    capture_time: i * 33,
    expected_display_time: null,
    receive_time: null,
    processing_duration: null,
    width: 640,
    height: 480,
    face_found: true,
    regions: {},
  });
  const record = (frames: number, aborted: boolean): LabRecord => ({
    schema_version: 1,
    kind: "chromapulse_lab",
    created_at: "2026-10-15T00:00:00.000Z",
    scenario: "real",
    take: 1,
    note: "",
    privacy: "x",
    device: {} as LabRecord["device"],
    support: {
      request_video_frame_callback: true,
      has_capture_time: true,
      frame_metadata_keys: [],
      landmarker_delegate: "CPU",
      clock: "performance.now",
    },
    camera: { settings: {}, applied_constraints_error: null },
    config: {} as LabRecord["config"],
    sequence: [],
    timeline: { total_ms: 0, tail_start_ms: 0, start_performance_now: 0 },
    color_events: Array.from({ length: chromaPulseConfig.steps }, (_, i) => ({
      index: i,
      rgb: "#000000",
      painted_at: 1000 + i * 600,
      painted_next_raf: 1000 + i * 600 + 16,
    })),
    display_samples: [],
    frame_times: Array.from({ length: frames }, (_, i) => frame(i)),
    region_defs: {} as LabRecord["region_defs"],
    quality: { max_raf_gap_ms: 17, hidden_during_trial: false, aborted, sample_errors: 0 },
  });

  it("không có khung nào: báo camera không cấp khung", () => {
    expect(recordProblems(record(0, false)).join(" ")).toContain("camera không cấp khung");
  });

  it("quá ít khung (dưới ngưỡng) bị báo, đủ ngưỡng thì không", () => {
    expect(recordProblems(record(MIN_FRAMES - 1, false)).join(" ")).toContain("Quá ít khung hình");
    expect(recordProblems(record(MIN_FRAMES, false))).toEqual([]);
  });

  it("bấm Dừng giữa chừng bị báo", () => {
    expect(recordProblems(record(MIN_FRAMES, true)).join(" ")).toContain("bị dừng giữa chừng");
  });
});
