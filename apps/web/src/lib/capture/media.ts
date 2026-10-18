// Chụp ảnh và ghi đoạn video ngắn từ camera thật (CAP-06). Logic thuần trình duyệt, không đụng giao diện.
// MediaRecorder CHỈ để lưu video gửi đi, không dùng để đo thời gian (xem apps/web/AGENTS.md).

/** Cạnh dài tối đa của ảnh gửi đi (px). Camera 720p/1080p được thu nhỏ, giữ tỉ lệ. */
export const IMAGE_MAX_EDGE = 1280;
/** Chất lượng JPEG (ADR-0012: ≈ 0,9). */
export const IMAGE_JPEG_QUALITY = 0.9;
/** Độ dài đoạn video gửi cho bộ phát hiện deepfake khuôn mặt (ms). */
export const VIDEO_CLIP_MS = 3000;
/** Bitrate video. Đoạn 3 giây giữ dưới vài MB để mạng di động gửi kịp. */
export const VIDEO_BITS_PER_SECOND = 2_500_000;

/** Sau khi gọi stop(), nếu sự kiện "stop" không bắn trong ngần này (ms) thì bỏ video, không treo luồng. */
export const VIDEO_STOP_GRACE_MS = 3000;

/** Thứ tự ưu tiên; API đọc webm bằng cv2. Safari cũ không có webm: bỏ qua video (trường tùy chọn). */
const VIDEO_MIME_CANDIDATES = ["video/webm;codecs=vp8", "video/webm;codecs=vp9", "video/webm"];

export type Size = { width: number; height: number };

/** Thu nhỏ vừa khung `maxEdge` theo cạnh dài, giữ tỉ lệ; không phóng to. */
export function fitWithin(width: number, height: number, maxEdge: number = IMAGE_MAX_EDGE): Size {
  const longest = Math.max(width, height);
  if (!(longest > maxEdge)) return { width, height };
  const scale = maxEdge / longest;
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

/** Chụp khung hiện tại của <video> thành JPEG (cạnh dài ≤ IMAGE_MAX_EDGE). Ném lỗi nếu chưa có khung. */
export async function captureJpeg(video: HTMLVideoElement): Promise<Blob> {
  const sourceWidth = video.videoWidth;
  const sourceHeight = video.videoHeight;
  if (!(sourceWidth > 0 && sourceHeight > 0)) throw new Error("Chưa có khung hình từ camera");
  const { width, height } = fitWithin(sourceWidth, sourceHeight);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Không tạo được canvas");
  context.drawImage(video, 0, 0, width, height);
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("Không mã hóa được ảnh"))),
      "image/jpeg",
      IMAGE_JPEG_QUALITY,
    );
  });
}

/** Định dạng webm đầu tiên trình duyệt ghi được, hoặc null (không có MediaRecorder/webm). */
export function pickVideoMimeType(
  isTypeSupported: ((type: string) => boolean) | undefined = typeof MediaRecorder === "undefined"
    ? undefined
    : (type) => MediaRecorder.isTypeSupported(type),
): string | null {
  if (!isTypeSupported) return null;
  return VIDEO_MIME_CANDIDATES.find((type) => isTypeSupported(type)) ?? null;
}

export type VideoClip = {
  /** Blob webm khi ghi xong; null nếu không ghi được (video là trường tùy chọn, không làm hỏng phiên). */
  done: Promise<Blob | null>;
  /** Dừng sớm (rời trang, hủy). Vẫn trả phần đã ghi qua `done`. */
  stop: () => void;
};

/** Ghi `durationMs` video (không âm thanh) từ các track hình của `stream`. */
export function startVideoClip(
  stream: MediaStream,
  options: { durationMs?: number; mimeType?: string | null } = {},
): VideoClip {
  const durationMs = options.durationMs ?? VIDEO_CLIP_MS;
  const mimeType = options.mimeType === undefined ? pickVideoMimeType() : options.mimeType;
  const videoTracks = stream.getVideoTracks();
  if (!mimeType || videoTracks.length === 0 || typeof MediaRecorder === "undefined") {
    return { done: Promise.resolve(null), stop: () => undefined };
  }

  let recorder: MediaRecorder;
  try {
    recorder = new MediaRecorder(new MediaStream(videoTracks), {
      mimeType,
      videoBitsPerSecond: VIDEO_BITS_PER_SECOND,
    });
  } catch {
    return { done: Promise.resolve(null), stop: () => undefined };
  }

  const chunks: Blob[] = [];
  let timer: ReturnType<typeof setTimeout> | null = null;
  let graceTimer: ReturnType<typeof setTimeout> | null = null;
  let finish: (blob: Blob | null) => void = () => undefined;
  const stop = () => {
    if (timer !== null) clearTimeout(timer);
    timer = null;
    if (recorder.state !== "inactive") {
      try {
        recorder.stop();
      } catch {
        /* đã dừng */
      }
      // Một số trình duyệt không bắn "stop": hết hạn thì trả null để người gọi (await done) không treo.
      graceTimer ??= setTimeout(() => finish(null), VIDEO_STOP_GRACE_MS);
    }
  };

  const done = new Promise<Blob | null>((resolve) => {
    finish = (blob) => {
      if (graceTimer !== null) clearTimeout(graceTimer);
      resolve(blob);
    };
    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) chunks.push(event.data);
    };
    recorder.onerror = () => {
      finish(null); // trước stop(): onstop bắn sau đó không được đổi kết quả
      stop();
    };
    recorder.onstop = () => {
      finish(chunks.length > 0 ? new Blob(chunks, { type: "video/webm" }) : null);
    };
  });

  try {
    recorder.start();
  } catch {
    return { done: Promise.resolve(null), stop: () => undefined };
  }
  timer = setTimeout(stop, durationMs);
  return { done, stop };
}
