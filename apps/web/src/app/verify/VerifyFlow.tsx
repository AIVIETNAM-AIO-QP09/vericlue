"use client";

// Luồng /verify cho người dân. Máy trạng thái nằm ở src/lib/capture/flow.ts; file này chỉ nối giao diện,
// camera và lời gọi API (qua runner.ts → src/lib/api/client.ts) với máy trạng thái đó.
// Người dân không thấy điểm số hay chữ "giả mạo": mọi chữ lấy từ vi.verify (có test quét chuỗi).

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";

import { vi } from "@/i18n/vi";
import { createApiClient, type Signals } from "@/lib/api/client";
import { challengeToSteps, configForChallenge, flashProblems } from "@/lib/capture/challenge";
import { chromaPulseConfig } from "@/lib/capture/chromapulse/config";
import { openFrontCamera } from "@/lib/capture/chromapulse/device";
import type { FrameSampler } from "@/lib/capture/chromapulse/sampler";
import { runTrial, supportsFrameCallback } from "@/lib/capture/chromapulse/trial";
import { type FlowState, initialState, reduce, sessionExpired } from "@/lib/capture/flow";
import { cameraMessage, errorMessage, retryMessage } from "@/lib/capture/messages";
import { sendVoiceAnswer, startSession, uploadAndFinalize } from "@/lib/capture/runner";
import { resolveScenario } from "@/lib/capture/scenario";

const t = vi.verify;
const IS_DEV = process.env.NODE_ENV !== "production";

// TẠM — CAP-04 thay bằng bộ lấy mẫu thật (MediaPipe, 5 vùng da); hiện chưa đo gì.
const NO_SAMPLER: FrameSampler = { sample: () => null };

// TẠM — CAP-06 thay bằng ảnh chụp thật tại `capture_at_ms` do máy chủ chọn.
const PLACEHOLDER_IMAGE = new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xd9])], {
  type: "image/jpeg",
});
// TẠM — CAP-07 thay bằng ghi âm thật khi đọc câu (chỉ dùng ở môi trường phát triển).
const PLACEHOLDER_AUDIO = new Blob([new Uint8Array([0x52, 0x49, 0x46, 0x46])], {
  type: "audio/wav",
});

