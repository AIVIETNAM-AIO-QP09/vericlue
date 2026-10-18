import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  FRAME_SIZE_SETTLE_MS,
  PROBE_RESOLUTIONS,
  collectCamProbe,
  detectApiTampering,
  duplicateRatio,
  probeConstraints,
  sameSize,
} from "./camprobe";

// --- "cửa sổ" giả ---------------------------------------------------------------------------

type WinLike = Window & typeof globalThis;
type Fn = (...args: unknown[]) => unknown;

/** Hàm được coi là native: toString giả trả "function <tên>() { [native code] }". */
const natives = new WeakSet<object>();

function nativeFn(name: string): Fn {
  // Phương thức trong object literal: không có `prototype`, own props chỉ "length,name".
  const fn = { [name]: () => undefined }[name] as Fn;
  natives.add(fn);
  return fn;
}

function fakeToString(this: unknown): string {
  if (typeof this === "function") {
    return natives.has(this)
      ? `function ${this.name}() { [native code] }`
      : `function ${this.name}() { return 1; }`;
  }
  return "";
}

type FakeWin = {
  Function: { prototype: { toString: Fn } };
  MediaDevices: { prototype: Record<string, unknown> };
  MediaStreamTrack: { prototype: Record<string, unknown> };
  navigator: { mediaDevices: Record<string, unknown> };
};

function makeWindow(): FakeWin {
  const mediaDevicesProto = {
    getUserMedia: nativeFn("getUserMedia"),
    enumerateDevices: nativeFn("enumerateDevices"),
  };
  return {
    Function: { prototype: { toString: makeToString() } },
    MediaDevices: { prototype: mediaDevicesProto },
    MediaStreamTrack: {
      prototype: {
        getSettings: nativeFn("getSettings"),
        getCapabilities: nativeFn("getCapabilities"),
        applyConstraints: nativeFn("applyConstraints"),
      },
    },
    navigator: { mediaDevices: Object.create(mediaDevicesProto) as Record<string, unknown> },
  };
}

/** toString giả: tự đăng ký native, thực thi bằng fakeToString. */
function makeToString(): Fn {
  const fn = { toString: fakeToString }.toString as Fn;
  natives.add(fn);
  return fn;
}

function asWin(win: FakeWin): WinLike {
  return win as unknown as WinLike;
}

