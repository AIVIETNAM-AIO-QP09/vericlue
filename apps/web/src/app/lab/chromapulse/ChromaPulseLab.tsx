"use client";

// Trang thử ChromaPulse (CAP-03). Chỉ dùng nội bộ: không gọi API phiên, không lưu gì lên máy chủ.
// Mọi logic đo nằm trong src/lib/capture/chromapulse/; file này chỉ nối giao diện với logic đó.

import { useCallback, useEffect, useRef, useState } from "react";

import { assembleRecord } from "@/lib/capture/chromapulse/assemble";
import {
  collectDeviceInfo,
  detectBrowser,
  openFrontCamera,
  readCameraSettings,
} from "@/lib/capture/chromapulse/device";
import { createLandmarker, type LandmarkerHandle } from "@/lib/capture/chromapulse/landmarker";
import {
  SCENARIOS,
  type LabRecord,
  type Scenario,
  buildFileName,
  recordProblems,
  serializeRecord,
} from "@/lib/capture/chromapulse/record";
import { createFrameSampler, type FrameSampler } from "@/lib/capture/chromapulse/sampler";
import { generateSequence } from "@/lib/capture/chromapulse/sequence";
import { runTrial, supportsFrameCallback } from "@/lib/capture/chromapulse/trial";
import { vi } from "@/i18n/vi";

const t = vi.lab.chromapulse;
const COUNTDOWN_SECONDS = 3;
const REGION_COLORS: Record<string, string> = {
  forehead: "#22c55e",
  left_cheek: "#3b82f6",
  right_cheek: "#a855f7",
  nose: "#f59e0b",
  chin: "#ef4444",
  background: "#06b6d4",
};

type Stage = "intro" | "loading" | "ready" | "countdown" | "running" | "done" | "error";
type Result = { record: LabRecord; problems: string[]; fileName: string; aborted: boolean };

