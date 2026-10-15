// Đổi trạng thái/lỗi của luồng thành chữ hiển thị (lấy từ src/i18n/vi.ts). Hàm thuần, có test quét chuỗi:
// không màn hình nào có điểm số hay chữ "giả mạo", và gợi ý chụp lại chỉ nói về chất lượng.

import { vi } from "@/i18n/vi";

import type { CameraProblem, ErrorKind, RetryHint } from "./flow";

const v = vi.verify;

export function errorMessage(kind: ErrorKind): string {
  return v.errors[kind];
}

export function cameraMessage(problem: CameraProblem | null): string {
  if (problem === null) return v.camera.asking;
  return v.camera[problem];
}

/** Một câu hướng dẫn cho lần chụp lại; gợi ý thiếu hoặc lạ thì dùng câu chung. */
export function retryMessage(hint: RetryHint | null): string {
  return hint ? v.retryHints[hint] : v.retryHintFallback;
}
