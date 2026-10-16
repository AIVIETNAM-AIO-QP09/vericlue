// Đổi trạng thái/lỗi của luồng thành chữ hiển thị (lấy từ src/i18n/vi.ts). Hàm thuần, có test quét chuỗi:
// không màn hình nào có điểm số hay chữ "giả mạo", và gợi ý chụp lại chỉ nói về chất lượng.

import { vi } from "@/i18n/vi";

import type { CameraProblem, ErrorKind, RetryHint, UnsupportedReason } from "./flow";
import type { QualityGuidance } from "./quality";

const v = vi.verify;

export function errorMessage(kind: ErrorKind): string {
  return v.errors[kind];
}

export function cameraMessage(problem: CameraProblem | null): string {
  if (problem === null) return v.camera.asking;
  return v.camera[problem];
}

/** Câu chỉ dẫn của cổng chất lượng; null (khung đạt) thì khen ngắn và giữ nguyên tư thế. */
export function qualityMessage(guidance: QualityGuidance | null): string {
  return guidance === null ? v.framing.allGood : v.quality[guidance];
}

/** Lý do thiết bị/trình duyệt chưa đáp ứng (hiện dưới tiêu đề chung). */
export function unsupportedReason(reason: UnsupportedReason): string {
  return v.deviceUnsupported.reasons[reason];
}

/** Một câu hướng dẫn cho lần chụp lại; gợi ý thiếu hoặc lạ thì dùng câu chung. */
export function retryMessage(hint: RetryHint | null): string {
  return hint ? v.retryHints[hint] : v.retryHintFallback;
}
