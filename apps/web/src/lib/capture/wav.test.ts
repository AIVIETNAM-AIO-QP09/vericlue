import { afterEach, describe, expect, it, vi } from "vitest";

import { WAV_SAMPLE_RATE, boxResample, concatChunks, encodeWav, resample16k } from "./wav";

async function readWav(blob: Blob): Promise<DataView> {
  return new DataView(await blob.arrayBuffer());
}

function ascii(view: DataView, offset: number, length: number): string {
  let text = "";
  for (let i = 0; i < length; i += 1) text += String.fromCharCode(view.getUint8(offset + i));
  return text;
}

describe("concatChunks", () => {
  it("ghép các đoạn theo thứ tự", () => {
    const out = concatChunks([
      new Float32Array([1, 2]),
      new Float32Array([3]),
      new Float32Array([4, 5]),
    ]);
    expect(Array.from(out)).toEqual([1, 2, 3, 4, 5]);
  });

  it("danh sách rỗng cho mảng rỗng", () => {
    expect(concatChunks([]).length).toBe(0);
  });

  it("bỏ qua đoạn rỗng", () => {
    const out = concatChunks([new Float32Array(0), new Float32Array([7]), new Float32Array(0)]);
    expect(Array.from(out)).toEqual([7]);
  });
});

describe("encodeWav", () => {
  it("header RIFF/WAVE PCM mono 16 kHz 16-bit, tổng 44 + 2n byte", async () => {
    const pcm = new Float32Array([0, 0.5, -0.5, 0.25]);
    const blob = encodeWav(pcm);
    expect(blob.type).toBe("audio/wav");
    expect(blob.size).toBe(44 + pcm.length * 2);

    const view = await readWav(blob);
    expect(ascii(view, 0, 4)).toBe("RIFF");
    expect(view.getUint32(4, true)).toBe(36 + pcm.length * 2);
    expect(ascii(view, 8, 4)).toBe("WAVE");
    expect(ascii(view, 12, 4)).toBe("fmt ");
    expect(view.getUint32(16, true)).toBe(16);
    expect(view.getUint16(20, true)).toBe(1); // PCM
    expect(view.getUint16(22, true)).toBe(1); // mono
    expect(view.getUint32(24, true)).toBe(16000);
    expect(view.getUint32(28, true)).toBe(32000); // byteRate
    expect(view.getUint16(32, true)).toBe(2); // block align
    expect(view.getUint16(34, true)).toBe(16);
    expect(ascii(view, 36, 4)).toBe("data");
    expect(view.getUint32(40, true)).toBe(pcm.length * 2);
  });

  it("dùng sampleRate truyền vào cho header", async () => {
    const view = await readWav(encodeWav(new Float32Array(2), 8000));
    expect(view.getUint32(24, true)).toBe(8000);
    expect(view.getUint32(28, true)).toBe(16000);
  });

  it("+1 → 32767, -1 → -32768, 0 → 0", async () => {
    const view = await readWav(encodeWav(new Float32Array([1, -1, 0])));
    expect(view.getInt16(44, true)).toBe(32767);
    expect(view.getInt16(46, true)).toBe(-32768);
    expect(view.getInt16(48, true)).toBe(0);
  });

  it("mẫu ngoài [-1, 1] bị cắt", async () => {
    const view = await readWav(encodeWav(new Float32Array([2.5, -3, 1.0001, -1.5])));
    expect(view.getInt16(44, true)).toBe(32767);
    expect(view.getInt16(46, true)).toBe(-32768);
    expect(view.getInt16(48, true)).toBe(32767);
    expect(view.getInt16(50, true)).toBe(-32768);
  });

  it("giá trị giữa được làm tròn đúng", async () => {
    const view = await readWav(encodeWav(new Float32Array([0.5, -0.5])));
    expect(view.getInt16(44, true)).toBe(Math.round(0.5 * 32767));
    expect(view.getInt16(46, true)).toBe(-16384);
  });

  it("mảng rỗng cho WAV 44 byte hợp lệ", async () => {
    const blob = encodeWav(new Float32Array(0));
    expect(blob.size).toBe(44);
    const view = await readWav(blob);
    expect(ascii(view, 0, 4)).toBe("RIFF");
    expect(view.getUint32(4, true)).toBe(36);
    expect(view.getUint32(40, true)).toBe(0);
  });
});

