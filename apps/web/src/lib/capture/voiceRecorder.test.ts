import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VOICE_CONSTRAINTS, VOICE_MAX_MS, VoiceRecorder } from "./voiceRecorder";

// --- đồ giả -------------------------------------------------------------------------------

type FakeTrack = { stop: ReturnType<typeof vi.fn> };
type PortMessage = { data: Float32Array };

class FakeNode {
  static instances: FakeNode[] = [];
  port: { onmessage: ((event: PortMessage) => void) | null } = { onmessage: null };
  disconnect = vi.fn();
  connect = vi.fn();
  constructor(
    public context: unknown,
    public name: string,
  ) {
    FakeNode.instances.push(this);
  }
  emit(samples: Float32Array) {
    this.port.onmessage?.({ data: samples });
  }
}

type Env = {
  contexts: FakeContext[];
  tracks: FakeTrack[];
  getUserMedia: ReturnType<typeof vi.fn>;
  sampleRate: number;
  addModule: ReturnType<typeof vi.fn>;
  order: string[];
};

let env: Env;

class FakeContext {
  state: "suspended" | "running" | "closed" = "suspended";
  sampleRate = env.sampleRate;
  resume = vi.fn(async () => {
    env.order.push("resume");
    this.state = "running";
  });
  close = vi.fn(async () => {
    this.state = "closed";
  });
  audioWorklet = { addModule: env.addModule };
  source = { connect: vi.fn() };
  createMediaStreamSource = vi.fn(() => this.source);
  destination = { kind: "destination" };
  gains: {
    gain: { value: number };
    connect: ReturnType<typeof vi.fn>;
    disconnect: ReturnType<typeof vi.fn>;
  }[] = [];
  createGain = vi.fn(() => {
    const gain = { gain: { value: 1 }, connect: vi.fn(), disconnect: vi.fn() };
    this.gains.push(gain);
    return gain;
  });
  constructor() {
    env.contexts.push(this);
  }
}

function setup(sampleRate = 16000) {
  const tracks: FakeTrack[] = [{ stop: vi.fn() }, { stop: vi.fn() }];
  env = {
    contexts: [],
    tracks,
    sampleRate,
    order: [],
    addModule: vi.fn(async () => undefined),
    getUserMedia: vi.fn(async () => {
      env.order.push("getUserMedia");
      return { getTracks: () => tracks };
    }),
  };
  FakeNode.instances = [];
  vi.stubGlobal("window", { AudioContext: FakeContext });
  vi.stubGlobal("AudioWorkletNode", FakeNode);
  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: env.getUserMedia } });
}

async function readWav(blob: Blob): Promise<DataView> {
  return new DataView(await blob.arrayBuffer());
}

