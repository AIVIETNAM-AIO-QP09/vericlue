import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  IMAGE_JPEG_QUALITY,
  IMAGE_MAX_EDGE,
  VIDEO_BITS_PER_SECOND,
  VIDEO_CLIP_MS,
  VIDEO_STOP_GRACE_MS,
  captureJpeg,
  fitWithin,
  pickVideoMimeType,
  startVideoClip,
} from "./media";

describe("fitWithin", () => {
  it("không phóng to ảnh nhỏ hơn khung", () => {
    expect(fitWithin(640, 480)).toEqual({ width: 640, height: 480 });
  });

  it("ảnh đúng bằng khung giữ nguyên", () => {
    expect(fitWithin(1280, 720)).toEqual({ width: 1280, height: 720 });
  });

  it("thu nhỏ 1920x1080 về cạnh dài 1280, giữ tỉ lệ", () => {
    expect(fitWithin(1920, 1080)).toEqual({ width: 1280, height: 720 });
  });

  it("ảnh dọc: cạnh dài là chiều cao", () => {
    expect(fitWithin(1080, 1920)).toEqual({ width: 720, height: 1280 });
  });

  it("làm tròn cạnh ngắn", () => {
    // 1000/3000 * 1280 = 426.67 → 427
    expect(fitWithin(3000, 1000)).toEqual({ width: 1280, height: 427 });
  });

  it("cạnh ngắn không bao giờ dưới 1", () => {
    expect(fitWithin(100000, 1)).toEqual({ width: 1280, height: 1 });
  });

  it("cạnh dài kết quả không vượt IMAGE_MAX_EDGE", () => {
    const out = fitWithin(4032, 3024);
    expect(Math.max(out.width, out.height)).toBe(IMAGE_MAX_EDGE);
  });

  it("maxEdge tùy chỉnh", () => {
    expect(fitWithin(800, 400, 200)).toEqual({ width: 200, height: 100 });
  });
});

type FakeCanvas = {
  width: number;
  height: number;
  getContext: ReturnType<typeof vi.fn>;
  toBlob: ReturnType<typeof vi.fn>;
};

function videoOf(width: number, height: number): HTMLVideoElement {
  return { videoWidth: width, videoHeight: height } as unknown as HTMLVideoElement;
}

describe("captureJpeg", () => {
  let canvas: FakeCanvas;
  let drawImage: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    drawImage = vi.fn();
    canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn(() => ({ drawImage })),
      toBlob: vi.fn((cb: BlobCallback) => cb(new Blob(["jpg"], { type: "image/jpeg" }))),
    };
    vi.stubGlobal("document", { createElement: vi.fn(() => canvas) });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("ném lỗi khi videoWidth = 0", async () => {
    await expect(captureJpeg(videoOf(0, 720))).rejects.toThrow("Chưa có khung hình");
  });

  it("ném lỗi khi videoHeight = 0", async () => {
    await expect(captureJpeg(videoOf(1280, 0))).rejects.toThrow("Chưa có khung hình");
  });

  it("canvas có kích thước đã thu nhỏ và vẽ đúng kích thước đó", async () => {
    const video = videoOf(1920, 1080);
    await captureJpeg(video);
    expect(canvas.width).toBe(1280);
    expect(canvas.height).toBe(720);
    expect(canvas.getContext).toHaveBeenCalledWith("2d");
    expect(drawImage).toHaveBeenCalledWith(video, 0, 0, 1280, 720);
  });

  it("giữ nguyên kích thước khi ảnh nhỏ", async () => {
    await captureJpeg(videoOf(640, 480));
    expect([canvas.width, canvas.height]).toEqual([640, 480]);
  });

  it("gọi toBlob với image/jpeg và IMAGE_JPEG_QUALITY, trả Blob đó", async () => {
    const blob = await captureJpeg(videoOf(640, 480));
    expect(canvas.toBlob).toHaveBeenCalledTimes(1);
    expect(canvas.toBlob.mock.calls[0][1]).toBe("image/jpeg");
    expect(canvas.toBlob.mock.calls[0][2]).toBe(IMAGE_JPEG_QUALITY);
    expect(IMAGE_JPEG_QUALITY).toBe(0.9);
    expect(blob.type).toBe("image/jpeg");
    expect(blob.size).toBe(3);
  });

  it("ném lỗi khi không lấy được context 2d", async () => {
    canvas.getContext.mockReturnValue(null);
    await expect(captureJpeg(videoOf(640, 480))).rejects.toThrow("canvas");
  });

  it("ném lỗi khi toBlob trả null", async () => {
    canvas.toBlob.mockImplementation((cb: BlobCallback) => cb(null));
    await expect(captureJpeg(videoOf(640, 480))).rejects.toThrow("mã hóa");
  });
});

