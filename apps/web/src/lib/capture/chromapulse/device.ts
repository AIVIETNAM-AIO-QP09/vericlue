// Thông tin máy và camera ghi vào JSON (chỉ để phân tích kết quả, không định danh người dùng).

import type { DeviceInfo } from "./record";

export function collectDeviceInfo(label: string, track: MediaStreamTrack | null): DeviceInfo {
  return {
    label,
    user_agent: navigator.userAgent,
    platform: navigator.platform,
    language: navigator.language,
    screen: {
      width: window.screen.width,
      height: window.screen.height,
      device_pixel_ratio: window.devicePixelRatio,
    },
    hardware_concurrency: navigator.hardwareConcurrency ?? null,
    camera_label: track?.label ?? null,
  };
}

/** Ghi lại cài đặt camera thực tế (tự động phơi sáng, cân bằng trắng... ảnh hưởng phép đo). */
export function readCameraSettings(track: MediaStreamTrack | null): Record<string, unknown> {
  if (!track) return {};
  // Bỏ deviceId và groupId: định danh phần cứng ổn định, không cần cho phân tích.
  const settings = { ...track.getSettings() } as Record<string, unknown>;
  delete settings.deviceId;
  delete settings.groupId;
  const capabilities =
    typeof track.getCapabilities === "function"
      ? (track.getCapabilities() as Record<string, unknown>)
      : {};
  // Chỉ giữ các khóa liên quan đến ánh sáng/màu để file gọn.
  const keys = ["exposureMode", "whiteBalanceMode", "exposureTime", "colorTemperature", "iso"];
  return {
    ...settings,
    capability_modes: Object.fromEntries(
      keys.filter((k) => k in capabilities).map((k) => [k, capabilities[k]]),
    ),
  };
}

/** Ước lượng độ phân giải của performance.now() (Safari làm tròn thô hơn Chrome). */
export function estimateClockResolutionMs(samples = 200): number {
  let min = Infinity;
  let last = performance.now();
  for (let i = 0; i < samples; i += 1) {
    const now = performance.now();
    const delta = now - last;
    if (delta > 0 && delta < min) min = delta;
    last = now;
  }
  return Number.isFinite(min) ? min : 0;
}

/** Xin camera trước, không bật micro. Không ép phơi sáng thủ công: trình duyệt nào hỗ trợ ghi lại ở getSettings(). */
export async function openFrontCamera(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    audio: false,
    video: {
      facingMode: "user",
      width: { ideal: 1280 },
      height: { ideal: 720 },
      frameRate: { ideal: 30 },
    },
  });
}

/** Tên trình duyệt ngắn gọn để đặt tên file (chrome, safari, firefox, edge, samsung, other). */
export function detectBrowser(userAgent: string): string {
  const ua = userAgent.toLowerCase();
  if (ua.includes("edg/") || ua.includes("edga/") || ua.includes("edgios/")) return "edge";
  if (ua.includes("samsungbrowser")) return "samsung";
  if (ua.includes("firefox/") || ua.includes("fxios/")) return "firefox";
  if (ua.includes("chrome/") || ua.includes("crios/")) return "chrome";
  if (ua.includes("safari/")) return "safari";
  return "other";
}
