// Đổi thử thách màu do máy chủ cấp (snake_case) thành bước nháy màu của web, và KIỂM AN TOÀN trước khi nháy.
// Web không tin tuyệt đối thử thách: nếu vi phạm giới hạn của ADR-0011 thì không nháy.

import type { Challenge } from "@/lib/api/client";

import { type ChromaPulseConfig, chromaPulseConfig } from "./chromapulse/config";
import { type SequenceStep, maxChangesPerSecond, paletteProblems } from "./chromapulse/sequence";

const HEX = /^#[0-9a-f]{6}$/i;

/** Thử thách của máy chủ → các bước nháy. Trả null nếu dữ liệu thiếu hoặc sai dạng. */
export function challengeToSteps(challenge: Challenge): SequenceStep[] | null {
  const seq = challenge?.color_sequence;
  if (!Array.isArray(seq) || seq.length === 0) return null;
  const steps: SequenceStep[] = [];
  for (const [index, step] of seq.entries()) {
    const ok =
      typeof step?.rgb === "string" &&
      HEX.test(step.rgb) &&
      Number.isFinite(step.hold_ms) &&
      Number.isFinite(step.transition_ms);
    if (!ok) return null;
    steps.push({ index, rgb: step.rgb, holdMs: step.hold_ms, transitionMs: step.transition_ms });
  }
  return steps;
}

/**
 * Các vấn đề an toàn của chuỗi nháy (rỗng = được phép nháy):
 * đúng số bước, không quá `maxChangesPerSecond` lần đổi/giây, hai màu liền kề khác nhau,
 * chênh độ chói và độ đỏ trong giới hạn.
 */
export function flashProblems(
  steps: readonly SequenceStep[],
  cfg: ChromaPulseConfig = chromaPulseConfig,
): string[] {
  const problems: string[] = [];
  if (steps.length !== cfg.steps) problems.push(`Cần ${cfg.steps} bước, nhận ${steps.length}`);
  if (steps.some((s) => s.holdMs < cfg.holdMinMs || s.holdMs > cfg.holdMaxMs)) {
    problems.push(`Thời gian giữ màu ngoài khoảng ${cfg.holdMinMs}–${cfg.holdMaxMs} ms`);
  }
  if (steps.some((s) => s.transitionMs !== cfg.transitionMs)) {
    problems.push(`Thời gian chuyển màu khác ${cfg.transitionMs} ms`);
  }
  if (steps.length > 0 && maxChangesPerSecond(steps) > cfg.maxChangesPerSecond) {
    problems.push(`Đổi màu quá nhanh (hơn ${cfg.maxChangesPerSecond} lần mỗi giây)`);
  }
  if (steps.some((s, i) => i > 0 && s.rgb.toLowerCase() === steps[i - 1].rgb.toLowerCase())) {
    problems.push("Hai bước liền kề cùng màu");
  }
  problems.push(...paletteProblems([...new Set(steps.map((s) => s.rgb))], cfg));
  return problems;
}

/** Cấu hình thời gian cho một thử thách: nền đầu lấy từ máy chủ nếu có. */
export function configForChallenge(
  challenge: Challenge,
  base: ChromaPulseConfig = chromaPulseConfig,
): ChromaPulseConfig {
  const baseline = challenge.baseline_ms;
  return typeof baseline === "number" && Number.isFinite(baseline) && baseline >= 0
    ? { ...base, baselineMs: baseline }
    : base;
}