describe("pickVideoMimeType", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("ưu tiên vp8 khi hỗ trợ tất cả", () => {
    expect(pickVideoMimeType(() => true)).toBe("video/webm;codecs=vp8");
  });

  it("rơi xuống vp9 rồi webm trơn theo thứ tự", () => {
    expect(pickVideoMimeType((t) => t !== "video/webm;codecs=vp8")).toBe("video/webm;codecs=vp9");
    expect(pickVideoMimeType((t) => t === "video/webm")).toBe("video/webm");
  });

  it("null khi không hỗ trợ định dạng nào", () => {
    expect(pickVideoMimeType(() => false)).toBeNull();
  });

  it("null khi không có MediaRecorder (mặc định)", () => {
    vi.stubGlobal("MediaRecorder", undefined);
    expect(pickVideoMimeType(undefined)).toBeNull();
    expect(pickVideoMimeType()).toBeNull();
  });

  it("mặc định dùng MediaRecorder.isTypeSupported khi có", () => {
    const isTypeSupported = vi.fn((t: string) => t === "video/webm");
    vi.stubGlobal("MediaRecorder", { isTypeSupported });
    expect(pickVideoMimeType()).toBe("video/webm");
    expect(isTypeSupported).toHaveBeenCalled();
  });
});

// --- startVideoClip ------------------------------------------------------------------------

type RecorderBehavior = {
  ctorThrows: boolean;
  startThrows: boolean;
  chunksOnStop: Blob[];
  /** true: trình duyệt không bao giờ bắn sự kiện stop. */
  silentStop?: boolean;
};

class FakeRecorder {
  static instances: FakeRecorder[] = [];
  static behavior: RecorderBehavior;
  state: "inactive" | "recording" = "inactive";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;
  stopCalls = 0;
  constructor(
    public stream: unknown,
    public options: { mimeType: string; videoBitsPerSecond: number },
  ) {
    if (FakeRecorder.behavior.ctorThrows) throw new Error("mimeType không hỗ trợ");
    FakeRecorder.instances.push(this);
  }
  start() {
    if (FakeRecorder.behavior.startThrows) throw new Error("start lỗi");
    this.state = "recording";
  }
  stop() {
    this.stopCalls += 1;
    this.state = "inactive";
    if (FakeRecorder.behavior.silentStop) return;
    // Trình duyệt thật bắn sự kiện bất đồng bộ.
    queueMicrotask(() => {
      for (const data of FakeRecorder.behavior.chunksOnStop) this.ondataavailable?.({ data });
      this.onstop?.();
    });
  }
}

class FakeStream {
  constructor(public tracks: unknown[]) {}
}

function streamWith(videoTracks: unknown[]): MediaStream {
  return { getVideoTracks: () => videoTracks } as unknown as MediaStream;
}

