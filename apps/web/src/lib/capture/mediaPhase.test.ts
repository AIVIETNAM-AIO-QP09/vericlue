import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { VideoClip } from "./media";
import { captureNeutralMedia, captureThenFlash } from "./mediaPhase";

function videoOf(width: number, height: number): HTMLVideoElement {
  return { videoWidth: width, videoHeight: height } as unknown as HTMLVideoElement;
}

const STREAM = {} as unknown as MediaStream;

/** Clip giả: `done` do test điều khiển bằng `finish`. */
function fakeClip(log: string[]) {
  let finish: (blob: Blob | null) => void = () => undefined;
  const done = new Promise<Blob | null>((resolve) => {
    finish = (blob) => {
      log.push("clip:done");
      resolve(blob);
    };
  });
  const stop = vi.fn(() => {
    log.push("clip:stop");
    finish(null);
  });
  const clip: VideoClip = { done, stop };
  return { clip, finish: (blob: Blob | null) => finish(blob), stop };
}

describe("captureNeutralMedia", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("chụp ảnh TRƯỚC khi bắt đầu quay clip (nhật ký sự kiện)", async () => {
    const log: string[] = [];
    const image = new Blob(["img"]);
    const fake = fakeClip(log);
    const pending = captureNeutralMedia({
      video: videoOf(1920, 1080),
      stream: STREAM,
      captureImage: async () => {
        log.push("image");
        return image;
      },
      startClip: () => {
        log.push("clip:start");
        return fake.clip;
      },
    });
    await vi.advanceTimersByTimeAsync(0);
    expect(log).toEqual(["image", "clip:start"]);
    fake.finish(null);
    await pending;
    expect(log).toEqual(["image", "clip:start", "clip:done"]);
  });

  it("chờ clip.done (3 giây) rồi mới resolve", async () => {
    const log: string[] = [];
    const clipBlob = new Blob(["webm"]);
    const done = new Promise<Blob | null>((resolve) => setTimeout(() => resolve(clipBlob), 3000));
    let settled = false;
    const pending = captureNeutralMedia({
      video: videoOf(1920, 1080),
      stream: STREAM,
      captureImage: async () => new Blob(["img"]),
      startClip: () => ({ done, stop: vi.fn() }),
    });
    void pending.then(() => {
      settled = true;
      log.push("resolved");
    });

    await vi.advanceTimersByTimeAsync(2999);
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(settled).toBe(true);
    expect((await pending)?.clip).toBe(clipBlob);
  });

  it("trả image, clip, imageSize (đã thu nhỏ) và sourceSize", async () => {
    const image = new Blob(["img"]);
    const clipBlob = new Blob(["webm"]);
    const result = await captureNeutralMedia({
      video: videoOf(1920, 1080),
      stream: STREAM,
      captureImage: async () => image,
      startClip: () => ({ done: Promise.resolve(clipBlob), stop: vi.fn() }),
    });
    expect(result).not.toBeNull();
    expect(result?.image).toBe(image);
    expect(result?.clip).toBe(clipBlob);
    expect(result?.sourceSize).toEqual({ width: 1920, height: 1080 });
    expect(result?.imageSize).toEqual({ width: 1280, height: 720 });
  });

  it("ảnh nhỏ không bị phóng to: imageSize = sourceSize", async () => {
    const result = await captureNeutralMedia({
      video: videoOf(640, 480),
      stream: STREAM,
      captureImage: async () => new Blob(["img"]),
      startClip: () => ({ done: Promise.resolve(null), stop: vi.fn() }),
    });
    expect(result?.imageSize).toEqual({ width: 640, height: 480 });
    expect(result?.sourceSize).toEqual({ width: 640, height: 480 });
  });

  it("clip.done = null (không ghi được) vẫn trả ảnh, clip null", async () => {
    const result = await captureNeutralMedia({
      video: videoOf(640, 480),
      stream: STREAM,
      captureImage: async () => new Blob(["img"]),
      startClip: () => ({ done: Promise.resolve(null), stop: vi.fn() }),
    });
    expect(result?.clip).toBeNull();
    expect(result?.image.size).toBe(3);
  });

  it("stream null → clip null và không gọi startClip", async () => {
    const startClip = vi.fn();
    const result = await captureNeutralMedia({
      video: videoOf(1920, 1080),
      stream: null,
      captureImage: async () => new Blob(["img"]),
      startClip,
    });
    expect(startClip).not.toHaveBeenCalled();
    expect(result?.clip).toBeNull();
    expect(result?.imageSize).toEqual({ width: 1280, height: 720 });
  });

  it("abort giữa lúc chờ clip → clip.stop() được gọi và trả null", async () => {
    const log: string[] = [];
    const fake = fakeClip(log);
    const controller = new AbortController();
    const pending = captureNeutralMedia({
      video: videoOf(1920, 1080),
      stream: STREAM,
      signal: controller.signal,
      captureImage: async () => {
        log.push("image");
        return new Blob(["img"]);
      },
      startClip: () => {
        log.push("clip:start");
        return fake.clip;
      },
    });
    await vi.advanceTimersByTimeAsync(1000);
    expect(log).toEqual(["image", "clip:start"]);
    controller.abort();
    expect(await pending).toBeNull();
    expect(fake.stop).toHaveBeenCalledTimes(1);
    expect(log).toEqual(["image", "clip:start", "clip:stop", "clip:done"]);
  });

  it("abort từ trước → null và không chụp ảnh", async () => {
    const controller = new AbortController();
    controller.abort();
    const captureImage = vi.fn(async () => new Blob(["img"]));
    const startClip = vi.fn();
    const result = await captureNeutralMedia({
      video: videoOf(1920, 1080),
      stream: STREAM,
      signal: controller.signal,
      captureImage,
      startClip,
    });
    expect(result).toBeNull();
    expect(captureImage).not.toHaveBeenCalled();
    expect(startClip).not.toHaveBeenCalled();
  });

  it("abort trong lúc chụp ảnh → null và không quay clip", async () => {
    const controller = new AbortController();
    const startClip = vi.fn();
    const result = await captureNeutralMedia({
      video: videoOf(1920, 1080),
      stream: STREAM,
      signal: controller.signal,
      captureImage: async () => {
        controller.abort();
        return new Blob(["img"]);
      },
      startClip,
    });
    expect(result).toBeNull();
    expect(startClip).not.toHaveBeenCalled();
  });

  it("captureImage ném lỗi → reject, không quay clip", async () => {
    const startClip = vi.fn();
    await expect(
      captureNeutralMedia({
        video: videoOf(0, 0),
        stream: STREAM,
        captureImage: async () => {
          throw new Error("Chưa có khung hình từ camera");
        },
        startClip,
      }),
    ).rejects.toThrow("Chưa có khung hình");
    expect(startClip).not.toHaveBeenCalled();
  });

  it("gỡ listener abort sau khi xong (abort muộn không dừng clip)", async () => {
    const stop = vi.fn();
    const controller = new AbortController();
    await captureNeutralMedia({
      video: videoOf(640, 480),
      stream: STREAM,
      signal: controller.signal,
      captureImage: async () => new Blob(["img"]),
      startClip: () => ({ done: Promise.resolve(new Blob(["x"])), stop }),
    });
    controller.abort();
    expect(stop).not.toHaveBeenCalled();
  });
});

