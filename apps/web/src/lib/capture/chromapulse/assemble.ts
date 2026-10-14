// Ghép kết quả một lần thử thành bản ghi JSON hoàn chỉnh (hàm thuần, có test).

import {
  type DeviceInfo,
  type LabRecord,
  PRIVACY_NOTE,
  RECORD_SCHEMA_VERSION,
  type Scenario,
  configToRecord,
  sequenceToRecord,
  summarizeSupport,
  timelineToRecord,
} from "./record";
import { REGION_DEFS } from "./regions";
import { type SequenceStep, buildTimeline } from "./sequence";
import type { TrialResult } from "./trial";

export type AssembleInput = {
  scenario: Scenario;
  take: number;
  note: string;
  createdAt: string;
  device: DeviceInfo;
  cameraSettings: Record<string, unknown>;
  steps: readonly SequenceStep[];
  trial: TrialResult;
  delegate: string | null;
  hasFrameCallback: boolean;
};

export function assembleRecord(input: AssembleInput): LabRecord {
  const { trial } = input;
  const timeline = buildTimeline(input.steps);
  return {
    schema_version: RECORD_SCHEMA_VERSION,
    kind: "chromapulse_lab",
    created_at: input.createdAt,
    scenario: input.scenario,
    take: input.take,
    note: input.note,
    privacy: PRIVACY_NOTE,
    device: input.device,
    support: {
      request_video_frame_callback: input.hasFrameCallback,
      has_capture_time: summarizeSupport(trial.frames).has_capture_time,
      frame_metadata_keys: trial.metadataKeys,
      landmarker_delegate: input.delegate,
      clock: "performance.now",
    },
    camera: { settings: input.cameraSettings, applied_constraints_error: null },
    config: configToRecord(),
    sequence: sequenceToRecord(input.steps),
    timeline: timelineToRecord(timeline, trial.startPerformanceNow),
    color_events: trial.colorEvents,
    display_samples: trial.displaySamples,
    frame_times: trial.frames,
    region_defs: REGION_DEFS,
    quality: {
      max_raf_gap_ms: trial.maxRafGapMs,
      hidden_during_trial: trial.hiddenDuringTrial,
      sample_errors: trial.sampleErrors,
    },
  };
}