describe("boxResample", () => {
  it("48000 → 16000 cho đúng 16000 mẫu từ 48000 mẫu", () => {
    expect(boxResample(new Float32Array(48000), 48000).length).toBe(16000);
  });

  it("44100 → 16000 cho đúng 16000 mẫu từ 44100 mẫu", () => {
    expect(boxResample(new Float32Array(44100), 44100).length).toBe(16000);
  });

  it("cùng tần số thì trả nguyên mảng đầu vào", () => {
    const input = new Float32Array([0.1, 0.2, 0.3]);
    expect(boxResample(input, 16000)).toBe(input);
  });

  it("tham số toRate tùy chỉnh", () => {
    expect(boxResample(new Float32Array(1000), 8000, 4000).length).toBe(500);
  });

  it("hằng số 0.5 vẫn là 0.5 (kể cả tỉ lệ lẻ 44100)", () => {
    for (const rate of [48000, 44100]) {
      const out = boxResample(new Float32Array(rate).fill(0.5), rate);
      expect(out.length).toBe(16000);
      for (const value of [out[0], out[1], out[8000], out[15999]]) {
        expect(value).toBeCloseTo(0.5, 4);
      }
    }
  });

  it("sin thấp tần (100 Hz) giữ biên độ", () => {
    const rate = 48000;
    const input = new Float32Array(rate);
    for (let i = 0; i < rate; i += 1) input[i] = Math.sin((2 * Math.PI * 100 * i) / rate);
    const out = boxResample(input, rate);
    let peak = 0;
    for (const value of out) peak = Math.max(peak, Math.abs(value));
    expect(peak).toBeGreaterThan(0.99);
    expect(peak).toBeLessThanOrEqual(1.0001);
    // So khớp với sin lý tưởng tại một điểm mẫu.
    const k = 40;
    expect(out[k]).toBeCloseTo(Math.sin((2 * Math.PI * 100 * (k + 0.5)) / 16000), 2);
  });

  it("đầu vào rỗng cho đầu ra rỗng", () => {
    expect(boxResample(new Float32Array(0), 48000).length).toBe(0);
  });
});

describe("resample16k", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("cùng tần số 16 kHz trả nguyên mảng", async () => {
    const input = new Float32Array([0.1, 0.2]);
    expect(await resample16k(input, WAV_SAMPLE_RATE)).toBe(input);
  });

  it("đầu vào rỗng trả nguyên mảng", async () => {
    const input = new Float32Array(0);
    expect(await resample16k(input, 48000)).toBe(input);
  });

  it("không có OfflineAudioContext thì rơi về boxResample", async () => {
    vi.stubGlobal("OfflineAudioContext", undefined);
    const out = await resample16k(new Float32Array(48000).fill(0.25), 48000);
    expect(out.length).toBe(16000);
    expect(out[100]).toBeCloseTo(0.25, 4);
  });

  it("OfflineAudioContext ném lỗi thì rơi về boxResample", async () => {
    class Broken {
      constructor() {
        throw new Error("không hỗ trợ");
      }
    }
    vi.stubGlobal("OfflineAudioContext", Broken);
    const out = await resample16k(new Float32Array(44100), 44100);
    expect(out.length).toBe(16000);
  });

  it("có OfflineAudioContext thì dùng kết quả của nó", async () => {
    const rendered = new Float32Array([0.9, 0.8, 0.7]);
    const created: { args: unknown[] }[] = [];
    const copied: Float32Array[] = [];
    class FakeOffline {
      destination = {};
      constructor(...args: unknown[]) {
        created.push({ args });
      }
      createBuffer(channels: number, length: number, rate: number) {
        expect([channels, length, rate]).toEqual([1, 48000, 48000]);
        return {
          copyToChannel: (data: Float32Array) => copied.push(data),
        };
      }
      createBufferSource() {
        return { buffer: null, connect: vi.fn(), start: vi.fn() };
      }
      async startRendering() {
        return { getChannelData: () => rendered };
      }
    }
    vi.stubGlobal("OfflineAudioContext", FakeOffline);

    const out = await resample16k(new Float32Array(48000).fill(0.5), 48000);
    expect(out).toBe(rendered);
    expect(created[0].args).toEqual([1, 16000, 16000]);
    expect(copied[0].length).toBe(48000);
  });
});
