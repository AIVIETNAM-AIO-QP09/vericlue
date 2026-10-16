"use client";

// Khung xem camera kèm oval hướng dẫn đặt mặt. Chỉ trình bày: logic đo nằm ở src/lib/capture/quality.ts.
// Video luôn nằm trong DOM (iOS Safari có thể ngừng cấp khung nếu video bị display:none khi đang chạy);
// khi chưa cần xem thì chỉ ẩn bằng class `hidden` ở bên ngoài các bước đang chạy.

import { useState } from "react";

import { vi } from "@/i18n/vi";
import { ovalRect } from "@/lib/capture/quality";

type CameraViewProps = {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  /** Hiện khung xem hay không. */
  visible: boolean;
  /** Vẽ oval hướng dẫn (bước đặt mặt). */
  showOval: boolean;
  /** Khung đạt: oval chuyển màu xanh. */
  ok: boolean;
};

/** Kích thước tham chiếu để dựng oval theo phần trăm; oval tính bằng cùng hàm với cổng chất lượng. */
const REFERENCE_WIDTH = 1000;
const DEFAULT_ASPECT = 3 / 4; // dọc, trước khi biết kích thước thật của video

export function CameraView({ videoRef, visible, showOval, ok }: CameraViewProps) {
  const [aspect, setAspect] = useState(DEFAULT_ASPECT);
  const height = REFERENCE_WIDTH / aspect;
  const oval = ovalRect(REFERENCE_WIDTH, height);

  return (
    <div className={visible ? "relative w-full max-w-md" : "hidden"}>
      <video
        ref={videoRef}
        playsInline
        muted
        onLoadedMetadata={(e) => {
          const { videoWidth, videoHeight } = e.currentTarget;
          if (videoWidth > 0 && videoHeight > 0) setAspect(videoWidth / videoHeight);
        }}
        // Lật gương cho tự nhiên; oval đối xứng nên không bị ảnh hưởng.
        className="block w-full -scale-x-100 rounded"
      />
      {showOval && (
        <svg
          role="img"
          aria-label={vi.verify.framing.ovalLabel}
          viewBox={`0 0 ${REFERENCE_WIDTH} ${height}`}
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-0 h-full w-full"
        >
          <ellipse
            cx={oval.x + oval.w / 2}
            cy={oval.y + oval.h / 2}
            rx={oval.w / 2}
            ry={oval.h / 2}
            fill="none"
            stroke={ok ? "#16a34a" : "#ffffff"}
            strokeWidth={6}
            strokeDasharray={ok ? undefined : "24 16"}
          />
        </svg>
      )}
    </div>
  );
}
