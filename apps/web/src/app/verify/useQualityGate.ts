"use client";

// Vòng đo chất lượng khi xem trước camera (requestVideoFrameCallback).
// Hai pha để không báo oan "thiết bị chưa đáp ứng":
//  1) ĐO FPS trước, CHƯA chạy dò mặt (dò mặt chặn luồng chính nên làm FPS trông thấp): bỏ qua vài khung
//     khởi động, đo theo cửa sổ, chỉ báo thấp khi thấp LIÊN TIẾP nhiều cửa sổ (quality.ts: evaluateFpsWindows);
//  2) sau đó mới đo nặng (dò mặt, độ nét, độ sáng) cách nhau ~SAMPLE_INTERVAL_MS để máy yếu không bị kéo chậm.
// Kết quả đã phân loại gửi ra qua callback; hook KHÔNG tự quyết "đạt": máy trạng thái (flow.ts) quyết định.
// Lỗi (tải mô hình hỏng, thiếu rVFC, đo lỗi, video đứng) không bao giờ thành "đạt".

import { useEffect, useRef } from "react";

import type { Rect } from "@/lib/capture/chromapulse/regions";
import { createLandmarker, type LandmarkerHandle } from "@/lib/capture/chromapulse/landmarker";
import { supportsFrameCallback } from "@/lib/capture/chromapulse/trial";
import type { UnsupportedReason } from "@/lib/capture/flow";
import {
  FPS_WARMUP_CALLBACKS,
  FPS_WINDOW,
  type QualityGuidance,
  analyzeFrame,
  estimateFps,
  evaluateFpsWindows,
  isResolutionTooLow,
  pickGuidance,
} from "@/lib/capture/quality";
import { createQualitySampler } from "@/lib/capture/qualitySampler";

/** TẠM — chỉnh khi thử máy thật. Khoảng cách tối thiểu giữa hai lần đo nặng (ms). */
const SAMPLE_INTERVAL_MS = 120;
/** TẠM — chỉnh khi thử máy thật. Không có khung hình nào trong chừng này thời gian thì coi là camera đứng (lỗi). */
const FIRST_FRAME_TIMEOUT_MS = 10_000;

export type QualityGateCallbacks = {
  /** Kết quả của MỘT lần đo (null = khung đạt). */
  onGuidance: (guidance: QualityGuidance | null) => void;
  /** Camera/trình duyệt chưa đáp ứng: FPS thấp, độ phân giải thấp, thiếu requestVideoFrameCallback. */
  onUnsupported: (reason: UnsupportedReason) => void;
  /** Không đo được (tải mô hình hỏng, lỗi lấy mẫu, camera đứng): báo lỗi, không cho qua cổng. */
  onFailure: () => void;
};

type Options = {
  /** Chỉ chạy khi true (đúng bước đặt mặt). */
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
    let watchdog: ReturnType<typeof setTimeout> | null = null;
    let removePlayingListener: (() => void) | null = null;

    const cleanup = () => {
      cancelled = true;
      if (watchdog) clearTimeout(watchdog);
      watchdog = null;
      removePlayingListener?.();
      if (callbackId && typeof video.cancelVideoFrameCallback === "function") {
        video.cancelVideoFrameCallback(callbackId);
      }
      handle?.landmarker.close();
      handle = null;
    };
    const fail = () => {
      if (!cancelled) callbacksRef.current.onFailure();
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
        fail();
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
        fail();
        return;
      }

      let callbacksSeen = 0;

      // Camera đứng (rVFC không bao giờ bắn): báo lỗi thay vì chờ mãi. Đồng hồ chỉ bắt đầu khi video đã có
      // luồng và đang phát (nếu không, thời gian xin quyền camera hay tải mô hình bị tính nhầm là "đứng").
      const startWatchdog = () => {
        if (cancelled || watchdog || callbacksSeen > 0) return;
        watchdog = setTimeout(fail, FIRST_FRAME_TIMEOUT_MS);
      };
      const isPlaying = () => video.srcObject !== null && !video.paused && video.readyState >= 2;
      const onPlaying = () => startWatchdog();
      if (isPlaying()) startWatchdog();
      else video.addEventListener("playing", onPlaying, { once: true });
      removePlayingListener = () => video.removeEventListener("playing", onPlaying);

      let fpsTimes: number[] = [];
      const windowFps: (number | null)[] = [];
      let sampling = false;
      let prevFace: Rect | null = null;
      let lastSampleAt = Number.NEGATIVE_INFINITY;

      const loop = (now: number, metadata: VideoFrameCallbackMetadata) => {
        if (cancelled) return;
        if (watchdog) {
          clearTimeout(watchdog);
          watchdog = null;
        }
        callbacksSeen += 1;

        // Độ phân giải thật của khung (theo metadata, không tin cài đặt xin).
        if (isResolutionTooLow(metadata.width, metadata.height)) {
          callbacksRef.current.onUnsupported("low_resolution");
          return;
        }

        if (!sampling) {
          // Pha 1: đo FPS khi CHƯA có việc nặng. Bỏ qua các khung khởi động.
          if (callbacksSeen > FPS_WARMUP_CALLBACKS) {
            fpsTimes.push(now);
            if (fpsTimes.length >= FPS_WINDOW) {
              windowFps.push(estimateFps(fpsTimes));
              fpsTimes = [];
              const verdict = evaluateFpsWindows(windowFps);
              if (verdict === "low") {
                callbacksRef.current.onUnsupported("low_fps");
                return;
              }
              if (verdict === "ok") sampling = true;
            }
          }
        } else if (now - lastSampleAt >= SAMPLE_INTERVAL_MS) {
          // Pha 2: đo nặng.
          lastSampleAt = now;
          try {
            const raw = sampler.sample(video);
            if (raw) {
              const metrics = analyzeFrame({ ...raw, prevFace });
              prevFace = metrics.face;
              callbacksRef.current.onGuidance(pickGuidance(metrics));
            }
          } catch {
            fail();
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
