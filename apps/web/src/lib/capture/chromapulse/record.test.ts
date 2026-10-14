import { describe, expect, it } from "vitest";

import { chromaPulseConfig } from "./config";
import {
  PRIVACY_NOTE,
  RECORD_SCHEMA_VERSION,
  type FrameRecord,
  type LabRecord,
  buildFileName,
  configToRecord,
  frameMetadataKeys,
  recordProblems,
  sequenceToRecord,
  serializeRecord,
  slugify,
  summarizeSupport,
  timelineToRecord,
} from "./record";
import { REGION_DEFS } from "./regions";
import type { SequenceStep, Timeline } from "./sequence";

function frame(index: number, over: Partial<FrameRecord> = {}): FrameRecord {
  return {
    index,
    now: 1000 + index * 33,
    media_time: index / 30,
    presented_frames: index,
    capture_time: 990 + index * 33,
    expected_display_time: null,
    receive_time: null,
    processing_duration: null,
    width: 640,
    height: 480,
    face_found: true,
    regions: null,
    ...over,
  };
}

function makeRecord(over: Partial<LabRecord> = {}): LabRecord {
  const steps: SequenceStep[] = Array.from({ length: chromaPulseConfig.steps }, (_, i) => ({
    index: i,
    rgb: "#112233",
    holdMs: 300,
    transitionMs: 100,
  }));
  return {
    schema_version: RECORD_SCHEMA_VERSION,
    kind: "chromapulse_lab",
    created_at: "2026-10-15T00:00:00.000Z",
    scenario: "real",
    take: 1,
    note: "",
    privacy: PRIVACY_NOTE,
    device: {
      label: "iPhone 13",
      user_agent: "ua",
      platform: "iOS",
      language: "vi",
      screen: { width: 390, height: 844, device_pixel_ratio: 3 },
      hardware_concurrency: 6,
      camera_label: null,
    },
    support: {
      request_video_frame_callback: true,
      has_capture_time: true,
      frame_metadata_keys: ["captureTime", "mediaTime"],
      landmarker_delegate: "GPU",
      clock: "performance.now",
    },
    camera: { settings: {}, applied_constraints_error: null },
    config: configToRecord(),
    sequence: sequenceToRecord(steps),
    timeline: { total_ms: 5000, tail_start_ms: 4000, start_performance_now: 1000 },
    color_events: steps.map((s) => ({
      index: s.index,
      rgb: s.rgb,
      painted_at: 1000 + s.index * 400,
      painted_next_raf: 1000 + s.index * 400 + 16,
    })),
    display_samples: [[1000, 1, 2, 3]],
    frame_times: Array.from({ length: 10 }, (_, i) => frame(i)),
    region_defs: REGION_DEFS,
    ...over,
  };
}

describe("slugify", () => {
  it("bỏ dấu tiếng Việt", () => {
    expect(slugify("Điện thoại Xiaomi Redmi 12")).toBe("dien-thoai-xiaomi-redmi-12");
  });

  it("chuỗi rỗng hoặc toàn ký tự lạ thành 'x'", () => {
    expect(slugify("")).toBe("x");
    expect(slugify("???///")).toBe("x");
    expect(slugify("   ")).toBe("x");
  });

  it("không có gạch ngang đầu/cuối và gộp ký tự lạ liên tiếp", () => {
    expect(slugify("  --Hello,,  World!! ")).toBe("hello-world");
  });
});

describe("buildFileName", () => {
  it("ghép máy, trình duyệt, tình huống, lần thử", () => {
    expect(
      buildFileName({ device: "iPhone 13", browser: "Safari", scenario: "real", take: 2 }),
    ).toBe("iphone-13_safari_real_02.json");
  });

  it("take < 1 thành 01, số thực được làm tròn xuống", () => {
    const base = { device: "a", browser: "b", scenario: "obs" } as const;
    expect(buildFileName({ ...base, take: 0 })).toBe("a_b_obs_01.json");
    expect(buildFileName({ ...base, take: -5 })).toBe("a_b_obs_01.json");
    expect(buildFileName({ ...base, take: 3.9 })).toBe("a_b_obs_03.json");
    expect(buildFileName({ ...base, take: 12 })).toBe("a_b_obs_12.json");
  });

  it("tên chứa '/' hay '..' không thoát thư mục", () => {
    const name = buildFileName({
      device: "../../etc/passwd",
      browser: "..\\x/y",
      scenario: "replay",
      take: 1,
    });
    expect(name).toMatch(/^[a-z0-9_-]+_[a-z0-9_-]+_replay_01\.json$/);
    expect(name).not.toContain("/");
    expect(name).not.toContain("\\");
    expect(name).not.toContain("..");
  });
});

