// Một lần thử: phát chuỗi màu bằng requestAnimationFrame và ghi mỗi khung video bằng
// requestVideoFrameCallback. Mọi mốc thời gian dùng performance.now() (không Date.now, không MediaRecorder).

import type { Rgb } from "./config";
import type { ColorEvent, DisplaySample, FrameRecord } from "./record";
import { frameMetadataKeys } from "./record";
import type { FrameSampler, FrameSample } from "./sampler";
import { type SequenceStep, buildTimeline, colorAt } from "./sequence";

export type TrialResult = {
  colorEvents: ColorEvent[];
  displaySamples: DisplaySample[];
  frames: FrameRecord[];
  metadataKeys: string[];
  startPerformanceNow: number;
  totalMs: number;
  aborted: boolean;
};

export type TrialOptions = {
  video: HTMLVideoElement;
  sampler: FrameSampler;
  steps: readonly SequenceStep[];
  /** Vẽ màu nền màn hình. */
  onColor: (rgb: Rgb) => void;
  /** Mỗi khung video đã lấy mẫu (để vẽ lớp phủ kiểm tra), tùy chọn. */
  onSample?: (sample: FrameSample) => void;
  onProgress?: (elapsedMs: number, totalMs: number) => void;
  signal?: AbortSignal;
};

export function supportsFrameCallback(video: HTMLVideoElement): boolean {
  return typeof video.requestVideoFrameCallback === "function";
}

export function runTrial(options: TrialOptions): Promise<TrialResult> {
  const { video, sampler, steps, onColor, onSample, onProgress, signal } = options;
  const timeline = buildTimeline(steps);

  const colorEvents: ColorEvent[] = [];
  const displaySamples: DisplaySample[] = [];
  const frames: FrameRecord[] = [];
  const metadataKeys = new Set<string>();

  let startNow: number | null = null;
  let nextEvent = 0;
  let finished = false;

  return new Promise<TrialResult>((resolve) => {
    const finish = (aborted: boolean) => {
      if (finished) return;
      finished = true;
      resolve({
        colorEvents,
        displaySamples,
        frames,
        metadataKeys: [...metadataKeys].sort(),
        startPerformanceNow: startNow ?? 0,
        totalMs: timeline.totalMs,
        aborted,
      });
    };

    const onFrame = (now: number, metadata: VideoFrameCallbackMetadata) => {
      if (finished) return;
      if (startNow !== null) {
        const sample = sampler.sample(video);
        onSample?.(sample);
        for (const key of frameMetadataKeys(metadata)) metadataKeys.add(key);
        // Các trường có thể không có trên mọi trình duyệt.
        const extra = metadata as VideoFrameCallbackMetadata & {
          captureTime?: number;
          receiveTime?: number;
        };
        frames.push({
          index: frames.length,
          now,
          media_time: metadata.mediaTime,
          presented_frames: metadata.presentedFrames,
          capture_time: extra.captureTime ?? null,
          expected_display_time: metadata.expectedDisplayTime ?? null,
          receive_time: extra.receiveTime ?? null,
          processing_duration: metadata.processingDuration ?? null,
          width: metadata.width,
          height: metadata.height,
          face_found: sample.faceFound,
          regions: sample.regions,
        });
      }
      video.requestVideoFrameCallback(onFrame);
    };

    const tick = (t: number) => {
      if (finished) return;
      if (signal?.aborted) {
        finish(true);
        return;
      }
      if (startNow === null) startNow = t;
      const elapsed = t - startNow;
      const { rgb, done } = colorAt(timeline, elapsed);
      onColor(rgb);
      displaySamples.push([t, rgb[0], rgb[1], rgb[2]]);

      while (
        nextEvent < timeline.segments.length &&
        elapsed >= timeline.segments[nextEvent].startMs
      ) {
        const seg = timeline.segments[nextEvent];
        colorEvents.push({ index: seg.index, rgb: seg.rgb, painted_at: t });
        nextEvent += 1;
      }
      onProgress?.(Math.min(elapsed, timeline.totalMs), timeline.totalMs);
      if (done) finish(false);
      else requestAnimationFrame(tick);
    };

    video.requestVideoFrameCallback(onFrame);
    requestAnimationFrame(tick);
  });
}
