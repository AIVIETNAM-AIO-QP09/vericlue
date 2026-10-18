// Mã hóa WAV PCM 16-bit mono 16 kHz ngay trên trình duyệt (CAP-07). Không gửi webm/opus cho âm thanh:
// bộ phát hiện giọng giả đọc WAV. Mọi hàm ở đây là hàm thuần (trừ resample16k, dùng OfflineAudioContext).

/** Tần số lấy mẫu gửi đi (Hz). */
export const WAV_SAMPLE_RATE = 16000;

/** Ghép các đoạn PCM float thành một mảng. */
export function concatChunks(chunks: readonly Float32Array[]): Float32Array {
  const out = new Float32Array(chunks.reduce((total, chunk) => total + chunk.length, 0));
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}

/** WAV PCM 16-bit little-endian, 1 kênh, header RIFF 44 byte. Mẫu ngoài [-1, 1] bị cắt. */
export function encodeWav(pcm: Float32Array, sampleRate: number = WAV_SAMPLE_RATE): Blob {
  const dataBytes = pcm.length * 2;
  const buffer = new ArrayBuffer(44 + dataBytes);
  const view = new DataView(buffer);
  const writeText = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
  };
  writeText(0, "RIFF");
  view.setUint32(4, 36 + dataBytes, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true); // kích thước khối fmt
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte/giây
  view.setUint16(32, 2, true); // byte/mẫu
  view.setUint16(34, 16, true); // bit/mẫu
  writeText(36, "data");
  view.setUint32(40, dataBytes, true);
  for (let i = 0; i < pcm.length; i += 1) {
    const x = Math.max(-1, Math.min(1, pcm[i]));
    view.setInt16(44 + i * 2, Math.round(x * (x < 0 ? 32768 : 32767)), true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

/**
 * Hạ tần số lấy mẫu bằng trung bình theo diện tích (tương đương lọc hộp rồi lấy mẫu thưa).
 * Xác định, không phụ thuộc trình duyệt; dùng làm dự phòng khi OfflineAudioContext lỗi.
 */
export function boxResample(
  input: Float32Array,
  fromRate: number,
  toRate: number = WAV_SAMPLE_RATE,
): Float32Array {
  if (fromRate === toRate) return input;
  const ratio = fromRate / toRate;
  const out = new Float32Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i += 1) {
    const start = i * ratio;
    const end = start + ratio;
    let sum = 0;
    for (let j = Math.floor(start); j < Math.min(Math.ceil(end), input.length); j += 1) {
      sum += input[j] * (Math.min(j + 1, end) - Math.max(j, start));
    }
    out[i] = sum / ratio;
  }
  return out;
}

/** Đưa PCM về 16 kHz: OfflineAudioContext (chất lượng tốt), lỗi thì dùng boxResample. */
export async function resample16k(input: Float32Array, fromRate: number): Promise<Float32Array> {
  if (fromRate === WAV_SAMPLE_RATE || input.length === 0) return input;
  try {
    const offline = new OfflineAudioContext(
      1,
      Math.ceil((input.length * WAV_SAMPLE_RATE) / fromRate),
      WAV_SAMPLE_RATE,
    );
    const buffer = offline.createBuffer(1, input.length, fromRate);
    buffer.copyToChannel(new Float32Array(input), 0);
    const source = offline.createBufferSource();
    source.buffer = buffer;
    source.connect(offline.destination);
    source.start();
    const rendered = await offline.startRendering();
    return rendered.getChannelData(0);
  } catch {
    return boxResample(input, fromRate);
  }
}