describe("startVideoClip", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeRecorder.instances = [];
    FakeRecorder.behavior = {
      ctorThrows: false,
      startThrows: false,
      chunksOnStop: [new Blob(["abc"])],
    };
    vi.stubGlobal("MediaRecorder", FakeRecorder);
    vi.stubGlobal("MediaStream", FakeStream);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  const track = { kind: "video" };
  const MIME = "video/webm;codecs=vp8";

  it("trả Blob webm sau durationMs", async () => {
    const clip = startVideoClip(streamWith([track]), { durationMs: 3000, mimeType: MIME });
    const recorder = FakeRecorder.instances[0];
    expect(recorder.state).toBe("recording");
    expect(recorder.options).toEqual({ mimeType: MIME, videoBitsPerSecond: VIDEO_BITS_PER_SECOND });
    expect((recorder.stream as FakeStream).tracks).toEqual([track]);

    await vi.advanceTimersByTimeAsync(2999);
    expect(recorder.stopCalls).toBe(0);
    await vi.advanceTimersByTimeAsync(1);
    expect(recorder.stopCalls).toBe(1);

    const blob = await clip.done;
    expect(blob).not.toBeNull();
    expect(blob?.type).toBe("video/webm");
    expect(blob?.size).toBe(3);
  });

  it("durationMs mặc định là VIDEO_CLIP_MS", async () => {
    startVideoClip(streamWith([track]), { mimeType: MIME });
    const recorder = FakeRecorder.instances[0];
    await vi.advanceTimersByTimeAsync(VIDEO_CLIP_MS - 1);
    expect(recorder.stopCalls).toBe(0);
    await vi.advanceTimersByTimeAsync(1);
    expect(recorder.stopCalls).toBe(1);
  });

  it("stop() sớm vẫn trả phần đã ghi và hủy hẹn giờ", async () => {
    const clip = startVideoClip(streamWith([track]), { durationMs: 3000, mimeType: MIME });
    const recorder = FakeRecorder.instances[0];
    clip.stop();
    expect(recorder.stopCalls).toBe(1);
    const blob = await clip.done;
    expect(blob?.size).toBe(3);

    await vi.advanceTimersByTimeAsync(5000);
    expect(recorder.stopCalls).toBe(1); // hẹn giờ đã bị hủy
    clip.stop(); // gọi lại an toàn
    expect(recorder.stopCalls).toBe(1);
  });

  it("mimeType null → done = null, không tạo recorder", async () => {
    const clip = startVideoClip(streamWith([track]), { mimeType: null });
    expect(await clip.done).toBeNull();
    expect(FakeRecorder.instances).toHaveLength(0);
    expect(() => clip.stop()).not.toThrow();
  });

  it("mimeType không truyền → tự chọn qua MediaRecorder.isTypeSupported", async () => {
    // Thêm isTypeSupported tĩnh cho FakeRecorder để pickVideoMimeType mặc định dùng.
    (FakeRecorder as unknown as { isTypeSupported: (t: string) => boolean }).isTypeSupported = (
      t,
    ) => t === "video/webm";
    try {
      const clip = startVideoClip(streamWith([track]), { durationMs: 10 });
      expect(FakeRecorder.instances[0].options.mimeType).toBe("video/webm");
      await vi.advanceTimersByTimeAsync(10);
      expect(await clip.done).not.toBeNull();
    } finally {
      delete (FakeRecorder as unknown as { isTypeSupported?: unknown }).isTypeSupported;
    }
  });

  it("stream không có video track → null", async () => {
    const clip = startVideoClip(streamWith([]), { mimeType: MIME });
    expect(await clip.done).toBeNull();
    expect(FakeRecorder.instances).toHaveLength(0);
  });

  it("không có MediaRecorder → null", async () => {
    vi.stubGlobal("MediaRecorder", undefined);
    const clip = startVideoClip(streamWith([track]), { mimeType: MIME });
    expect(await clip.done).toBeNull();
  });

  it("constructor ném lỗi → null", async () => {
    FakeRecorder.behavior.ctorThrows = true;
    const clip = startVideoClip(streamWith([track]), { mimeType: MIME });
    expect(await clip.done).toBeNull();
  });

  it("start() ném lỗi → null", async () => {
    FakeRecorder.behavior.startThrows = true;
    const clip = startVideoClip(streamWith([track]), { mimeType: MIME });
    expect(await clip.done).toBeNull();
  });

  it("onerror → null và dừng recorder", async () => {
    const clip = startVideoClip(streamWith([track]), { durationMs: 3000, mimeType: MIME });
    const recorder = FakeRecorder.instances[0];
    recorder.onerror?.();
    expect(await clip.done).toBeNull();
    expect(recorder.stopCalls).toBe(1);
  });

  it("onerror: kết quả là null dù onstop bắn sau đó kèm chunk", async () => {
    const clip = startVideoClip(streamWith([track]), { durationMs: 3000, mimeType: MIME });
    FakeRecorder.instances[0].onerror?.();
    await vi.advanceTimersByTimeAsync(0); // để onstop (với chunk) bắn
    expect(await clip.done).toBeNull();
  });

  it("onerror hủy hẹn giờ dừng (không dừng lần hai)", async () => {
    startVideoClip(streamWith([track]), { durationMs: 3000, mimeType: MIME });
    const recorder = FakeRecorder.instances[0];
    recorder.onerror?.();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(recorder.stopCalls).toBe(1);
  });

  it("onstop không bao giờ bắn → done = null sau VIDEO_STOP_GRACE_MS", async () => {
    FakeRecorder.behavior.silentStop = true;
    const clip = startVideoClip(streamWith([track]), { durationMs: 3000, mimeType: MIME });
    let settled = false;
    void clip.done.then(() => (settled = true));

    await vi.advanceTimersByTimeAsync(3000); // tới hạn ghi → stop()
    expect(FakeRecorder.instances[0].stopCalls).toBe(1);
    await vi.advanceTimersByTimeAsync(VIDEO_STOP_GRACE_MS - 1);
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(settled).toBe(true);
    expect(await clip.done).toBeNull();
  });

  it("stop() sớm mà onstop không bắn → null sau thời gian ân hạn", async () => {
    FakeRecorder.behavior.silentStop = true;
    const clip = startVideoClip(streamWith([track]), { durationMs: 60_000, mimeType: MIME });
    clip.stop();
    clip.stop(); // gọi lại không đặt thêm hẹn giờ
    await vi.advanceTimersByTimeAsync(VIDEO_STOP_GRACE_MS);
    expect(await clip.done).toBeNull();
  });

  it("onstop bắn kịp thì kết quả giữ Blob, hẹn giờ ân hạn bị hủy", async () => {
    const clip = startVideoClip(streamWith([track]), { durationMs: 100, mimeType: MIME });
    await vi.advanceTimersByTimeAsync(100);
    const blob = await clip.done;
    expect(blob?.size).toBe(3);
    await vi.advanceTimersByTimeAsync(VIDEO_STOP_GRACE_MS * 2);
    expect(await clip.done).toBe(blob);
  });

  it("không có chunk nào → null", async () => {
    FakeRecorder.behavior.chunksOnStop = [];
    const clip = startVideoClip(streamWith([track]), { durationMs: 100, mimeType: MIME });
    await vi.advanceTimersByTimeAsync(100);
    expect(await clip.done).toBeNull();
  });

  it("chunk rỗng (size 0) bị bỏ qua → null", async () => {
    FakeRecorder.behavior.chunksOnStop = [new Blob([])];
    const clip = startVideoClip(streamWith([track]), { durationMs: 100, mimeType: MIME });
    await vi.advanceTimersByTimeAsync(100);
    expect(await clip.done).toBeNull();
  });

  it("nhiều chunk được ghép thành một Blob", async () => {
    FakeRecorder.behavior.chunksOnStop = [new Blob(["ab"]), new Blob(["cde"])];
    const clip = startVideoClip(streamWith([track]), { durationMs: 100, mimeType: MIME });
    await vi.advanceTimersByTimeAsync(100);
    expect((await clip.done)?.size).toBe(5);
  });
});