describe("detectApiTampering", () => {
  it("cửa sổ sạch, không có cleanWindow → []", () => {
    expect(detectApiTampering(asWin(makeWindow()), null)).toEqual([]);
  });

  it("cửa sổ sạch so với iframe sạch → []", () => {
    expect(detectApiTampering(asWin(makeWindow()), asWin(makeWindow()))).toEqual([]);
  });

  it("hàm bị thay bằng hàm JS thường → non_native_tostring", () => {
    const win = makeWindow();
    win.MediaDevices.prototype.getUserMedia = () => undefined; // không đăng ký native
    const flags = detectApiTampering(asWin(win), null);
    expect(flags).toContain("getUserMedia:non_native_tostring");
    expect(flags.every((f) => f.startsWith("getUserMedia:"))).toBe(true);
  });

  it("hàm có thuộc tính prototype → has_prototype (và own_properties bất thường)", () => {
    const win = makeWindow();
    const patched = function getSettings() {
      return {};
    } as Fn;
    natives.add(patched); // toString giả vẫn "native" để cô lập cờ
    win.MediaStreamTrack.prototype.getSettings = patched;
    const flags = detectApiTampering(asWin(win), null);
    expect(flags).toContain("getSettings:has_prototype");
    expect(flags).toContain("getSettings:unexpected_own_properties");
    expect(flags).not.toContain("getSettings:non_native_tostring");
  });

  it("thêm thuộc tính riêng lên hàm → unexpected_own_properties", () => {
    const win = makeWindow();
    (win.MediaStreamTrack.prototype.applyConstraints as Fn & { hook?: boolean }).hook = true;
    expect(detectApiTampering(asWin(win), null)).toEqual([
      "applyConstraints:unexpected_own_properties",
    ]);
  });

  it("gán đè trên navigator.mediaDevices → own_property_override", () => {
    const win = makeWindow();
    win.navigator.mediaDevices.getUserMedia = nativeFn("getUserMedia");
    expect(detectApiTampering(asWin(win), null)).toEqual(["getUserMedia:own_property_override"]);
  });

  it("gán đè enumerateDevices → own_property_override", () => {
    const win = makeWindow();
    win.navigator.mediaDevices.enumerateDevices = nativeFn("enumerateDevices");
    expect(detectApiTampering(asWin(win), null)).toContain(
      "enumerateDevices:own_property_override",
    );
  });

  it("không có navigator.mediaDevices thì bỏ qua kiểm tra gán đè", () => {
    const win = makeWindow();
    (win.navigator as { mediaDevices?: unknown }).mediaDevices = undefined;
    expect(detectApiTampering(asWin(win), null)).toEqual([]);
  });

  it("khác bản trong iframe (tên khác) → iframe_mismatch", () => {
    const win = makeWindow();
    const clean = makeWindow();
    win.MediaStreamTrack.prototype.getSettings = nativeFn("fakeGetSettings");
    expect(detectApiTampering(asWin(win), asWin(clean))).toEqual(["getSettings:iframe_mismatch"]);
  });

  it("khác bản trong iframe (length khác) → iframe_mismatch", () => {
    const win = makeWindow();
    const clean = makeWindow();
    const twoArgs = { applyConstraints: (a: unknown, b: unknown) => [a, b] }.applyConstraints as Fn;
    natives.add(twoArgs);
    win.MediaStreamTrack.prototype.applyConstraints = twoArgs;
    expect(detectApiTampering(asWin(win), asWin(clean))).toEqual([
      "applyConstraints:iframe_mismatch",
    ]);
  });

  it("cleanWindow=null bỏ qua so sánh iframe", () => {
    const win = makeWindow();
    win.MediaStreamTrack.prototype.getSettings = nativeFn("fakeGetSettings");
    expect(detectApiTampering(asWin(win), null)).toEqual([]);
  });

  it("toString của trang bị thay → Function.toString:iframe_mismatch", () => {
    const win = makeWindow();
    const clean = makeWindow();
    win.Function.prototype.toString = function toString(this: unknown) {
      return fakeToString.call(this);
    } as Fn; // hàm JS thường, không đăng ký native
    expect(detectApiTampering(asWin(win), asWin(clean))).toContain(
      "Function.toString:iframe_mismatch",
    );
  });

  it("trang thiếu hàm mà iframe sạch có → not_function", () => {
    const win = makeWindow();
    delete win.MediaDevices.prototype.enumerateDevices;
    win.MediaStreamTrack.prototype.getCapabilities = "không phải hàm";
    const flags = detectApiTampering(asWin(win), asWin(makeWindow()));
    expect(flags).toContain("enumerateDevices:not_function");
    expect(flags).toContain("getCapabilities:not_function");
    expect(flags).toHaveLength(2);
  });

  it("trang thiếu cả MediaDevices/MediaStreamTrack mà iframe có → 5 cờ not_function", () => {
    const win = makeWindow();
    (win as { MediaDevices?: unknown }).MediaDevices = undefined;
    (win as { MediaStreamTrack?: unknown }).MediaStreamTrack = undefined;
    const flags = detectApiTampering(asWin(win), asWin(makeWindow()));
    expect(flags.sort()).toEqual(
      [
        "applyConstraints:not_function",
        "enumerateDevices:not_function",
        "getCapabilities:not_function",
        "getSettings:not_function",
        "getUserMedia:not_function",
      ].sort(),
    );
  });

  it("cả trang và iframe cùng thiếu hàm → không cờ (trình duyệt cũ)", () => {
    const win = makeWindow();
    const clean = makeWindow();
    delete win.MediaStreamTrack.prototype.getCapabilities;
    delete clean.MediaStreamTrack.prototype.getCapabilities;
    expect(detectApiTampering(asWin(win), asWin(clean))).toEqual([]);
  });

  it("cleanWindow=null và trang thiếu hàm → không cờ", () => {
    const win = makeWindow();
    delete win.MediaDevices.prototype.enumerateDevices;
    (win as { MediaStreamTrack?: unknown }).MediaStreamTrack = undefined;
    expect(detectApiTampering(asWin(win), null)).toEqual([]);
  });

  it("iframe thiếu hàm mà trang có → không cờ not_function", () => {
    const clean = makeWindow();
    delete clean.MediaStreamTrack.prototype.getCapabilities;
    const flags = detectApiTampering(asWin(makeWindow()), asWin(clean));
    expect(flags.some((f) => f.endsWith(":not_function"))).toBe(false);
  });

  it("toString ném lỗi → coi là non_native_tostring", () => {
    const win = makeWindow();
    win.Function.prototype.toString = {
      toString() {
        throw new TypeError("bị chặn");
      },
    }.toString as Fn;
    const flags = detectApiTampering(asWin(win), null);
    expect(flags).toContain("getUserMedia:non_native_tostring");
    expect(flags).toContain("applyConstraints:non_native_tostring");
  });

  it("không trùng cờ", () => {
    const win = makeWindow();
    win.MediaDevices.prototype.getUserMedia = () => undefined;
    const flags = detectApiTampering(asWin(win), asWin(makeWindow()));
    expect(new Set(flags).size).toBe(flags.length);
  });
});