export function ChromaPulseLab() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const colorRef = useRef<HTMLDivElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const handleRef = useRef<LandmarkerHandle | null>(null);
  const samplerRef = useRef<FrameSampler | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const previewOn = useRef(false);
  const showRegionsRef = useRef(true);

  const [stage, setStage] = useState<Stage>("intro");
  const [accepted, setAccepted] = useState(false);
  const [deviceLabel, setDeviceLabel] = useState("");
  const [scenario, setScenario] = useState<Scenario>("real");
  const [take, setTake] = useState(1);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [faceFound, setFaceFound] = useState(false);
  const [delegate, setDelegate] = useState<string | null>(null);
  const [captureTimeSeen, setCaptureTimeSeen] = useState<boolean | null>(null);
  const [showRegions, setShowRegions] = useState(true);
  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    showRegionsRef.current = showRegions;
  }, [showRegions]);

  const stopCamera = useCallback(() => {
    previewOn.current = false;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    handleRef.current?.landmarker.close();
    handleRef.current = null;
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  // Vòng xem trước: cập nhật "thấy mặt", captureTime và lớp phủ các vùng đo.
  const startPreview = useCallback(() => {
    const video = videoRef.current;
    const sampler = samplerRef.current;
    if (!video || !sampler || !supportsFrameCallback(video)) return;
    previewOn.current = true;
    let lastFace = false;
    const loop = (_now: number, metadata: VideoFrameCallbackMetadata) => {
      if (!previewOn.current) return;
      const sample = sampler.sample(video);
      if (sample.faceFound !== lastFace) {
        lastFace = sample.faceFound;
        setFaceFound(sample.faceFound);
      }
      if ("captureTime" in metadata) setCaptureTimeSeen(true);
      else setCaptureTimeSeen((prev) => prev ?? false);
      drawOverlay(overlayRef.current, sample, showRegionsRef.current);
      video.requestVideoFrameCallback(loop);
    };
    video.requestVideoFrameCallback(loop);
  }, []);

  const begin = useCallback(async () => {
    setStage("loading");
    setError(null);
    try {
      if (!window.isSecureContext) throw new Error(t.httpsHint);
      const [stream, handle] = await Promise.all([openFrontCamera(), createLandmarker()]);
      streamRef.current = stream;
      handleRef.current = handle;
      setDelegate(handle.delegate);
      samplerRef.current = createFrameSampler(handle.landmarker);
      const video = videoRef.current;
      if (!video) throw new Error("Không có phần tử video");
      video.srcObject = stream;
      await video.play();
      if (!supportsFrameCallback(video)) throw new Error(t.noFrameCallback);
      setStage("ready");
      startPreview();
    } catch (e) {
      stopCamera();
      const detail = e instanceof Error ? e.message : String(e);
      setError(`${detail}\n${t.assetsHint}`);
      setStage("error");
    }
  }, [startPreview, stopCamera]);

  const run = useCallback(async () => {
    const video = videoRef.current;
    const sampler = samplerRef.current;
    const stream = streamRef.current;
    if (!video || !sampler || !stream) return;

    setStage("countdown");
    for (let s = COUNTDOWN_SECONDS; s > 0; s -= 1) {
      setCountdown(s);
      await new Promise((r) => setTimeout(r, 1000)); // chỉ để đếm ngược trên giao diện, không dùng để đo
    }
    previewOn.current = false;
    abortRef.current = new AbortController();
    setStage("running");

    let wakeLock: WakeLockSentinel | null = null;
    try {
      wakeLock = (await navigator.wakeLock?.request("screen")) ?? null;
    } catch {
      wakeLock = null; // không bắt buộc
    }

    const steps = generateSequence();
    const trial = await runTrial({
      video,
      sampler,
      steps,
      signal: abortRef.current.signal,
      onColor: (rgb) => {
        if (colorRef.current) colorRef.current.style.backgroundColor = `rgb(${rgb.join(",")})`;
      },
      onProgress: (elapsed, total) => {
        if (progressRef.current) progressRef.current.style.width = `${(elapsed / total) * 100}%`;
      },
    });
    await wakeLock?.release().catch(() => undefined);

    const track = stream.getVideoTracks()[0] ?? null;
    const device = collectDeviceInfo(deviceLabel.trim() || "may", track);
    const record = assembleRecord({
      scenario,
      take,
      note,
      createdAt: new Date().toISOString(),
      device,
      cameraSettings: readCameraSettings(track),
      steps,
      trial,
      delegate: handleRef.current?.delegate ?? null,
      hasFrameCallback: supportsFrameCallback(video),
    });
    const fileName = buildFileName({
      device: device.label,
      browser: detectBrowser(device.user_agent),
      scenario,
      take,
    });
    setResult({ record, problems: recordProblems(record), fileName, aborted: trial.aborted });
    setStage("done");
  }, [deviceLabel, note, scenario, take]);

  const download = useCallback(() => {
    if (!result) return;
    const blob = new Blob([serializeRecord(result.record)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = result.fileName;
    a.click();
    URL.revokeObjectURL(url);
  }, [result]);

  const again = useCallback(
    (nextTake: boolean) => {
      if (nextTake) setTake((n) => n + 1);
      setResult(null);
      setStage("ready");
      startPreview();
    },
    [startPreview],
  );

  const showVideo = stage === "ready" || stage === "countdown";
  const canStart = accepted && deviceLabel.trim().length > 0;

  return (
    <div className="flex flex-col gap-4">
      {(stage === "intro" || stage === "error") && (
        <section className="flex flex-col gap-3 rounded border p-4">
          <h2 className="font-semibold">{t.privacyTitle}</h2>
          <p>{t.privacy}</p>
          <h2 className="font-semibold">{t.warningTitle}</h2>
          <p>{t.warning}</p>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={accepted}
              onChange={(e) => setAccepted(e.target.checked)}
            />
            {t.accept}
          </label>
          <label className="flex flex-col gap-1">
            {t.deviceLabel}
            <input
              className="rounded border px-2 py-1 text-black"
              value={deviceLabel}
              onChange={(e) => setDeviceLabel(e.target.value)}
            />
          </label>
          <button
            type="button"
            disabled={!canStart}
            onClick={begin}
            className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-40"
          >
            {t.loadStart}
          </button>
          {error ? (
            <pre className="whitespace-pre-wrap text-red-600">{`${t.loadError}: ${error}`}</pre>
          ) : null}
        </section>
      )}

      {stage === "loading" && <p>{t.loading}</p>}

      <div className={showVideo ? "relative w-full max-w-md" : "hidden"}>
        {/* Video luôn có trong DOM để nhận khung; lớp phủ vẽ các vùng đo (không lưu). */}
        <video ref={videoRef} playsInline muted className="w-full -scale-x-100 rounded" />
        <canvas
          ref={overlayRef}
          className="pointer-events-none absolute inset-0 h-full w-full -scale-x-100"
        />
      </div>

      {stage === "ready" && (
        <section className="flex flex-col gap-3 rounded border p-4">
          <p>
            {faceFound ? t.faceFound : t.faceNotFound} · {t.delegate}: {delegate} · {t.captureTime}:{" "}
            {captureTimeSeen === null ? "…" : captureTimeSeen ? t.captureTimeYes : t.captureTimeNo}
          </p>
          <p>{t.brightnessHint}</p>
          <label className="flex flex-col gap-1">
            {t.scenarioLabel}
            <select
              className="rounded border px-2 py-1 text-black"
              value={scenario}
              onChange={(e) => setScenario(e.target.value as Scenario)}
            >
              {SCENARIOS.map((s) => (
                <option key={s} value={s}>
                  {t.scenarios[s]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            {t.takeLabel}
            <input
              type="number"
              min={1}
              className="rounded border px-2 py-1 text-black"
              value={take}
              onChange={(e) => setTake(Math.max(1, Number(e.target.value) || 1))}
            />
          </label>
          <label className="flex flex-col gap-1">
            {t.noteLabel}
            <input
              className="rounded border px-2 py-1 text-black"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={showRegions}
              onChange={(e) => setShowRegions(e.target.checked)}
            />
            {t.showRegions}
          </label>
          <button type="button" onClick={run} className="rounded bg-green-600 px-4 py-2 text-white">
            {t.start}
          </button>
        </section>
      )}

      {stage === "countdown" && (
        <p className="text-center text-2xl">
          {t.countdown} {countdown}
        </p>
      )}

      {/* Màn hình nháy màu: phủ toàn bộ trang trong lúc chạy. */}
      <div
        ref={colorRef}
        className={
          stage === "running" ? "fixed inset-0 z-50 flex items-end justify-center" : "hidden"
        }
        style={{ backgroundColor: "#d1d1d1" }}
      >
        <div className="mb-6 flex w-full max-w-sm flex-col gap-2 px-4">
          <div className="h-1 w-full bg-black/20">
            <div ref={progressRef} className="h-1 bg-black/50" style={{ width: "0%" }} />
          </div>
          <button
            type="button"
            onClick={() => abortRef.current?.abort()}
            className="rounded bg-black/60 px-4 py-2 text-white"
          >
            {t.stop}
          </button>
        </div>
      </div>

      {stage === "done" && result && (
        <section className="flex flex-col gap-3 rounded border p-4">
          <h2 className="font-semibold">{t.doneTitle}</h2>
          {result.aborted ? <p className="text-amber-600">{t.aborted}</p> : null}
          <ul className="list-disc pl-5">
            <li>
              {t.framesSummary}: {result.record.frame_times.length}
            </li>
            <li>
              {t.faceSummary}: {result.record.frame_times.filter((f) => f.face_found).length}
            </li>
            <li>
              {t.colorsSummary}: {result.record.color_events.length}
            </li>
            <li>
              {t.captureTime}:{" "}
              {result.record.support.has_capture_time ? t.captureTimeYes : t.captureTimeNo}
            </li>
            <li>
              {t.fileName}: {result.fileName}
            </li>
          </ul>
          <h3 className="font-semibold">{t.problemsTitle}</h3>
          {result.problems.length ? (
            <ul className="list-disc pl-5">
              {result.problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          ) : (
            <p>{t.noProblems}</p>
          )}
          <button
            type="button"
            onClick={download}
            className="rounded bg-blue-600 px-4 py-2 text-white"
          >
            {t.download}
          </button>
          <div className="flex gap-2">
            <button type="button" onClick={() => again(false)} className="rounded border px-4 py-2">
              {t.again}
            </button>
            <button type="button" onClick={() => again(true)} className="rounded border px-4 py-2">
              {t.nextTake}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

function drawOverlay(
  canvas: HTMLCanvasElement | null,
  sample: ReturnType<FrameSampler["sample"]>,
  enabled: boolean,
) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  if (canvas.width !== sample.canvasWidth || canvas.height !== sample.canvasHeight) {
    canvas.width = sample.canvasWidth;
    canvas.height = sample.canvasHeight;
  }
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!enabled) return;
  ctx.lineWidth = 2;
  for (const [name, rects] of Object.entries(sample.rects)) {
    ctx.strokeStyle = REGION_COLORS[name] ?? "#fff";
    for (const r of rects ?? []) ctx.strokeRect(r.x, r.y, r.w, r.h);
  }
}