describe("captureThenFlash", () => {
  it("flash CHỈ chạy sau khi capture resolve", async () => {
    const log: string[] = [];
    let release: (value: string) => void = () => undefined;
    const pending = captureThenFlash({
      capture: () => {
        log.push("capture:start");
        return new Promise<string>((resolve) => {
          release = (value) => {
            log.push("capture:done");
            resolve(value);
          };
        });
      },
      flash: async () => {
        log.push("flash:start");
        return "flash-result";
      },
    });
    await Promise.resolve();
    expect(log).toEqual(["capture:start"]);
    release("anh");
    await pending;
    expect(log).toEqual(["capture:start", "capture:done", "flash:start"]);
  });

  it("flash nhận đúng giá trị capture và kết quả được trả về cả hai", async () => {
    const flash = vi.fn(async (captured: { id: number }) => `flash-${captured.id}`);
    const captured = { id: 7 };
    const result = await captureThenFlash({ capture: async () => captured, flash });
    expect(flash).toHaveBeenCalledWith(captured);
    expect(result).toEqual({ captured, flash: "flash-7" });
    expect(result?.captured).toBe(captured);
  });

  it("capture trả null → flash KHÔNG được gọi và kết quả null", async () => {
    const flash = vi.fn(async () => "x");
    const result = await captureThenFlash<string, string>({ capture: async () => null, flash });
    expect(result).toBeNull();
    expect(flash).not.toHaveBeenCalled();
  });

  it("lỗi từ capture lan ra, flash không chạy", async () => {
    const flash = vi.fn(async () => "x");
    await expect(
      captureThenFlash<string, string>({
        capture: async () => {
          throw new Error("capture lỗi");
        },
        flash,
      }),
    ).rejects.toThrow("capture lỗi");
    expect(flash).not.toHaveBeenCalled();
  });

  it("lỗi từ flash lan ra", async () => {
    await expect(
      captureThenFlash({
        capture: async () => "ok",
        flash: async () => {
          throw new Error("flash lỗi");
        },
      }),
    ).rejects.toThrow("flash lỗi");
  });

  it("capture giá trị falsy khác null (0, chuỗi rỗng) vẫn chạy flash", async () => {
    const flash = vi.fn(async (v: number) => v + 1);
    const result = await captureThenFlash({ capture: async () => 0, flash });
    expect(flash).toHaveBeenCalledWith(0);
    expect(result).toEqual({ captured: 0, flash: 1 });
  });
});

