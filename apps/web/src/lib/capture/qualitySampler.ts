// Lấy mẫu một khung video cho cổng chất lượng: dò mặt (MediaPipe) và đọc điểm ảnh vùng mặt.
// Chỉ chạy trên trình duyệt. KHÔNG giữ ảnh: canvas chỉ là bộ đệm tạm, kết quả là số liệu (quality.ts).
// Tách riêng khỏi sampler của trang thử ChromaPulse (chromapulse/sampler.ts) để không đụng định dạng JSON của lab.

import type { FaceLandmarker } from "@mediapipe/tasks-vision";

import type { Point } from "./chromapulse/regions";
import { faceBox } from "./chromapulse/regions";
import { type FrameAnalysisInput, type PixelCrop, cropRectForFace } from "./quality";

/** Chiều rộng canvas đệm; đủ cho đo độ nét/độ sáng và nhẹ cho điện thoại. */
const SAMPLE_WIDTH = 480;

export type QualitySampler = {
  /** Đo một khung. Trả null khi video chưa có khung (videoWidth = 0): bỏ qua, không tạo NaN. */
  sample: (video: HTMLVideoElement) => Omit<FrameAnalysisInput, "prevFace"> | null;
};

export function createQualitySampler(landmarker: FaceLandmarker): QualitySampler {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true, colorSpace: "srgb" });
  if (!ctx) throw new Error("Không tạo được canvas 2D");
  let lastTimestamp = 0;

  return {
    sample(video) {
      if (!video.videoWidth || !video.videoHeight) return null;
      const width = SAMPLE_WIDTH;
      const height = Math.max(1, Math.round((video.videoHeight * SAMPLE_WIDTH) / video.videoWidth));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      ctx.drawImage(video, 0, 0, width, height);

      // MediaPipe cần mốc thời gian tăng chặt.
      lastTimestamp = Math.max(lastTimestamp + 1, performance.now());
      const result = landmarker.detectForVideo(video, lastTimestamp);
      const faces = result.faceLandmarks;
      const landmarks: readonly Point[] | null = faces[0] ?? null;
      const frame = { width, height };

      let crop: PixelCrop | null = null;
      if (landmarks) {
        const rect = cropRectForFace(faceBox(landmarks, width, height), frame);
        if (rect) {
          const image = ctx.getImageData(rect.x, rect.y, rect.w, rect.h);
          crop = { data: image.data, width: rect.w, height: rect.h };
        }
      }
      return { faceCount: faces.length, landmarks, frame, crop };
    },
  };
}