describe("duplicateRatio", () => {
  it("toàn khung khác nhau → 0", () => {
    expect(duplicateRatio(["a", "b", "c", "d"])).toBe(0);
  });

  it("toàn khung giống nhau → 1", () => {
    expect(duplicateRatio(["a", "a", "a", "a"])).toBe(1);
  });

  it("một phần: so cặp liên tiếp", () => {
    // cặp: a-a (giống), a-b, b-b (giống), b-c → 2/4
    expect(duplicateRatio(["a", "a", "b", "b", "c"])).toBe(0.5);
  });

  it("chỉ so cặp liên tiếp, không so toàn cục", () => {
    expect(duplicateRatio(["a", "b", "a", "b"])).toBe(0);
  });

  it("hai mẫu giống nhau → 1", () => {
    expect(duplicateRatio(["x", "x"])).toBe(1);
  });

  it("ít hơn 2 mẫu → null", () => {
    expect(duplicateRatio([])).toBeNull();
    expect(duplicateRatio(["a"])).toBeNull();
  });
});

// --- probeConstraints ------------------------------------------------------------------------

type Dim = { width: number; height: number };
type FakeVideo = { videoWidth: number; videoHeight: number };

function makeTrack(
  initial: Dim,
  video: FakeVideo,
  behavior: {
    reflectSettings?: boolean;
    reflectFrame?: boolean;
    reject?: boolean;
    rotateFrame?: boolean;
  } = {},
) {
  const {
    reflectSettings = true,
    reflectFrame = true,
    reject = false,
    rotateFrame = false,
  } = behavior;
  let settings: Dim = { ...initial };
  const applyConstraints = vi.fn(async (constraints: MediaTrackConstraints) => {
    if (reject) throw new Error("OverconstrainedError");
    const width = (constraints.width as { exact: number }).exact;
    const height = (constraints.height as { exact: number }).exact;
    if (reflectSettings) settings = { width, height };
    if (reflectFrame) {
      video.videoWidth = rotateFrame ? height : width;
      video.videoHeight = rotateFrame ? width : height;
    }
  });
  const track = {
    getSettings: () => ({ ...settings }),
    applyConstraints,
  } as unknown as MediaStreamTrack;
  return { track, applyConstraints };
}

function asVideo(video: FakeVideo): HTMLVideoElement {
  return video as unknown as HTMLVideoElement;
}

