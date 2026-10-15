// Bảng màu, nhịp và giới hạn an toàn của ChromaPulse.
// Nguồn DUY NHẤT: packages/contracts/chromapulse.json (API cũng đọc file này). Đừng chép số vào đây.

import raw from "@contracts/chromapulse.json";

export type Rgb = readonly [number, number, number];

export type ChromaPulseConfig = {
  version: number;
  palette: readonly string[];
  baselineColor: string;
  steps: number;
  baselineMs: number;
  tailMs: number;
  holdMinMs: number;
  holdMaxMs: number;
  transitionMs: number;
  maxChangesPerSecond: number;
  maxLuminanceSpread: number;
  maxRedShare: number;
};

export const chromaPulseConfig: ChromaPulseConfig = {
  version: raw.version,
  palette: raw.palette,
  baselineColor: raw.baseline_color,
  steps: raw.steps,
  baselineMs: raw.baseline_ms,
  tailMs: raw.tail_ms,
  holdMinMs: raw.hold_ms.min,
  holdMaxMs: raw.hold_ms.max,
  transitionMs: raw.transition_ms,
  maxChangesPerSecond: raw.limits.max_changes_per_second,
  maxLuminanceSpread: raw.limits.max_luminance_spread,
  maxRedShare: raw.limits.max_red_share,
};

export function hexToRgb(hex: string): Rgb {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) throw new Error(`Màu không hợp lệ: ${hex}`);
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
