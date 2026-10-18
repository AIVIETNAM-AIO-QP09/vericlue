// Giai đoạn chụp ảnh + quay clip 3 giây trên màn hình TRUNG TÍNH, xong rồi mới được nháy màu.
// Lý do (quyết định trưởng nhóm, duyệt PR #29): bộ phát hiện deepfake khuôn mặt ưu tiên đọc video, nên
// video không được quay lúc màn hình đang đổi màu (mặt bị ám màu). Logic tách khỏi UI để test thứ tự.

import { type Size, type VideoClip, captureJpeg, fitWithin, startVideoClip } from "./media";

export type NeutralCapture = {
  image: Blob;
  /** Video webm; null nếu trình duyệt không ghi được (trường tùy chọn). */
  clip: Blob | null;
  /** Kích thước ảnh thật đã gửi (sau khi thu nhỏ). */
  imageSize: Size;
  /** Kích thước khung camera gốc lúc chụp. */
  sourceSize: Size;
};

export type NeutralCaptureOptions = {
  video: HTMLVideoElement;
  stream: MediaStream | null;
  /** Hủy (bấm Dừng, rời trang): dừng clip ngay và trả null. */
  signal?: AbortSignal;
  captureImage?: (video: HTMLVideoElement) => Promise<Blob>;
  startClip?: (stream: MediaStream) => VideoClip;
};

/**
 * Chụp ảnh, rồi quay clip và CHỜ clip xong. Trả null nếu bị hủy giữa chừng.
 * Ném lỗi nếu không chụp được ảnh.
 */
export async function captureNeutralMedia(
  options: NeutralCaptureOptions,
): Promise<NeutralCapture | null> {
  const { video, stream, signal } = options;
  const captureImage = options.captureImage ?? captureJpeg;
  const startClip = options.startClip ?? ((s: MediaStream) => startVideoClip(s));
  if (signal?.aborted) return null;

  const sourceSize = { width: video.videoWidth, height: video.videoHeight };
  const image = await captureImage(video);
  if (signal?.aborted) return null;

  const clip = stream ? startClip(stream) : null;
  const onAbort = () => clip?.stop();
  signal?.addEventListener("abort", onAbort, { once: true });
  try {
    const blob = clip ? await clip.done : null;
    if (signal?.aborted) return null;
    return {
      image,
      clip: blob,
      imageSize: fitWithin(sourceSize.width, sourceSize.height),
      sourceSize,
    };
  } finally {
    signal?.removeEventListener("abort", onAbort);
  }
}

/**
 * Chạy `flash` CHỈ SAU khi `capture` xong. Nếu `capture` trả null (bị hủy) thì không nháy màu.
 * Đây là hợp đồng thứ tự mà test kiểm: ảnh → clip xong → mới nháy.
 */
export async function captureThenFlash<C, T>(steps: {
  capture: () => Promise<C | null>;
  flash: (captured: C) => Promise<T>;
}): Promise<{ captured: C; flash: T } | null> {
  const captured = await steps.capture();
  if (captured === null) return null;
  return { captured, flash: await steps.flash(captured) };
}