describe("probeConstraints", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  async function run(track: MediaStreamTrack, video: FakeVideo) {
    const pending = probeConstraints(track, asVideo(video));
    await vi.advanceTimersByTimeAsync(PROBE_RESOLUTIONS.length * (FRAME_SIZE_SETTLE_MS + 100));
    return pending;
  }

  it("thiết bị thật: settings và khung hình đổi theo yêu cầu", async () => {
    const video = { videoWidth: 1280, videoHeight: 720 };
    const { track, applyConstraints } = makeTrack({ width: 1280, height: 720 }, video);
    const probes = await run(track, video);

    expect(probes).toHaveLength(2);
    expect(applyConstraints).toHaveBeenNthCalledWith(1, {
      width: { exact: 640 },
      height: { exact: 480 },
    });
    const [first, second] = probes;
    expect(first).toMatchObject({
      kind: "resolution",
      requested: { width: 640, height: 480 },
      ok: true,
      settings_before: { width: 1280, height: 720 },
      settings_after: { width: 640, height: 480 },
      settings_changed: true,
      frame_size_after: { width: 640, height: 480 },
      frame_size_changed: true,
    });
    expect(first.apply_ms).toBeGreaterThanOrEqual(0);
    expect(second).toMatchObject({
      requested: { width: 320, height: 240 },
      settings_before: { width: 640, height: 480 },
      settings_changed: true,
      frame_size_changed: true,
    });
  });

  it("applyConstraints bị từ chối → ok=false, không đo khung, không đổi", async () => {
    const video = { videoWidth: 1280, videoHeight: 720 };
    const { track } = makeTrack({ width: 1280, height: 720 }, video, { reject: true });
    const probes = await run(track, video);

    expect(probes).toHaveLength(2);
    for (const probe of probes) {
      expect(probe.ok).toBe(false);
      expect(probe.settings_changed).toBe(false);
      expect(probe.frame_size_after).toBeNull();
      expect(probe.frame_size_changed).toBeNull();
    }
  });

  it("bỏ qua độ phân giải trùng với độ phân giải hiện tại", async () => {
    const video = { videoWidth: 640, videoHeight: 480 };
    const { track, applyConstraints } = makeTrack({ width: 640, height: 480 }, video);
    const probes = await run(track, video);

    expect(probes).toHaveLength(1);
    expect(probes[0].requested).toEqual({ width: 320, height: 240 });
    expect(applyConstraints).toHaveBeenCalledTimes(1);
  });

  it("đang ở 320x240: mốc 640x480 thăm dò trước, rồi 320x240 (vì đã đổi sang 640x480)", async () => {
    const video = { videoWidth: 320, videoHeight: 240 };
    const { track } = makeTrack({ width: 320, height: 240 }, video);
    const probes = await run(track, video);
    expect(probes.map((p) => p.requested.width)).toEqual([640, 320]);
  });

  it("camera giả trả ngay nhưng settings không đổi → settings_changed=false", async () => {
    const video = { videoWidth: 1280, videoHeight: 720 };
    const { track } = makeTrack({ width: 1280, height: 720 }, video, {
      reflectSettings: false,
      reflectFrame: false,
    });
    const probes = await run(track, video);

    for (const probe of probes) {
      expect(probe.ok).toBe(true);
      expect(probe.settings_changed).toBe(false);
      expect(probe.settings_after).toEqual({ width: 1280, height: 720 });
      // Khung vẫn là 1280x720 sau thời gian chờ tối đa.
      expect(probe.frame_size_after).toEqual({ width: 1280, height: 720 });
      expect(probe.frame_size_changed).toBe(false);
    }
  });

  it("settings đổi nhưng khung hình không đổi → settings_changed=true, frame_size_changed=false", async () => {
    const video = { videoWidth: 1280, videoHeight: 720 };
    const { track } = makeTrack({ width: 1280, height: 720 }, video, { reflectFrame: false });
    const probes = await run(track, video);

    expect(probes[0].settings_changed).toBe(true);
    expect(probes[0].frame_size_changed).toBe(false);
  });

  it("chưa có khung hình (videoWidth=0) → frame_size_after=null", async () => {
    const video = { videoWidth: 0, videoHeight: 0 };
    const { track } = makeTrack({ width: 1280, height: 720 }, video, { reflectFrame: false });
    const probes = await run(track, video);

    expect(probes[0].ok).toBe(true);
    expect(probes[0].frame_size_after).toBeNull();
    expect(probes[0].frame_size_changed).toBeNull();
  });

  it("bỏ qua mốc khi độ phân giải hiện tại là bản xoay (480x640 ~ 640x480)", async () => {
    const video = { videoWidth: 480, videoHeight: 640 };
    const { track, applyConstraints } = makeTrack({ width: 480, height: 640 }, video);
    const probes = await run(track, video);
    expect(probes.map((p) => p.requested.width)).toEqual([320]);
    expect(applyConstraints).toHaveBeenCalledTimes(1);
  });

  it("khung báo 480x640 cho yêu cầu 640x480 → frame_size_changed=true (không phân biệt xoay)", async () => {
    const video = { videoWidth: 1280, videoHeight: 720 };
    const { track } = makeTrack({ width: 1280, height: 720 }, video, { rotateFrame: true });
    const probes = await run(track, video);
    expect(probes[0].frame_size_after).toEqual({ width: 480, height: 640 });
    expect(probes[0].frame_size_changed).toBe(true);
  });

  it("khung giữ nguyên 1280x720 → frame_size_changed=false (không phải null)", async () => {
    const video = { videoWidth: 1280, videoHeight: 720 };
    const { track } = makeTrack({ width: 1280, height: 720 }, video, { reflectFrame: false });
    const probes = await run(track, video);
    expect(probes[0].frame_size_changed).toBe(false);
  });

  it("khung đổi kích thước muộn (sau 200 ms) vẫn được đo là đã đổi", async () => {
    const video = { videoWidth: 1280, videoHeight: 720 };
    const { track } = makeTrack({ width: 1280, height: 720 }, video, { reflectFrame: false });
    setTimeout(() => {
      video.videoWidth = 640;
      video.videoHeight = 480;
    }, 200);
    const pending = probeConstraints(track, asVideo(video));
    await vi.advanceTimersByTimeAsync(300);
    const probes = await (async () => {
      // Probe thứ hai (320x240) không đổi khung → chờ hết hạn.
      await vi.advanceTimersByTimeAsync(FRAME_SIZE_SETTLE_MS + 200);
      return pending;
    })();
    expect(probes[0].frame_size_after).toEqual({ width: 640, height: 480 });
    expect(probes[0].frame_size_changed).toBe(true);
  });
});