describe("frameMetadataKeys / summarizeSupport", () => {
  it("frameMetadataKeys trả khóa đã sắp xếp", () => {
    expect(frameMetadataKeys({ presentedFrames: 1, captureTime: 2, mediaTime: 3 })).toEqual([
      "captureTime",
      "mediaTime",
      "presentedFrames",
    ]);
    expect(frameMetadataKeys({})).toEqual([]);
  });

  it("has_capture_time true khi có ít nhất một khung có capture_time", () => {
    const frames = [frame(0, { capture_time: null }), frame(1, { capture_time: 5 })];
    expect(summarizeSupport(frames)).toEqual({ has_capture_time: true });
  });

  it("has_capture_time false khi mọi khung null hoặc không có khung", () => {
    expect(summarizeSupport([frame(0, { capture_time: null })]).has_capture_time).toBe(false);
    expect(summarizeSupport([]).has_capture_time).toBe(false);
  });
});

describe("chuyển đổi sang bản ghi", () => {
  it("sequenceToRecord đổi tên trường sang snake_case và giữ thứ tự", () => {
    const steps: SequenceStep[] = [
      { index: 0, rgb: "#ff0000", holdMs: 250, transitionMs: 80 },
      { index: 1, rgb: "#00ff00", holdMs: 400, transitionMs: 90 },
    ];
    expect(sequenceToRecord(steps)).toEqual([
      { index: 0, rgb: "#ff0000", hold_ms: 250, transition_ms: 80 },
      { index: 1, rgb: "#00ff00", hold_ms: 400, transition_ms: 90 },
    ]);
    expect(sequenceToRecord([])).toEqual([]);
  });

  it("configToRecord khớp chromaPulseConfig", () => {
    const c = chromaPulseConfig;
    expect(configToRecord()).toEqual({
      palette: c.palette,
      baseline_color: c.baselineColor,
      baseline_ms: c.baselineMs,
      tail_ms: c.tailMs,
      transition_ms: c.transitionMs,
      hold_ms: { min: c.holdMinMs, max: c.holdMaxMs },
    });
  });

  it("timelineToRecord khớp đầu vào", () => {
    const t: Timeline = {
      segments: [],
      tailStartMs: 4200,
      totalMs: 5200,
      baselineMs: 500,
      tailMs: 1000,
      baselineColor: "#808080",
    };
    expect(timelineToRecord(t, 12345.5)).toEqual({
      total_ms: 5200,
      tail_start_ms: 4200,
      start_performance_now: 12345.5,
    });
  });
});

describe("recordProblems", () => {
  it("bản ghi hợp lệ không có vấn đề", () => {
    expect(recordProblems(makeRecord())).toEqual([]);
  });

  it("thiếu màu", () => {
    const rec = makeRecord();
    const p = recordProblems({ ...rec, color_events: rec.color_events.slice(0, 5) });
    expect(p).toHaveLength(1);
    expect(p[0]).toContain(`5/${chromaPulseConfig.steps}`);
  });

  it("không có khung hình", () => {
    expect(recordProblems(makeRecord({ frame_times: [] }))).toEqual([
      "Không có khung hình nào (camera không cấp khung)",
    ]);
  });

  it("thấy mặt dưới 80% khung", () => {
    const frames = Array.from({ length: 10 }, (_, i) => frame(i, { face_found: i < 7 }));
    const p = recordProblems(makeRecord({ frame_times: frames }));
    expect(p).toHaveLength(1);
    expect(p[0]).toContain("7/10");
  });

  it("đúng 80% thì vẫn đạt", () => {
    const frames = Array.from({ length: 10 }, (_, i) => frame(i, { face_found: i < 8 }));
    expect(recordProblems(makeRecord({ frame_times: frames }))).toEqual([]);
  });

  it("không có captureTime", () => {
    const rec = makeRecord();
    const p = recordProblems({ ...rec, support: { ...rec.support, has_capture_time: false } });
    expect(p).toEqual(["Trình duyệt này không có captureTime"]);
  });

  it("nhiều vấn đề cùng lúc được báo đủ", () => {
    const rec = makeRecord({ color_events: [], frame_times: [] });
    const p = recordProblems({ ...rec, support: { ...rec.support, has_capture_time: false } });
    expect(p).toHaveLength(3);
  });
});

describe("serializeRecord và riêng tư", () => {
  it("JSON.parse ra đúng bản ghi", () => {
    const rec = makeRecord();
    expect(JSON.parse(serializeRecord(rec))).toEqual(rec);
  });

  it("không chứa ảnh hay khung hình", () => {
    const text = serializeRecord(makeRecord());
    expect(text).not.toContain("data:image");
    const keys = new Set<string>();
    const walk = (v: unknown): void => {
      if (Array.isArray(v)) v.forEach(walk);
      else if (v && typeof v === "object") {
        for (const [k, val] of Object.entries(v)) {
          keys.add(k);
          walk(val);
        }
      }
    };
    walk(JSON.parse(text));
    expect(keys.has("image")).toBe(false);
    expect(keys.has("frame_data")).toBe(false);
  });

  it("bản ghi mang PRIVACY_NOTE", () => {
    const rec = makeRecord();
    expect(rec.privacy).toBe(PRIVACY_NOTE);
    expect(serializeRecord(rec)).toContain(PRIVACY_NOTE);
  });
});
