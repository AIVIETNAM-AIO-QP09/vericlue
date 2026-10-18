"use client";

// Luồng /verify cho người dân. Máy trạng thái nằm ở src/lib/capture/flow.ts; file này chỉ nối giao diện,
// camera và lời gọi API (qua runner.ts → src/lib/api/client.ts) với máy trạng thái đó.
// Người dân không thấy điểm số hay chữ "giả mạo": mọi chữ lấy từ vi.verify (có test quét chuỗi).

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";

import { vi } from "@/i18n/vi";
import { createApiClient, type Signals } from "@/lib/api/client";
import { challengeToSteps, configForChallenge, flashProblems } from "@/lib/capture/challenge";
import { type CamProbe, collectCamProbe } from "@/lib/capture/camprobe";
import { chromaPulseConfig } from "@/lib/capture/chromapulse/config";
import { openFrontCamera } from "@/lib/capture/chromapulse/device";
import type { FrameSampler } from "@/lib/capture/chromapulse/sampler";
import { buildTimeline } from "@/lib/capture/chromapulse/sequence";
import { runTrial, supportsFrameCallback } from "@/lib/capture/chromapulse/trial";
import {
  type CameraProblem,
  type FlowEvent,
  type FlowState,
  hasTimeToFlash,
  initialState,
  qualityWouldPass,
  reduce,
  sessionExpired,
} from "@/lib/capture/flow";
import {
  cameraMessage,
  errorMessage,
  qualityMessage,
  retryMessage,
  unsupportedReason,
} from "@/lib/capture/messages";
import { VIDEO_CLIP_MS, type VideoClip, startVideoClip } from "@/lib/capture/media";
import {
  type NeutralCapture,
  captureNeutralMedia,
  captureThenFlash,
} from "@/lib/capture/mediaPhase";
import { sendVoiceAnswer, startSession, uploadAndFinalize } from "@/lib/capture/runner";
import { resolveScenario } from "@/lib/capture/scenario";
import { VOICE_MAX_MS, VoiceRecorder } from "@/lib/capture/voiceRecorder";

import { CameraView } from "./CameraView";
import { useQualityGate } from "./useQualityGate";

const t = vi.verify;

// TẠM — CAP-04 thay bằng bộ lấy mẫu thật (MediaPipe, 5 vùng da); hiện chưa đo gì.
const NO_SAMPLER: FrameSampler = { sample: () => null };

/** Đoạn ghi âm ngắn hơn mức này (ms) thì bắt ghi lại, không gửi. */
const VOICE_MIN_MS = 1000;
const WAV_HEADER_BYTES = 44;
const WAV_BYTES_PER_MS = 32; // 16 kHz × 2 byte

type VoiceProblem = "tooShort" | "micDenied" | "micUnavailable" | null;

type CameraResult = { ok: true; stream: MediaStream } | { ok: false; problem: CameraProblem };

function stopTracks(stream: MediaStream | null) {
  stream?.getTracks().forEach((track) => track.stop());
}

