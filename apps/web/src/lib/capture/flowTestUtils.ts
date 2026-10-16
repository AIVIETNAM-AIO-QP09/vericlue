// Trợ giúp cho test: dựng chuỗi sự kiện đi qua cổng chất lượng (không dùng trong mã chạy thật).

import type { FlowEvent } from "./flow";
import { QUALITY_REQUIRED_FRAMES } from "./quality";

/**
 * Đủ `QUALITY_REQUIRED_FRAMES` khung đạt LIÊN TIẾP; khung cuối mang mã lần chạy `run`
 * (đúng như VerifyFlow làm khi `qualityWouldPass`).
 */
export function qualityGateEvents(run = 0): FlowEvent[] {
  return Array.from({ length: QUALITY_REQUIRED_FRAMES }, (_, i) => ({
    type: "QUALITY_FRAME",
    guidance: null,
    ...(i === QUALITY_REQUIRED_FRAMES - 1 ? { run } : {}),
  }));
}
