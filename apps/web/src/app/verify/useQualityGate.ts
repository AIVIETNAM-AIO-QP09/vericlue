"use client";

// Vòng đo chất lượng khi xem trước camera. Mỗi khung video (requestVideoFrameCallback) ghi nhận FPS và độ
// phân giải; cứ ~SAMPLE_INTERVAL_MS mới đo nặng (dò mặt, độ nét, độ sáng) để máy yếu không bị kéo chậm.
// Kết quả đã phân loại gửi ra qua callback; hook KHÔNG tự quyết "đạt": máy trạng thái (flow.ts) quyết định.
// Lỗi (tải mô hình hỏng, thiếu rVFC, đo lỗi) không bao giờ thành "đạt".

import { useEffect, useRef } from "react";

import { createLandmarker, type LandmarkerHandle } from "@/lib/capture/chromapulse/landmarker";
import { supportsFrameCallback } from "@/lib/capture/chromapulse/trial";
import type { UnsupportedReason } from "@/lib/capture/flow";
import {
  FPS_WINDOW,
  type QualityGuidance,
  analyzeFrame,
  estimateFps,
  isFpsTooLow,
  isResolutionTooLow,
  pickGuidance,
} from "@/lib/capture/quality";
import { createQualitySampler } from "@/lib/capture/qualitySampler";
import type { Rect } from "@/lib/capture/chromapulse/regions";

/** TẠM — chỉnh khi thử máy thật. Khoảng cách tối thiểu giữa hai lần đo nặng (ms). */
const SAMPLE_INTERVAL_MS = 120;
/** Số lần gọi khung hình cần có trước khi kết luận về FPS. */
const FPS_DECISION_SAMPLES = FPS_WINDOW;

export type QualityGateCallbacks = {
  /** Kết quả của MỘT lần đo (null = khung đạt). */
  onGuidance: (guidance: QualityGuidance | null) => void;
  /** Camera/trình duyệt chưa đáp ứng: FPS thấp, độ phân giải thấp, thiếu requestVideoFrameCallback. */
  onUnsupported: (reason: UnsupportedReason) => void;
  /** Không đo được (tải mô hình hỏng, lỗi lấy mẫu): báo lỗi, không cho qua cổng. */
  onFailure: () => void;
  /** Số khung đo được mỗi giây (để hiển thị tuỳ chọn, hiện không dùng). */
  onFps?: (fps: number) => void;
};

type Options = {
  /** Chỉ chạy khi true (đúng bước đặt mặt) và video đã có luồng. */
  active: boolean;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  callbacks: QualityGateCallbacks;
};

export function useQualityGate({ active, videoRef, callbacks }: Options) {
  // Giữ callback mới nhất trong ref để effect không khởi động lại mỗi lần render.
  const callbacksRef = useRef(callbacks);
  useEffect(() => {
    callbacksRef.current = callbacks;
  }, [callbacks]);

  useEffect(() => {
    if (!active) return;
    const video = videoRef.current;
    if (!video) return;

    let cancelled = false;
    let handle: LandmarkerHandle | null = null;
    let callbackId = 0;

    const cleanup = () => {
      cancelled = true;
      if (callbackId && typeof video.cancelVideoFrameCallback === "function") {
        video.cancelVideoFrameCallback(callbackId);
      }
      handle?.landmarker.close();
      handle = null;
    };

    void (async () => {
      // Không đo được FPS thì không có cổng: báo thiết bị chưa đáp ứng, không phải "đạt".
      if (!supportsFrameCallback(video)) {
        callbacksRef.current.onUnsupported("no_frame_callback");
        return;
      }
      try {
        handle = await createLandmarker({ numFaces: 2 });
      } catch {
        if (!cancelled) callbacksRef.current.onFailure();
        return;
      }
      if (cancelled) {
        handle.landmarker.close();
        handle = null;
        return;
      }

      let sampler: ReturnType<typeof createQualitySampler>;
      try {
        sampler = createQualitySampler(handle.landmarker);
      } catch {
        callbacksRef.current.onFailure();
        return;
      }

      const times: number[] = [];
      let prevFace: Rect | null = null;
      let lastSampleAt = Number.NEGATIVE_INFINITY;
      let fpsDecided = false;

      const loop = (now: number, metadata: VideoFrameCallbackMetadata) => {
        if (cancelled) return;
        times.push(now);
        if (times.length > FPS_WINDOW) times.shift();

        // Độ phân giải thật của khung (theo metadata, không tin cài đặt xin).
        if (isResolutionTooLow(metadata.width, metadata.height)) {
          callbacksRef.current.onUnsupported("low_resolution");
          return;
        }
        // Quyết định về FPS một lần, khi đã đủ mẫu; sau đó chỉ theo dõi nếu tụt nặng.
        if (!fpsDecided && times.length >= FPS_DECISION_SAMPLES) {
          fpsDecided = true;
          const fps = estimateFps(times);
          if (fps !== null) callbacksRef.current.onFps?.(fps);
          if (isFpsTooLow(fps)) {
            callbacksRef.current.onUnsupported("low_fps");
            return;
          }
        }

        if (now - lastSampleAt >= SAMPLE_INTERVAL_MS) {
          lastSampleAt = now;
          try {
            const raw = sampler.sample(video);
            if (raw) {
              const metrics = analyzeFrame({ ...raw, prevFace });
              prevFace = metrics.face;
              callbacksRef.current.onGuidance(pickGuidance(metrics));
            }
          } catch {
            callbacksRef.current.onFailure();
            return;
          }
        }
        callbackId = video.requestVideoFrameCallback(loop);
      };
      callbackId = video.requestVideoFrameCallback(loop);
    })();

    // Rời trang (kể cả khi trang vào bộ nhớ đệm mà không gỡ component): đóng mô hình và dừng đo ngay.
    window.addEventListener("pagehide", cleanup);
    return () => {
      window.removeEventListener("pagehide", cleanup);
      cleanup();
    };
  }, [active, videoRef]);
}