export function VerifyFlow() {
  const [state, rawDispatch] = useReducer(reduce, initialState);
  const client = useMemo(() => createApiClient(), []);

  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const colorLayerRef = useRef<HTMLDivElement>(null);
  const stopButtonRef = useRef<HTMLButtonElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  // Luôn đúng ngay lập tức: mọi sự kiện đi qua send() (xem bên dưới), không chờ render hay effect.
  const stateRef = useRef<FlowState>(initialState);
  const lifeAbortRef = useRef<AbortController | null>(null); // hủy mọi lời gọi API khi rời trang
  const flashAbortRef = useRef<AbortController | null>(null); // nút Dừng lúc nháy màu
  const signalsRef = useRef<Signals | null>(null);
  // Ảnh + clip 3 giây quay TRƯỚC khi nháy màu, lúc màn hình còn trung tính (mặt không bị ám màu).
  const captureRef = useRef<NeutralCapture | null>(null);
  // CamProbe chạy SAU khi đã chụp ảnh + quay clip (thăm dò applyConstraints có thể hạ độ phân giải nguồn);
  // kết quả (hoặc null nếu lỗi/quá hạn) được ghép vào signals.
  const camProbeRef = useRef<Promise<CamProbe | null> | null>(null);
  const recorderRef = useRef<VoiceRecorder | null>(null);
  const voiceClipRef = useRef<VideoClip | null>(null);
  const voiceFinishingRef = useRef(false);
  const scenarioRef = useRef<string | undefined>(undefined);
  const aliveRef = useRef(true);
  const flashStartedRef = useRef(false);
  const runCounterRef = useRef(0);
  const previousStepRef = useRef<FlowState["step"] | null>(null);
  const [flashing, setFlashing] = useState(false);
  const [holding, setHolding] = useState(false); // đang giữ yên để chụp ảnh + quay clip (chưa nháy màu)
  const [recording, setRecording] = useState(false);
  const [voiceProblem, setVoiceProblem] = useState<VoiceProblem>(null);

  // Đồng hồ đơn điệu: hết hạn không phụ thuộc giờ máy (có thể lệch cả chục phút).
  const deps = useMemo(() => ({ client, monoMs: () => performance.now() }), [client]);

  /** Mã lần chạy mới (tăng dần): kết quả bất đồng bộ của lần cũ bị reducer bỏ qua. */
  const nextRun = useCallback(() => {
    runCounterRef.current += 1;
    return runCounterRef.current;
  }, []);
  const apiSignal = useCallback(() => lifeAbortRef.current?.signal, []);

  const camProbeAbortRef = useRef<AbortController | null>(null);
  const voiceEpochRef = useRef(0); // tăng mỗi lần dọn: kết quả bất đồng bộ của lần ghi cũ bị bỏ qua

  const stopStream = useCallback(() => {
    camProbeAbortRef.current?.abort(); // tắt cả bản sao track của CamProbe, tránh đèn camera sáng thừa
    camProbeAbortRef.current = null;
    stopTracks(streamRef.current);
    streamRef.current = null;
  }, []);

  // Dọn MỌI trạng thái ghi âm. Dùng chung cho Bắt đầu lại (mọi nút), rời trang và bfcache.
  const resetVoice = useCallback(() => {
    voiceEpochRef.current += 1;
    recorderRef.current?.cancel();
    recorderRef.current = null;
    voiceClipRef.current?.stop();
    voiceClipRef.current = null;
    voiceFinishingRef.current = false;
    setRecording(false);
    setVoiceProblem(null);
  }, []);

  // Gửi MỌI sự kiện qua đây: cập nhật stateRef ngay bằng chính reducer thuần (kết quả giống hệt) rồi mới giao
  // cho React. Nhờ vậy hai lần đo liên tiếp, hay một callback đến muộn, không bao giờ đọc trạng thái cũ
  // (ví dụ khi quyết định có cấp mã lần chạy mới hay không).
  const send = useCallback((event: FlowEvent) => {
    stateRef.current = reduce(stateRef.current, event);
    rawDispatch(event);
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    lifeAbortRef.current = new AbortController();
    scenarioRef.current = resolveScenario(window.location.search, process.env.NODE_ENV);
    // Rời trang hoặc đưa vào bộ nhớ đệm: tắt camera và hủy lời gọi ngay (cleanup có thể không kịp chạy).
    const onPageHide = () => {
      flashAbortRef.current?.abort();
      resetVoice();
      stopStream();
    };
    // Trang được khôi phục từ bộ nhớ đệm (bfcache): camera và mô hình đã bị đóng ở pagehide, luồng đang dở
    // không thể chạy tiếp. Báo gián đoạn để người dùng bấm "Bắt đầu lại", thay vì đứng ở bước chuẩn bị.
    const onPageShow = (event: PageTransitionEvent) => {
      if (!event.persisted) return;
      const step = stateRef.current.step;
      if (step === "consent" || step === "result" || step === "error") return;
      if (step === "device_unsupported") return;
      resetVoice();
      stopStream();
      send({ type: "FAILED", kind: "interrupted" });
    };
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("pageshow", onPageShow);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("pageshow", onPageShow);
      aliveRef.current = false;
      lifeAbortRef.current?.abort();
      flashAbortRef.current?.abort();
      resetVoice();
      stopStream();
    };
  }, [stopStream, resetVoice, send]);

  // Mở camera và TRẢ luồng cục bộ (không gán vào ref): bên gọi quyết định có nhận luồng hay không.
  const openCamera = useCallback(async (): Promise<CameraResult> => {
    if (!window.isSecureContext) return { ok: false, problem: "insecure" };
    try {
      return { ok: true, stream: await openFrontCamera() };
    } catch (e) {
      const denied = e instanceof DOMException && e.name === "NotAllowedError";
      return { ok: false, problem: denied ? "denied" : "unavailable" };
    }
  }, []);

  // Nhận luồng vừa mở nếu còn hiệu lực. Nếu không, chỉ tắt luồng CỦA CHÍNH NÓ, không đụng luồng khác.
  const adoptStream = useCallback((stream: MediaStream, valid: boolean) => {
    if (!valid || !aliveRef.current) {
      stopTracks(stream);
      return false;
    }
    if (streamRef.current && streamRef.current !== stream) stopTracks(streamRef.current);
    streamRef.current = stream;
    // Luồng mới: CamProbe cũ không còn đúng. Chỉ bắt đầu lại sau khi chụp ảnh (startCamProbe).
    camProbeAbortRef.current?.abort();
    camProbeAbortRef.current = null;
    camProbeRef.current = null;
    return true;
  }, []);

  // CamProbe (CAP-05) chạy trên bản sao track, SAU khi đã chụp ảnh + quay clip. Lỗi/quá hạn thì null
  // (thiếu tín hiệu → máy chủ ra "review", không bao giờ "pass").
  const startCamProbe = useCallback(() => {
    const stream = streamRef.current;
    if (!stream || camProbeRef.current) return;
    const probeAbort = new AbortController();
    camProbeAbortRef.current = probeAbort;
    camProbeRef.current = collectCamProbe(stream, { signal: probeAbort.signal }).catch(() => null);
  }, []);

  // Mỗi trạng thái (một đối tượng riêng cho mỗi lần vào bước) chỉ khởi chạy việc bất đồng bộ một lần,
  // kể cả khi React StrictMode (chế độ phát triển) chạy effect hai lần.
  const startedFor = useRef<FlowState | null>(null);
  const startOnce = useCallback((s: FlowState) => {
    if (startedFor.current === s) return false;
    startedFor.current = s;
    return true;
  }, []);

  // --- Hiệu ứng theo từng bước -----------------------------------------------------------------

  useEffect(() => {
    if (state.step !== "camera_permission" || state.problem !== null) return;
    if (!startOnce(state)) return; // chỉ mở camera một lần cho mỗi lần xin
    const attempt = state.attempt;
    void openCamera().then((result) => {
      // Còn hiệu lực = trang còn sống và luồng vẫn đang xin quyền, ĐÚNG lần xin này. So NỘI DUNG
      // (step, problem, attempt): stateRef (do send() tạo) và state của React là hai đối tượng khác nhau,
      // nên KHÔNG được so danh tính (===) giữa chúng.
      const cur = stateRef.current;
      const stillHere =
        aliveRef.current &&
        cur.step === "camera_permission" &&
        cur.problem === null &&
        cur.attempt === attempt;
      if (result.ok) {
        if (adoptStream(result.stream, stillHere)) send({ type: "CAMERA_GRANTED", attempt });
      } else if (stillHere) {
        send({ type: "CAMERA_FAILED", problem: result.problem, attempt });
      }
    });
  }, [state, openCamera, adoptStream, startOnce, send]);

  // Gắn luồng camera vào video mỗi khi bước cần xem (khung hình, nháy màu).
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const needsVideo =
      state.step === "framing" || state.step === "flash_challenge" || state.step === "uploading";
    if (!needsVideo) return;
    const stepAtStart = state.step;
    let cancelled = false;
    void (async () => {
      let stream = streamRef.current;
      if (!stream) {
        const result = await openCamera(); // bắt đầu lại sau khi camera đã tắt
        const valid = !cancelled && stateRef.current.step === stepAtStart;
        if (!result.ok) {
          if (valid) send({ type: "FAILED", kind: "unexpected" });
          return;
        }
        if (!adoptStream(result.stream, valid)) return;
        stream = result.stream;
      }
      if (cancelled) return;
      if (video.srcObject !== stream) video.srcObject = stream;
      await video.play().catch(() => undefined);
    })();
    return () => {
      cancelled = true;
    };
  }, [state.step, openCamera, adoptStream, send]);

  // Cổng chất lượng (CAP-02): đo từng khung khi xem trước. Chỉ đủ N khung đạt LIÊN TIẾP mới đi tiếp, và
  // mã lần chạy mới chỉ được cấp đúng khung cuối cùng làm đủ N (qualityWouldPass).
  const qualityCallbacks = useMemo(
    () => ({
      onGuidance: (guidance: Parameters<typeof qualityWouldPass>[1]) => {
        const current = stateRef.current;
        if (current.step !== "framing") return;
        send({
          type: "QUALITY_FRAME",
          guidance,
          run: qualityWouldPass(current, guidance) ? nextRun() : undefined,
        });
      },
      onUnsupported: (reason: Extract<FlowEvent, { type: "DEVICE_UNSUPPORTED" }>["reason"]) =>
        send({ type: "DEVICE_UNSUPPORTED", reason }),
      onFailure: () => send({ type: "FAILED", kind: "unexpected" }),
    }),
    [send, nextRun],
  );
  useQualityGate({
    active: state.step === "framing",
    videoRef,
    callbacks: qualityCallbacks,
  });

  useEffect(() => {
    if (state.step !== "creating_session") return;
    if (!startOnce(state)) return; // chỉ tạo MỘT phiên cho mỗi lần vào bước này
    void startSession(deps, { run: state.run, signal: apiSignal() }, scenarioRef.current).then(
      (event) => {
        if (aliveRef.current) send(event);
      },
    );
  }, [state, deps, startOnce, apiSignal, send]);

  useEffect(() => {
    if (state.step !== "uploading") return;
    if (!startOnce(state)) return; // gửi MỘT lần: gửi hai lần có thể bị 409 ở lần finalize thứ hai
    const signals = signalsRef.current;
    const captured = captureRef.current;
    const session = state.session;
    const run =
      signals && captured
        ? uploadAndFinalize(
            deps,
            session,
            // Video là trường tùy chọn: không ghi được thì vẫn gửi ảnh.
            { image: captured.image, signals, video: captured.clip ?? undefined },
            apiSignal(),
          )
        : Promise.resolve({ type: "FAILED", kind: "unexpected", run: session.run } as const);
    void run.then((event) => {
      if (aliveRef.current) send(event);
    });
  }, [state, deps, startOnce, apiSignal, send]);

  useEffect(() => {
    if (state.step === "result" || state.step === "error" || state.step === "device_unsupported") {
      stopStream();
    }
  }, [state.step, stopStream]);

  // Đổi bước thì đưa tiêu đề mới vào focus (trình đọc màn hình đọc được); không cướp focus lúc mới vào trang.
  useEffect(() => {
    const previous = previousStepRef.current;
    previousStepRef.current = state.step;
    if (previous === null || previous === state.step) return;
    containerRef.current?.querySelector<HTMLElement>("[data-step-heading]")?.focus();
  }, [state.step]);

  // Lúc nháy màu, nút Dừng được focus để dùng bàn phím/trình đọc màn hình.
  useEffect(() => {
    if (flashing) stopButtonRef.current?.focus();
  }, [flashing]);

  // --- Hành động của người dùng ----------------------------------------------------------------

  const expire = useCallback(
    (run: number) => {
      send({ type: "EXPIRED", run, nextRun: nextRun() });
    },
    [nextRun, send],
  );

  const startFlash = useCallback(async () => {
    if (state.step !== "flash_challenge") return;
    const video = videoRef.current;
    const { session } = state;
    // Hết hạn thì không dùng thử thách cũ: quay về tạo phiên mới.
    if (sessionExpired(session, deps.monoMs())) {
      expire(session.run);
      return;
    }
    const steps = challengeToSteps(session.challenge);
    // Không nháy nếu thử thách vi phạm giới hạn an toàn hoặc trình duyệt không hỗ trợ.
    if (!video || !steps || flashProblems(steps).length > 0 || !supportsFrameCallback(video)) {
      send({ type: "FAILED", kind: "unexpected", run: session.run });
      return;
    }
    const config = configForChallenge(session.challenge);
    // Còn đủ thời gian để giữ yên (clip), nháy xong và gửi? Không đủ thì tạo phiên mới NGAY.
    const flashMs = buildTimeline(steps, config).totalMs;
    if (!hasTimeToFlash(session, deps.monoMs(), VIDEO_CLIP_MS + flashMs)) {
      expire(session.run);
      return;
    }
    if (flashStartedRef.current) return; // bấm Bắt đầu hai lần: chỉ chạy một lần
    flashStartedRef.current = true;
    const abort = new AbortController();
    flashAbortRef.current = abort;
    captureRef.current = null;
    setHolding(true);
    // Thứ tự (quyết định trưởng nhóm): ảnh → clip 3 giây → MỚI nháy màu. Quay clip lúc màn hình đổi màu
    // làm mặt bị ám màu và bộ phát hiện deepfake khuôn mặt (ưu tiên đọc video) chấm sai.
    // ChromaPulse là tín hiệu phụ ở hồ sơ mvp (ADR-0012), nên `capture_at_ms` của máy chủ chưa dùng.
    const runPhases = () =>
      captureThenFlash({
        capture: () =>
          captureNeutralMedia({ video, stream: streamRef.current, signal: abort.signal }),
        flash: (captured) => {
          captureRef.current = captured;
          startCamProbe(); // sau khi chụp xong: không làm hạ độ phân giải ảnh
          setHolding(false);
          setFlashing(true);
          return runTrial({
            video,
            sampler: NO_SAMPLER,
            steps,
            config,
            signal: abort.signal,
            onColor: (rgb) => {
              if (colorLayerRef.current)
                colorLayerRef.current.style.backgroundColor = `rgb(${rgb.join(",")})`;
            },
          });
        },
      });
    let outcome: Awaited<ReturnType<typeof runPhases>>;
    try {
      outcome = await runPhases();
    } catch {
      flashStartedRef.current = false;
      if (aliveRef.current) {
        setHolding(false);
        setFlashing(false); // không để màn hình nháy kẹt
        send({ type: "FAILED", kind: "unexpected", run: session.run });
      }
      return;
    }
    flashStartedRef.current = false;
    if (!aliveRef.current) return;
    setHolding(false);
    setFlashing(false);
    // Bị hủy lúc giữ yên (chưa nháy) hoặc lúc nháy.
    if (outcome === null || outcome.flash.aborted) {
      const hidden = outcome?.flash.hiddenDuringTrial ?? document.visibilityState !== "visible";
      send({ type: hidden ? "FLASH_INTERRUPTED" : "FLASH_STOPPED" });
      return;
    }
    const { captured, flash: trial } = outcome;
    // CamProbe bắt đầu ngay sau khi chụp xong nên thường đã xong trước khi nháy màu kết thúc; có hạn 8 giây.
    const camprobe = await camProbeRef.current;
    if (!aliveRef.current) return;
    // TẠM — CAP-04 thay bằng tín hiệu đầy đủ (frame_times, region_means).
    signalsRef.current = {
      color_events: trial.colorEvents,
      frame_times: [],
      ...(camprobe ? { camprobe } : {}),
      // Kích thước ảnh thật đã gửi (ảnh bị hạ độ phân giải sẽ thấy ở đây); schema: client_quality là object tự do.
      client_quality: {
        image_width: captured.imageSize.width,
        image_height: captured.imageSize.height,
        source_width: captured.sourceSize.width,
        source_height: captured.sourceSize.height,
        video_recorded: captured.clip !== null,
      },
    };
    send({ type: "FLASH_DONE" });
  }, [state, deps, expire, send, startCamProbe]);

  const continueRetry = useCallback(() => {
    if (state.step !== "retry") return;
    if (sessionExpired(state.session, deps.monoMs())) expire(state.session.run);
    else send({ type: "RETRY_CONTINUE" });
  }, [state, deps, expire, send]);

  // Dừng ghi (nút Dừng hoặc hết ~8 giây) rồi gửi WAV 16 kHz (+ video nếu có). Chỉ chạy một lần mỗi lần ghi.
  const finishVoice = useCallback(async () => {
    const current = stateRef.current;
    const recorder = recorderRef.current;
    if (current.step !== "voice_challenge" || !recorder || voiceFinishingRef.current) return;
    voiceFinishingRef.current = true;
    const epoch = voiceEpochRef.current;
    // Bắt đầu lại hoặc rời trang trong lúc chờ: bỏ kết quả, không gửi cho phiên cũ.
    const stale = () => !aliveRef.current || voiceEpochRef.current !== epoch;
    const clip = voiceClipRef.current;
    clip?.stop();
    const audio = await recorder.stop();
    if (stale()) return;
    recorderRef.current = null;
    voiceClipRef.current = null;
    setRecording(false);
    const durationMs = (audio.size - WAV_HEADER_BYTES) / WAV_BYTES_PER_MS;
    if (durationMs < VOICE_MIN_MS) {
      voiceFinishingRef.current = false;
      setVoiceProblem("tooShort");
      return;
    }
    const video = (await clip?.done) ?? undefined;
    if (stale()) return;
    send({ type: "VOICE_SENDING" });
    const event = await sendVoiceAnswer(deps, current.session, audio, video, apiSignal());
    if (stale()) return;
    voiceFinishingRef.current = false;
    send(event);
  }, [deps, apiSignal, send]);

  // Bấm "Bắt đầu ghi âm": VoiceRecorder PHẢI được tạo đồng bộ trong thao tác bấm (iOS), trước mọi await.
  const startVoice = useCallback(async () => {
    if (stateRef.current.step !== "voice_challenge" || recorderRef.current) return;
    setVoiceProblem(null);
    const epoch = voiceEpochRef.current;
    let recorder: VoiceRecorder;
    try {
      recorder = new VoiceRecorder({ onAutoStop: () => void finishVoice() });
    } catch {
      setVoiceProblem("micUnavailable");
      return;
    }
    recorderRef.current = recorder;
    try {
      await recorder.start();
    } catch (e) {
      if (!aliveRef.current || voiceEpochRef.current !== epoch) return; // đã dọn trong lúc chờ
      recorderRef.current = null;
      const denied = e instanceof DOMException && e.name === "NotAllowedError";
      setVoiceProblem(denied ? "micDenied" : "micUnavailable");
      return;
    }
    if (!aliveRef.current || voiceEpochRef.current !== epoch) {
      recorder.cancel();
      return;
    }
    voiceFinishingRef.current = false;
    voiceClipRef.current = streamRef.current
      ? startVideoClip(streamRef.current, { durationMs: VOICE_MAX_MS })
      : null;
    setRecording(true);
  }, [finishVoice]);

  const restart = useCallback(() => {
    resetVoice();
    send({ type: "RESTART" });
  }, [resetVoice, send]);

  // --- Giao diện -------------------------------------------------------------------------------

  const showVideo =
    state.step === "framing" || state.step === "flash_challenge" || state.step === "uploading";

  return (
    <div ref={containerRef} className="flex flex-col gap-4">
      {/* Video luôn nằm trong DOM; lúc nháy màu lớp màu phủ che nó (không display:none: iOS có thể ngừng cấp khung). */}
      <CameraView
        videoRef={videoRef}
        visible={showVideo}
        showOval={state.step === "framing"}
        ok={state.step === "framing" && state.guidance === null && state.streak > 0}
      />

      {state.step === "consent" && (
        <section className="flex flex-col gap-3 rounded border p-4">
          <h2 className="text-lg font-semibold" tabIndex={-1} data-step-heading>
            {t.consent.title}
          </h2>
          <p className="font-medium">{t.consent.sensitive}</p>
          <h3 className="font-semibold">{t.consent.purposeTitle}</h3>
          <p>{t.consent.purpose}</p>
          <h3 className="font-semibold">{t.consent.retentionTitle}</h3>
          <p>{t.consent.retention}</p>
          <p>{t.consent.stopAnytime}</p>
          <label className="flex items-start gap-2">
            <input
              type="checkbox"
              checked={state.accepted}
              onChange={(e) => send({ type: "TOGGLE_CONSENT", accepted: e.target.checked })}
              className="mt-1"
            />
            <span>{t.consent.checkbox}</span>
          </label>
          <button
            type="button"
            disabled={!state.accepted}
            onClick={() => send({ type: "CONTINUE" })}
            className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-40"
          >
            {t.consent.continue}
          </button>
        </section>
      )}

      {state.step === "camera_permission" && (
        <section className="flex flex-col gap-3 rounded border p-4">
          <h2 className="text-lg font-semibold" tabIndex={-1} data-step-heading>
            {t.camera.title}
          </h2>
          <p>{t.camera.description}</p>
          <p role="status">{cameraMessage(state.problem)}</p>
          {state.problem !== null && (
            <button
              type="button"
              onClick={() => send({ type: "CONTINUE" })}
              className="rounded bg-blue-600 px-4 py-2 text-white"
            >
              {t.camera.retry}
            </button>
          )}
        </section>
      )}

      {state.step === "framing" && (
        <section className="flex flex-col gap-3 rounded border p-4">
          <h2 className="text-lg font-semibold" tabIndex={-1} data-step-heading>
            {t.framing.title}
          </h2>
          <p>{t.framing.description}</p>
          {/* Mỗi lần chỉ MỘT chỉ dẫn, chỉ nói về chất lượng ảnh. */}
          <p role="status" aria-live="polite" className="text-lg font-medium">
            {state.guidance !== null
              ? qualityMessage(state.guidance)
              : state.streak > 0
                ? qualityMessage(null)
                : t.framing.loading}
          </p>
        </section>
      )}

      {state.step === "device_unsupported" && (
        <section className="flex flex-col gap-3 rounded border p-4" role="status">
          <h2 className="text-lg font-semibold" tabIndex={-1} data-step-heading>
            {t.deviceUnsupported.title}
          </h2>
          <p>{unsupportedReason(state.reason)}</p>
          <p>{t.deviceUnsupported.body}</p>
          <button
            type="button"
            onClick={restart}
            className="rounded bg-blue-600 px-4 py-2 text-white"
          >
            {t.deviceUnsupported.restart}
          </button>
        </section>
      )}
      {state.step === "creating_session" && <p role="status">{t.creating}</p>}

      {state.step === "flash_challenge" && holding && (
        <section
          className="flex flex-col gap-3 rounded border p-4"
          role="status"
          aria-live="polite"
        >
          <h2 className="text-lg font-semibold" tabIndex={-1} data-step-heading>
            {t.flash.holdTitle}
          </h2>
          <p className="text-lg">{t.flash.hold}</p>
          <button
            type="button"
            onClick={() => flashAbortRef.current?.abort()}
            className="rounded border px-4 py-2"
          >
            {t.flash.stop}
          </button>
        </section>
      )}

      {state.step === "flash_challenge" && !flashing && !holding && (
        <section className="flex flex-col gap-3 rounded border p-4">
          <h2 className="text-lg font-semibold" tabIndex={-1} data-step-heading>
            {t.flash.title}
          </h2>
          <p>{t.flash.warning}</p>
          <p>{t.flash.brightness}</p>
          <button
            type="button"
            onClick={startFlash}
            className="rounded bg-green-600 px-4 py-2 text-white"
          >
            {t.flash.start}
          </button>
        </section>
      )}

      {/* Màn hình nháy màu phủ toàn bộ trang. TẠM — CAP-04 thay bằng ChromaPulse chính thức. */}
      <div
        ref={colorLayerRef}
        className={
          flashing ? "fixed inset-0 z-50 flex flex-col items-center justify-end" : "hidden"
        }
        style={{ backgroundColor: chromaPulseConfig.baselineColor }}
      >
        <div className="mb-6 flex w-full max-w-sm flex-col gap-2 px-4">
          <p className="text-center text-black/70">{t.flash.running}</p>
          <button
            type="button"
            ref={stopButtonRef}
            onClick={() => flashAbortRef.current?.abort()}
            className="rounded bg-black/60 px-4 py-2 text-white"
          >
            {t.flash.stop}
          </button>
        </div>
      </div>

      {state.step === "uploading" && <p role="status">{t.uploading}</p>}

      {state.step === "retry" && (
        <section
          className="flex flex-col gap-3 rounded border p-4"
          role="status"
          aria-live="polite"
        >
          <h2 className="text-lg font-semibold" tabIndex={-1} data-step-heading>
            {t.result.retryTitle}
          </h2>
          <p>{retryMessage(state.hint)}</p>
          {state.attemptsLeft !== null && (
            <p>
              {t.result.retryAttempts}: {state.attemptsLeft}
            </p>
          )}
          <button
            type="button"
            onClick={continueRetry}
            className="rounded bg-blue-600 px-4 py-2 text-white"
          >
            {t.result.retryButton}
          </button>
        </section>
      )}

      {state.step === "voice_challenge" && (
        <section
          className="flex flex-col gap-3 rounded border p-4"
          role="status"
          aria-live="polite"
        >
          <h2 className="text-lg font-semibold" tabIndex={-1} data-step-heading>
            {t.voice.title}
          </h2>
          <p className="text-sm opacity-70">{t.voice.promptLabel}</p>
          <p className="text-xl font-medium">{state.prompt}</p>
          {state.rereadsLeft !== null && (
            <p>
              {t.voice.attemptsLeft}: {state.rereadsLeft}
            </p>
          )}
          <p>{t.voice.instruction}</p>
          {voiceProblem !== null && (
            <p role="alert" className="font-medium">
              {t.voice[voiceProblem]}
            </p>
          )}
          {recording && <p>{t.voice.recording}</p>}
          {state.sending ? (
            <p>{t.voice.sending}</p>
          ) : recording ? (
            <button
              type="button"
              onClick={() => void finishVoice()}
              className="rounded bg-red-700 px-4 py-2 text-white"
            >
              {t.voice.stop}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void startVoice()}
              className="rounded bg-green-600 px-4 py-2 text-white"
            >
              {t.voice.start}
            </button>
          )}
          <button type="button" onClick={restart} className="rounded border px-4 py-2">
            {t.errors.restart}
          </button>
        </section>
      )}

      {state.step === "result" && state.outcome === "pass" && (
        <section className="flex flex-col gap-2 rounded border p-4" role="status">
          <h2 className="text-lg font-semibold" tabIndex={-1} data-step-heading>
            {t.result.passTitle}
          </h2>
          <p>{t.result.passBody}</p>
        </section>
      )}

      {state.step === "result" && state.outcome === "review" && (
        <section className="flex flex-col gap-2 rounded border p-4" role="status">
          <h2 className="text-lg font-semibold" tabIndex={-1} data-step-heading>
            {t.result.reviewTitle}
          </h2>
          <p>{t.result.reviewBody}</p>
        </section>
      )}

      {state.step === "error" && (
        <section className="flex flex-col gap-3 rounded border border-red-300 p-4" role="alert">
          <h2 className="text-lg font-semibold" tabIndex={-1} data-step-heading>
            {t.errors.title}
          </h2>
          <p>{errorMessage(state.kind)}</p>
          <button
            type="button"
            onClick={restart}
            className="rounded bg-blue-600 px-4 py-2 text-white"
          >
            {t.errors.restart}
          </button>
        </section>
      )}
    </div>
  );
}