describe("sameSize", () => {
  it("bằng nhau khi cùng kích thước", () => {
    expect(sameSize({ width: 640, height: 480 }, { width: 640, height: 480 })).toBe(true);
  });

  it("xoay dọc/ngang vẫn bằng nhau", () => {
    expect(sameSize({ width: 480, height: 640 }, { width: 640, height: 480 })).toBe(true);
    expect(sameSize({ width: 640, height: 480 }, { width: 480, height: 640 })).toBe(true);
  });

  it("khác kích thước → false", () => {
    expect(sameSize({ width: 1280, height: 720 }, { width: 640, height: 480 })).toBe(false);
    expect(sameSize({ width: 640, height: 481 }, { width: 640, height: 480 })).toBe(false);
  });

  it("có giá trị null → false", () => {
    expect(sameSize({ width: null, height: null }, { width: 640, height: 480 })).toBe(false);
    expect(sameSize({ width: 640, height: 480 }, { width: null, height: 480 })).toBe(false);
    expect(sameSize({ width: null, height: null }, { width: null, height: null })).toBe(false);
  });
});

// --- collectCamProbe -----------------------------------------------------------------------

type FakeVideoEl = {
  videoWidth: number;
  videoHeight: number;
  srcObject: unknown;
  play: ReturnType<typeof vi.fn>;
  remove: ReturnType<typeof vi.fn>;
  requestVideoFrameCallback?: ReturnType<typeof vi.fn>;
};
type StoppableTrack = MediaStreamTrack & { stop: ReturnType<typeof vi.fn> };