describe("VoiceRecorder", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setup();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  describe("constructor", () => {
    it("ném lỗi khi không có AudioContext", () => {
      vi.stubGlobal("window", {});
      expect(() => new VoiceRecorder()).toThrow("không hỗ trợ ghi âm");
    });

    it("dùng webkitAudioContext khi không có AudioContext", () => {
      vi.stubGlobal("window", { webkitAudioContext: FakeContext });
      new VoiceRecorder();
      expect(env.contexts).toHaveLength(1);
    });

    it("tạo AudioContext và gọi resume đồng bộ", () => {
      new VoiceRecorder();
      expect(env.contexts).toHaveLength(1);
      expect(env.contexts[0].resume).toHaveBeenCalledTimes(1);
    });
  });

  describe("start", () => {
    it("xin micro đúng VOICE_CONSTRAINTS (tắt AEC/NS/AGC, mono)", async () => {
      const recorder = new VoiceRecorder();
      await recorder.start();
      expect(env.getUserMedia).toHaveBeenCalledWith({ audio: VOICE_CONSTRAINTS, video: false });
      expect(VOICE_CONSTRAINTS).toEqual({
        channelCount: 1,
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      });
    });

    it("nạp worklet và nối nguồn micro vào node pcm-recorder", async () => {
      const recorder = new VoiceRecorder();
      await recorder.start();
      expect(env.addModule).toHaveBeenCalledWith("/pcm-recorder.worklet.js");
      expect(FakeNode.instances).toHaveLength(1);
      expect(FakeNode.instances[0].name).toBe("pcm-recorder");
      expect(env.contexts[0].source.connect).toHaveBeenCalledWith(FakeNode.instances[0]);
    });

    it("gọi resume() sau getUserMedia (iOS có thể để context suspended)", async () => {
      const recorder = new VoiceRecorder();
      await recorder.start();
      // resume lần 1 ở constructor, lần 2 sau khi xin micro.
      expect(env.order).toEqual(["resume", "getUserMedia", "resume"]);
    });

    it("nối micro → node → gain(0) → destination", async () => {
      const recorder = new VoiceRecorder();
      await recorder.start();
      const ctx = env.contexts[0];
      const node = FakeNode.instances[0];
      expect(ctx.createGain).toHaveBeenCalledTimes(1);
      const gain = ctx.gains[0];
      expect(gain.gain.value).toBe(0);
      expect(node.connect).toHaveBeenCalledWith(gain);
      expect(gain.connect).toHaveBeenCalledWith(ctx.destination);
      expect(ctx.source.connect).toHaveBeenCalledWith(node);
    });

    it("stop() ngắt gain cùng node", async () => {
      const recorder = new VoiceRecorder();
      await recorder.start();
      await recorder.stop();
      expect(env.contexts[0].gains[0].disconnect).toHaveBeenCalledTimes(1);
      expect(FakeNode.instances[0].disconnect).toHaveBeenCalledTimes(1);
    });

    it("cancel() ngắt gain", async () => {
      const recorder = new VoiceRecorder();
      await recorder.start();
      recorder.cancel();
      expect(env.contexts[0].gains[0].disconnect).toHaveBeenCalledTimes(1);
    });

    it("getUserMedia bị từ chối: dọn dẹp và ném lại đúng lỗi", async () => {
      const denied = new Error("NotAllowedError");
      env.getUserMedia.mockRejectedValue(denied);
      const recorder = new VoiceRecorder();
      await expect(recorder.start()).rejects.toBe(denied);
      expect(env.contexts[0].close).toHaveBeenCalled();
      expect(env.addModule).not.toHaveBeenCalled();
    });

    it("addModule lỗi sau khi có stream: dừng track, đóng context, ném lại", async () => {
      const failure = new Error("không nạp được worklet");
      env.addModule.mockRejectedValue(failure);
      const recorder = new VoiceRecorder();
      await expect(recorder.start()).rejects.toBe(failure);
      for (const track of env.tracks) expect(track.stop).toHaveBeenCalledTimes(1);
      expect(env.contexts[0].close).toHaveBeenCalled();
    });

    it("start lỗi thì không đặt hẹn giờ tự dừng", async () => {
      env.getUserMedia.mockRejectedValue(new Error("x"));
      const onAutoStop = vi.fn();
      const recorder = new VoiceRecorder({ maxMs: 100, onAutoStop });
      await recorder.start().catch(() => undefined);
      await vi.advanceTimersByTimeAsync(1000);
      expect(onAutoStop).not.toHaveBeenCalled();
    });
  });

  describe("stop", () => {
    it("trả WAV 16 kHz khi context đã ở 16 kHz", async () => {
      const recorder = new VoiceRecorder();
      await recorder.start();
      const node = FakeNode.instances[0];
      node.emit(new Float32Array([0.5, -0.5]));
      node.emit(new Float32Array([1]));

      const blob = await recorder.stop();
      expect(blob.type).toBe("audio/wav");
      expect(blob.size).toBe(44 + 3 * 2);
      const view = await readWav(blob);
      expect(view.getUint32(24, true)).toBe(16000);
      expect(view.getInt16(44, true)).toBe(Math.round(0.5 * 32767));
      expect(view.getInt16(46, true)).toBe(-16384);
      expect(view.getInt16(48, true)).toBe(32767);
    });

    it("hạ 48 kHz xuống 16 kHz (không có OfflineAudioContext → boxResample)", async () => {
      setup(48000);
      vi.stubGlobal("OfflineAudioContext", undefined);
      const recorder = new VoiceRecorder();
      await recorder.start();
      const node = FakeNode.instances[0];
      node.emit(new Float32Array(24000).fill(0.5));
      node.emit(new Float32Array(24000).fill(0.5));

      const blob = await recorder.stop();
      expect(blob.size).toBe(44 + 16000 * 2);
      const view = await readWav(blob);
      expect(view.getUint32(24, true)).toBe(16000);
      expect(view.getInt16(44 + 100 * 2, true)).toBe(Math.round(0.5 * 32767));
    });

    it("idempotent: gọi hai lần trả cùng một promise", async () => {
      const recorder = new VoiceRecorder();
      await recorder.start();
      const first = recorder.stop();
      const second = recorder.stop();
      expect(second).toBe(first);
      await first;
      expect(env.contexts[0].close).toHaveBeenCalledTimes(1);
    });

    it("dừng mọi track, ngắt node và đóng context", async () => {
      const recorder = new VoiceRecorder();
      await recorder.start();
      await recorder.stop();
      for (const track of env.tracks) expect(track.stop).toHaveBeenCalledTimes(1);
      expect(FakeNode.instances[0].disconnect).toHaveBeenCalled();
      expect(env.contexts[0].close).toHaveBeenCalledTimes(1);
      expect(env.contexts[0].state).toBe("closed");
    });

    it("không có chunk nào thì trả WAV rỗng hợp lệ (44 byte)", async () => {
      const recorder = new VoiceRecorder();
      await recorder.start();
      const blob = await recorder.stop();
      expect(blob.size).toBe(44);
    });

    it("hủy hẹn giờ tự dừng khi dừng thủ công", async () => {
      const onAutoStop = vi.fn();
      const recorder = new VoiceRecorder({ maxMs: 500, onAutoStop });
      await recorder.start();
      await recorder.stop();
      await vi.advanceTimersByTimeAsync(2000);
      expect(onAutoStop).not.toHaveBeenCalled();
    });
  });

  describe("tự dừng", () => {
    it("sau maxMs tự dừng và gọi onAutoStop", async () => {
      const onAutoStop = vi.fn();
      const recorder = new VoiceRecorder({ maxMs: 1000, onAutoStop });
      await recorder.start();
      FakeNode.instances[0].emit(new Float32Array([0.1, 0.2]));

      await vi.advanceTimersByTimeAsync(999);
      expect(onAutoStop).not.toHaveBeenCalled();
      expect(env.contexts[0].close).not.toHaveBeenCalled();

      await vi.advanceTimersByTimeAsync(1);
      const blob = await recorder.stop(); // cùng promise với lần tự dừng
      expect(onAutoStop).toHaveBeenCalledTimes(1);
      expect(blob.size).toBe(44 + 2 * 2);
      expect(env.contexts[0].close).toHaveBeenCalledTimes(1);
    });

    it("mặc định VOICE_MAX_MS", async () => {
      const onAutoStop = vi.fn();
      const recorder = new VoiceRecorder({ onAutoStop });
      await recorder.start();
      await vi.advanceTimersByTimeAsync(VOICE_MAX_MS - 1);
      expect(onAutoStop).not.toHaveBeenCalled();
      await vi.advanceTimersByTimeAsync(1);
      await recorder.stop();
      expect(onAutoStop).toHaveBeenCalledTimes(1);
    });

    it("không có onAutoStop thì vẫn tự dừng được", async () => {
      const recorder = new VoiceRecorder({ maxMs: 50 });
      await recorder.start();
      await vi.advanceTimersByTimeAsync(50);
      expect(env.contexts[0].close).toHaveBeenCalled();
    });
  });

  describe("cancel", () => {
    it("dừng track, đóng context và hủy hẹn giờ", async () => {
      const onAutoStop = vi.fn();
      const recorder = new VoiceRecorder({ maxMs: 100, onAutoStop });
      await recorder.start();
      FakeNode.instances[0].emit(new Float32Array([0.9]));
      recorder.cancel();
      for (const track of env.tracks) expect(track.stop).toHaveBeenCalledTimes(1);
      expect(env.contexts[0].close).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1000);
      expect(onAutoStop).not.toHaveBeenCalled();
    });

    it("sau cancel, stop() trả WAV rỗng (bỏ dữ liệu đã thu)", async () => {
      const recorder = new VoiceRecorder();
      await recorder.start();
      FakeNode.instances[0].emit(new Float32Array([0.9, 0.9]));
      recorder.cancel();
      const blob = await recorder.stop();
      expect(blob.size).toBe(44);
    });

    it("cancel trước start không ném lỗi và đóng context", () => {
      const recorder = new VoiceRecorder();
      expect(() => recorder.cancel()).not.toThrow();
      expect(env.contexts[0].close).toHaveBeenCalledTimes(1);
    });
  });
});
