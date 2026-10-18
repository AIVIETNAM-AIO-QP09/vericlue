// Ghi âm giọng đọc câu thử thách → WAV 16 kHz mono (CAP-07). AudioWorklet thu ở tần số gốc của
// AudioContext rồi hạ xuống 16 kHz (wav.ts). Không dùng MediaRecorder cho âm thanh.

import { concatChunks, encodeWav, resample16k } from "./wav";

/** Tối đa ~8 giây mỗi lần đọc; hết giờ thì tự dừng. */
export const VOICE_MAX_MS = 8000;
/** Tắt xử lý của trình duyệt: khử ồn/AGC có thể xóa hoặc tạo dấu vết mà bộ phát hiện giả mạo dựa vào. */
export const VOICE_CONSTRAINTS: MediaTrackConstraints = {
  channelCount: 1,
  echoCancellation: false,
  noiseSuppression: false,
  autoGainControl: false,
};
const WORKLET_URL = "/pcm-recorder.worklet.js";

type AudioContextConstructor = typeof AudioContext;

export class VoiceRecorder {
  private readonly context: AudioContext;
  private readonly chunks: Float32Array[] = [];
  private stream: MediaStream | null = null;
  private node: AudioWorkletNode | null = null;
  private sink: GainNode | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private result: Promise<Blob> | null = null;

  /**
   * PHẢI tạo đồng bộ trong trình xử lý bấm nút (trước mọi await): iOS chỉ cho AudioContext chạy
   * khi nằm trong thao tác của người dùng.
   */
  constructor(private readonly options: { maxMs?: number; onAutoStop?: () => void } = {}) {
    const Ctor: AudioContextConstructor | undefined =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: AudioContextConstructor }).webkitAudioContext;
    if (!Ctor) throw new Error("Trình duyệt không hỗ trợ ghi âm");
    this.context = new Ctor();
    void this.context.resume();
  }

  /** Xin micro và bắt đầu thu. Ném lỗi (NotAllowedError...) nếu không được; đã dọn dẹp trước khi ném. */
  async start(): Promise<void> {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: VOICE_CONSTRAINTS,
        video: false,
      });
      // Sau lời nhắc cấp quyền micro, trình duyệt (iOS) có thể để context ở trạng thái suspended.
      await this.context.resume();
      await this.context.audioWorklet.addModule(WORKLET_URL);
      const node = new AudioWorkletNode(this.context, "pcm-recorder");
      node.port.onmessage = (event: MessageEvent<Float32Array>) => this.chunks.push(event.data);
      // Safari có thể không gọi process() nếu node không nối tới đích: nối qua Gain 0 (im lặng, không vọng loa).
      const sink = this.context.createGain();
      sink.gain.value = 0;
      node.connect(sink);
      sink.connect(this.context.destination);
      this.context.createMediaStreamSource(this.stream).connect(node);
      this.node = node;
      this.sink = sink;
    } catch (error) {
      this.release();
      throw error;
    }
    this.timer = setTimeout(() => {
      void this.stop().then(() => this.options.onAutoStop?.());
    }, this.options.maxMs ?? VOICE_MAX_MS);
  }

  /** Dừng và trả WAV 16 kHz. Gọi nhiều lần vẫn an toàn (nút Dừng và hẹn giờ cùng gọi). */
  stop(): Promise<Blob> {
    this.result ??= (async () => {
      const sampleRate = this.context.sampleRate;
      this.release();
      const pcm = await resample16k(concatChunks(this.chunks), sampleRate);
      return encodeWav(pcm);
    })();
    return this.result;
  }

  /** Hủy, bỏ dữ liệu (rời trang). */
  cancel(): void {
    this.result ??= Promise.resolve(encodeWav(new Float32Array(0)));
    this.release();
  }

  private release(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
    this.node?.disconnect();
    this.node = null;
    this.sink?.disconnect();
    this.sink = null;
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    if (this.context.state !== "closed") void this.context.close().catch(() => undefined);
  }
}