describe("tích hợp: clip 3 giây xong rồi mới nháy màu", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("nhật ký: image → clip:start → clip:done → flash", async () => {
    const log: string[] = [];
    const pending = captureThenFlash({
      capture: () =>
        captureNeutralMedia({
          video: videoOf(1920, 1080),
          stream: STREAM,
          captureImage: async () => {
            log.push("image");
            return new Blob(["img"]);
          },
          startClip: () => {
            log.push("clip:start");
            const done = new Promise<Blob | null>((resolve) =>
              setTimeout(() => {
                log.push("clip:done");
                resolve(new Blob(["webm"]));
              }, 3000),
            );
            return { done, stop: vi.fn() };
          },
        }),
      flash: async (captured) => {
        log.push("flash");
        return captured.clip?.size ?? 0;
      },
    });

    await vi.advanceTimersByTimeAsync(2999);
    expect(log).toEqual(["image", "clip:start"]); // chưa nháy khi clip chưa xong
    await vi.advanceTimersByTimeAsync(1);
    const result = await pending;
    expect(log).toEqual(["image", "clip:start", "clip:done", "flash"]);
    expect(result?.flash).toBe(4);
  });

  it("hủy giữa lúc quay clip → không nháy màu", async () => {
    const log: string[] = [];
    const controller = new AbortController();
    const fake = fakeClip(log);
    const flash = vi.fn(async () => "x");
    const pending = captureThenFlash({
      capture: () =>
        captureNeutralMedia({
          video: videoOf(1920, 1080),
          stream: STREAM,
          signal: controller.signal,
          captureImage: async () => new Blob(["img"]),
          startClip: () => fake.clip,
        }),
      flash,
    });
    await vi.advanceTimersByTimeAsync(500);
    controller.abort();
    expect(await pending).toBeNull();
    expect(flash).not.toHaveBeenCalled();
    expect(fake.stop).toHaveBeenCalledTimes(1);
  });
});