export function VerifyFlow() {
  const [state, dispatch] = useReducer(reduce, initialState);
  const client = useMemo(() => createApiClient(), []);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const colorLayerRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const signalsRef = useRef<Signals | null>(null);
  const scenarioRef = useRef<string | undefined>(undefined);
  const aliveRef = useRef(true);
  const flashStartedRef = useRef(false);
  const [flashing, setFlashing] = useState(false);

  const deps = useMemo(() => ({ client, nowMs: () => Date.now() }), [client]);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    scenarioRef.current = resolveScenario(window.location.search, process.env.NODE_ENV);
    return () => {
      aliveRef.current = false;
      abortRef.current?.abort();
      stopStream();
    };
  }, [stopStream]);

  // Mở camera (dùng cho bước xin quyền và khi bắt đầu lại mà camera đã tắt).
  const openCamera = useCallback(async (): Promise<
    "ok" | "denied" | "unavailable" | "insecure"
  > => {
    if (!window.isSecureContext) return "insecure";
    stopStream();
    try {
      const stream = await openFrontCamera();
      streamRef.current = stream; // gán ngay để rời trang vẫn tắt được camera
      if (!aliveRef.current) {
        stopStream();
        return "unavailable";
      }
      return "ok";
    } catch (e) {
      return e instanceof DOMException && e.name === "NotAllowedError" ? "denied" : "unavailable";
    }
  }, [stopStream]);

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
    if (!startOnce(state)) return; // StrictMode chạy effect hai lần: chỉ mở camera một lần cho mỗi lần xin
    void openCamera().then((result) => {
      if (!aliveRef.current) return;
      dispatch(
        result === "ok" ? { type: "CAMERA_GRANTED" } : { type: "CAMERA_FAILED", problem: result },
      );
    });
  }, [state, openCamera, startOnce]);

  // Gắn luồng camera vào video mỗi khi bước cần xem (khung hình, nháy màu).
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const needsVideo =
      state.step === "framing" || state.step === "flash_challenge" || state.step === "uploading";
    if (!needsVideo) return;
    let cancelled = false;
    void (async () => {
      if (!streamRef.current) {
        const result = await openCamera(); // bắt đầu lại sau khi camera đã tắt
        if (cancelled || !aliveRef.current) {
          stopStream(); // bước đã đổi trong lúc mở: không để camera mở thừa
          return;
        }
        if (result !== "ok") {
          dispatch({ type: "FAILED", kind: "unexpected" });
          return;
        }
      }
      if (video.srcObject !== streamRef.current) video.srcObject = streamRef.current;
      await video.play().catch(() => undefined);
    })();
    return () => {
      cancelled = true;
    };
  }, [state.step, openCamera, stopStream]);

  useEffect(() => {
    // TẠM — CAP-02 thay bằng cổng chất lượng thật; hiện luôn cho qua.
    if (state.step === "quality_check") dispatch({ type: "QUALITY_PASSED" });
  }, [state.step]);

  useEffect(() => {
    if (state.step !== "creating_session") return;
    if (!startOnce(state)) return; // chỉ tạo MỘT phiên cho mỗi lần vào bước này
    void startSession(deps, scenarioRef.current).then((event) => {
      if (aliveRef.current) dispatch(event);
    });
  }, [state, deps, startOnce]);

  useEffect(() => {
    if (state.step !== "uploading") return;
    if (!startOnce(state)) return; // gửi MỘT lần: gửi hai lần có thể bị 409 ở lần finalize thứ hai
    const signals = signalsRef.current;
    const run = signals
      ? uploadAndFinalize(deps, state.session, { image: PLACEHOLDER_IMAGE, signals })
      : Promise.resolve({ type: "FAILED", kind: "unexpected" } as const);
    void run.then((event) => {
      if (aliveRef.current) dispatch(event);
    });
  }, [state, deps, startOnce]);

  useEffect(() => {
    if (state.step === "result" || state.step === "error") stopStream();
  }, [state.step, stopStream]);

  // --- Hành động của người dùng ----------------------------------------------------------------

  const startFlash = useCallback(async () => {
    if (state.step !== "flash_challenge") return;
    const video = videoRef.current;
    const { session } = state;
    // Hết hạn thì không dùng thử thách cũ: quay về tạo phiên mới.
    if (sessionExpired(session, deps.nowMs())) {
      dispatch({ type: "EXPIRED" });
      return;
    }
    const steps = challengeToSteps(session.challenge);
    // Không nháy nếu thử thách vi phạm giới hạn an toàn hoặc trình duyệt không hỗ trợ.
    if (!video || !steps || flashProblems(steps).length > 0 || !supportsFrameCallback(video)) {
      dispatch({ type: "FAILED", kind: "unexpected" });
      return;
    }
    if (flashStartedRef.current) return; // bấm Bắt đầu hai lần: chỉ chạy một lần
    flashStartedRef.current = true;
    abortRef.current = new AbortController();
    setFlashing(true);
    let trial: Awaited<ReturnType<typeof runTrial>>;
    try {
      trial = await runTrial({
        video,
        sampler: NO_SAMPLER,
        steps,
        config: configForChallenge(session.challenge),
        signal: abortRef.current.signal,
        onColor: (rgb) => {
          if (colorLayerRef.current)
            colorLayerRef.current.style.backgroundColor = `rgb(${rgb.join(",")})`;
        },
      });
    } catch {
      flashStartedRef.current = false;
      if (aliveRef.current) {
        setFlashing(false); // không để màn hình nháy kẹt
        dispatch({ type: "FAILED", kind: "unexpected" });
      }
      return;
    }
    flashStartedRef.current = false;
    if (!aliveRef.current) return;
    setFlashing(false);
    if (trial.aborted) {
      dispatch({ type: trial.hiddenDuringTrial ? "FLASH_INTERRUPTED" : "FLASH_STOPPED" });
      return;
    }
    // TẠM — CAP-04 thay bằng tín hiệu đầy đủ (frame_times, region_means).
    signalsRef.current = { color_events: trial.colorEvents, frame_times: [] };
    dispatch({ type: "FLASH_DONE" });
  }, [state, deps]);

  const continueRetry = useCallback(() => {
    if (state.step !== "retry") return;
    dispatch(
      sessionExpired(state.session, deps.nowMs())
        ? { type: "EXPIRED" }
        : { type: "RETRY_CONTINUE" },
    );
  }, [state, deps]);

  const sendDevVoice = useCallback(async () => {
    if (state.step !== "voice_challenge") return;
    dispatch({ type: "VOICE_SENDING" });
    const event = await sendVoiceAnswer(deps, state.session, PLACEHOLDER_AUDIO);
    if (aliveRef.current) dispatch(event);
  }, [state, deps]);

  // --- Giao diện -------------------------------------------------------------------------------

  const showVideo =
    state.step === "framing" || state.step === "flash_challenge" || state.step === "uploading";

  return (
    <div className="flex flex-col gap-4">
      <video
        ref={videoRef}
        playsInline
        muted
        // Không dùng display:none khi đang chạy: iOS Safari có thể ngừng cấp khung. Lớp màu phủ che nó.
        className={showVideo ? "w-full max-w-md -scale-x-100 rounded" : "hidden"}
      />

      {state.step === "consent" && (
        <section className="flex flex-col gap-3 rounded border p-4">
          <h2 className="text-lg font-semibold">{t.consent.title}</h2>
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
              onChange={(e) => dispatch({ type: "TOGGLE_CONSENT", accepted: e.target.checked })}
              className="mt-1"
            />
            <span>{t.consent.checkbox}</span>
          </label>
          <button
            type="button"
            disabled={!state.accepted}
            onClick={() => dispatch({ type: "CONTINUE" })}
            className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-40"
          >
            {t.consent.continue}
          </button>
        </section>
      )}

      {state.step === "camera_permission" && (
        <section className="flex flex-col gap-3 rounded border p-4">
          <h2 className="text-lg font-semibold">{t.camera.title}</h2>
          <p>{t.camera.description}</p>
          <p role="status">{cameraMessage(state.problem)}</p>
          {state.problem !== null && (
            <button
              type="button"
              onClick={() => dispatch({ type: "CONTINUE" })}
              className="rounded bg-blue-600 px-4 py-2 text-white"
            >
              {t.camera.retry}
            </button>
          )}
        </section>
      )}

      {state.step === "framing" && (
        <section className="flex flex-col gap-3 rounded border p-4">
          <h2 className="text-lg font-semibold">{t.framing.title}</h2>
          <p>{t.framing.description}</p>
          <button
            type="button"
            onClick={() => dispatch({ type: "FRAMING_READY" })}
            className="rounded bg-green-600 px-4 py-2 text-white"
          >
            {t.framing.ready}
          </button>
        </section>
      )}

      {state.step === "quality_check" && <p role="status">{t.checking}</p>}
      {state.step === "creating_session" && <p role="status">{t.creating}</p>}

      {state.step === "flash_challenge" && !flashing && (
        <section className="flex flex-col gap-3 rounded border p-4">
          <h2 className="text-lg font-semibold">{t.flash.title}</h2>
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
            onClick={() => abortRef.current?.abort()}
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
          <h2 className="text-lg font-semibold">{t.result.retryTitle}</h2>
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
          <h2 className="text-lg font-semibold">{t.voice.title}</h2>
          <p className="text-sm opacity-70">{t.voice.promptLabel}</p>
          <p className="text-xl font-medium">{state.prompt}</p>
          {state.rereadsLeft !== null && (
            <p>
              {t.voice.attemptsLeft}: {state.rereadsLeft}
            </p>
          )}
          <p>{t.voice.pending}</p>
          {IS_DEV && (
            <button
              type="button"
              disabled={state.sending}
              onClick={sendDevVoice}
              className="rounded border px-4 py-2 disabled:opacity-40"
            >
              {state.sending ? t.voice.sending : t.voice.devSend}
            </button>
          )}
          <button
            type="button"
            onClick={() => dispatch({ type: "RESTART" })}
            className="rounded border px-4 py-2"
          >
            {t.errors.restart}
          </button>
        </section>
      )}

      {state.step === "result" && state.outcome === "pass" && (
        <section className="flex flex-col gap-2 rounded border p-4" role="status">
          <h2 className="text-lg font-semibold">{t.result.passTitle}</h2>
          <p>{t.result.passBody}</p>
        </section>
      )}

      {state.step === "result" && state.outcome === "review" && (
        <section className="flex flex-col gap-2 rounded border p-4" role="status">
          <h2 className="text-lg font-semibold">{t.result.reviewTitle}</h2>
          <p>{t.result.reviewBody}</p>
        </section>
      )}

      {state.step === "error" && (
        <section className="flex flex-col gap-3 rounded border border-red-300 p-4" role="alert">
          <h2 className="text-lg font-semibold">{t.errors.title}</h2>
          <p>{errorMessage(state.kind)}</p>
          <button
            type="button"
            onClick={() => dispatch({ type: "RESTART" })}
            className="rounded bg-blue-600 px-4 py-2 text-white"
          >
            {t.errors.restart}
          </button>
        </section>
      )}
    </div>
  );
}