describe("collectCamProbe", () => {
  let video: FakeVideoEl;
  let probeTrack: StoppableTrack;
  let clone: ReturnType<typeof vi.fn>;

  function makeStream(tracks: unknown[]): MediaStream {
    return { getVideoTracks: () => tracks } as unknown as MediaStream;
  }

  function makeOriginal() {
    return {
      label: "Camera thật",
      clone,
      getSettings: () => ({ deviceId: "d", groupId: "g", width: 1280, height: 720 }),
      getCapabilities: () => ({ deviceId: "d", groupId: "g", width: { min: 1, max: 1920 } }),
    };
  }

  function stubDom(options: { rVFC?: boolean } = {}) {
    video = {
      videoWidth: 1280,
      videoHeight: 720,
      srcObject: null,
      play: vi.fn(async () => undefined),
      remove: vi.fn(),
    };
    if (options.rVFC) {
      video.requestVideoFrameCallback = vi.fn((cb: () => void) => {
        queueMicrotask(cb);
        return 1;
      });
    }
    const element = (extra: object) => ({ style: {}, setAttribute: vi.fn(), ...extra });
    const canvas = element({
      getContext: () => ({
        drawImage: vi.fn(),
        getImageData: () => ({ data: new Uint8ClampedArray(24 * 24 * 4) }),
      }),
    });
    const iframe = element({ remove: vi.fn(), contentWindow: null });
    vi.stubGlobal("document", {
      createElement: (tag: string) =>
        tag === "video" ? Object.assign(video, element({})) : tag === "canvas" ? canvas : iframe,
      body: { appendChild: vi.fn() },
    });
  }

  /** Track giả mà applyConstraints cập nhật kích thước khung của `video` giả hiện tại. */
  function useRealisticProbeTrack() {
    const { track } = makeTrack({ width: 1280, height: 720 }, video);
    probeTrack = Object.assign(track, { stop: vi.fn() }) as StoppableTrack;
  }

  function hangPlay() {
    video.play.mockImplementation(() => new Promise(() => undefined));
  }

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
    stubDom();
    clone = vi.fn(() => probeTrack);
    useRealisticProbeTrack();
    vi.stubGlobal("window", makeWindow());
    vi.stubGlobal(
      "MediaStream",
      class {
        constructor(public tracks: unknown[]) {}
      },
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("stream không có video track → reject", async () => {
    await expect(collectCamProbe(makeStream([]))).rejects.toThrow("camprobe_no_video_track");
    expect(clone).not.toHaveBeenCalled();
  });

  it("signal đã abort từ trước → reject, không nhân bản track", async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(
      collectCamProbe(makeStream([makeOriginal()]), { signal: controller.signal }),
    ).rejects.toThrow("camprobe_aborted");
    expect(clone).not.toHaveBeenCalled();
  });

  it("quá hạn → reject camprobe_timeout và tắt bản clone", async () => {
    hangPlay();
    const pending = collectCamProbe(makeStream([makeOriginal()]), { timeoutMs: 100 });
    const assertion = expect(pending).rejects.toThrow("camprobe_timeout");
    await vi.advanceTimersByTimeAsync(100);
    await assertion;
    expect(probeTrack.stop).toHaveBeenCalledTimes(1);
    expect(video.remove).toHaveBeenCalled();
    expect(video.srcObject).toBeNull();
  });

  it("chưa tới hạn thì chưa reject", async () => {
    hangPlay();
    let settled = false;
    const pending = collectCamProbe(makeStream([makeOriginal()]), { timeoutMs: 100 });
    void pending.catch(() => undefined).finally(() => (settled = true));
    await vi.advanceTimersByTimeAsync(99);
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(settled).toBe(true);
  });

  it("signal abort giữa chừng → reject camprobe_aborted và tắt bản clone", async () => {
    hangPlay();
    const controller = new AbortController();
    const pending = collectCamProbe(makeStream([makeOriginal()]), {
      signal: controller.signal,
      timeoutMs: 10_000,
    });
    const assertion = expect(pending).rejects.toThrow("camprobe_aborted");
    await vi.advanceTimersByTimeAsync(10);
    controller.abort();
    await assertion;
    expect(probeTrack.stop).toHaveBeenCalledTimes(1);
    expect(video.remove).toHaveBeenCalled();
  });

  it("thành công, không có requestVideoFrameCallback → không có khóa duplicate_frame_ratio", async () => {
    const result = await collectCamProbe(makeStream([makeOriginal()]));
    expect("duplicate_frame_ratio" in result).toBe(false);
    expect(result.api_tamper_flags).toEqual([]);
    expect(result.device_label).toBe("Camera thật");
    expect(result.constraint_probes.length).toBeGreaterThan(0);
    // Bỏ định danh phần cứng.
    expect(result.track_settings).toEqual({ width: 1280, height: 720 });
    expect(result.track_capabilities).toEqual({ width: { min: 1, max: 1920 } });
    // Dọn dẹp sau khi xong.
    expect(probeTrack.stop).toHaveBeenCalledTimes(1);
    expect(video.remove).toHaveBeenCalled();
  });

  it("thành công, có requestVideoFrameCallback → duplicate_frame_ratio được gửi", async () => {
    stubDom({ rVFC: true });
    useRealisticProbeTrack();
    const result = await collectCamProbe(makeStream([makeOriginal()]));
    // Khung giả luôn giống nhau → mọi cặp trùng.
    expect(result.duplicate_frame_ratio).toBe(1);
  });
});
