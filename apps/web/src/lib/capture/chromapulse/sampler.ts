// Lấy mẫu màu từ một khung video: tìm khuôn mặt, đọc điểm ảnh từng vùng, tính trung vị.
// Chỉ chạy trên trình duyệt. Ảnh KHÔNG được giữ lại: canvas chỉ là bộ đệm tạm, kết quả là con số.

import type { FaceLandmarker } from "@mediapipe/tasks-vision";

import {
  REGION_NAMES,
  type Rect,
  type RegionName,
  type RegionStat,
  backgroundRects,
  faceBox,
  skinRegionRects,
  summarizePixels,
} from "./regions";

/** Chiều rộng canvas đệm; đủ cho vùng da và đỡ tốn CPU trên điện thoại. */
const SAMPLE_WIDTH = 480;

export type FrameSample = {
  faceFound: boolean;
  regions: Partial<Record<RegionName, RegionStat>> | null;
  /** Hộp vùng theo toạ độ canvas đệm (để vẽ lớp phủ kiểm tra); không lưu vào JSON. */
  rects: Partial<Record<RegionName, Rect[]>>;
  canvasWidth: number;
  canvasHeight: number;
};

export type FrameSampler = {
  /** null khi video chưa có khung (videoWidth = 0): bỏ qua, không tạo NaN. */
  sample: (video: HTMLVideoElement) => FrameSample | null;
};

export function createFrameSampler(landmarker: FaceLandmarker): FrameSampler {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true, colorSpace: "srgb" });
  if (!ctx) throw new Error("Không tạo được canvas 2D");
  let lastTimestamp = 0;

  return {
    sample(video) {
      if (!video.videoWidth || !video.videoHeight) return null;
      const scale = SAMPLE_WIDTH / video.videoWidth;
      const width = SAMPLE_WIDTH;
      const height = Math.max(1, Math.round(video.videoHeight * scale));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      ctx.drawImage(video, 0, 0, width, height);

      // MediaPipe cần mốc thời gian tăng chặt.
      lastTimestamp = Math.max(lastTimestamp + 1, performance.now());
      const result = landmarker.detectForVideo(video, lastTimestamp);
      const landmarks = result.faceLandmarks[0];
      const base = { canvasWidth: width, canvasHeight: height };

      if (!landmarks) {
        const bg = backgroundRects(null, width, height);
        return {
          ...base,
          faceFound: false,
          regions: { background: readRects(ctx, bg) },
          rects: { background: bg },
        };
      }

      const skin = skinRegionRects(landmarks, width, height);
      const bgRects = backgroundRects(faceBox(landmarks, width, height), width, height);
      const regions: Partial<Record<RegionName, RegionStat>> = {};
      const rects: Partial<Record<RegionName, Rect[]>> = {};
      for (const name of REGION_NAMES) {
        const list = name === "background" ? bgRects : skin[name] ? [skin[name]] : [];
        rects[name] = list;
        regions[name] = readRects(ctx, list);
      }
      return { ...base, faceFound: true, regions, rects };
    },
  };
}

function readRects(ctx: CanvasRenderingContext2D, rects: readonly Rect[]): RegionStat {
  const buffers = rects.map((r) => ctx.getImageData(r.x, r.y, r.w, r.h).data);
  return summarizePixels(buffers);
}
