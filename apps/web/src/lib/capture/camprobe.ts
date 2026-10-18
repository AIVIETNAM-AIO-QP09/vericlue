// CamProbe phía trình duyệt (CAP-05, ADR-0007): thu tín hiệu cho thấy camera bị thay thế hoặc can thiệp.
// Kết quả là object `camprobe` trong Signals (packages/contracts/schemas/session.schema.json);
// bộ chấm điểm nằm ở ml/src/vericlue_ml/presence/camprobe.py — hai phía PHẢI khớp tên trường dưới đây.
//
// Kỹ thuật kiểm tra hàm bị gán đè theo ý tưởng của CreepJS (MIT): so với bản gốc lấy từ <iframe> sạch.
// Mã ở đây viết lại, KHÔNG chép từ CreepJS nên không có vendor/ (third_party/README.md không đổi).
// Đây chỉ là MỘT lớp kiểm tra: kẻ tấn công có thể vá về sau (ADR-0007).

/** Một lần thăm dò `applyConstraints` trên bản sao của track. */
export type ConstraintProbe = {
  kind: "resolution";
  requested: { width: number; height: number };
  /** `applyConstraints` có thành công không (thiết bị không hỗ trợ thì false: KHÔNG phải bằng chứng can thiệp). */
  ok: boolean;
  /** Thời gian chờ `applyConstraints` (ms, performance.now). */
  apply_ms: number;
  settings_before: { width: number | null; height: number | null };
  settings_after: { width: number | null; height: number | null };
  /** `getSettings()` có phản ánh yêu cầu không. */
  settings_changed: boolean;
  /** Kích thước khung hình THẬT đo được sau khi áp dụng (videoWidth/videoHeight). */
  frame_size_after: { width: number; height: number } | null;
  /**
   * Kích thước khung thật có đổi theo yêu cầu không (so không phân biệt xoay dọc/ngang).
   * true = đã đổi. false = getSettings() báo ĐÃ đổi mà khung thật không đổi sau FRAME_SIZE_SETTLE_MS
   * (dấu hiệu giả thông số). null = không kết luận được (không đo được khung, hoặc khung chưa đổi
   * nhưng getSettings() cũng không đổi): KHÔNG phải bằng chứng.
   */
  frame_size_changed: boolean | null;
  /** Thời gian đã chờ khung đổi kích thước (ms); null nếu không chờ (applyConstraints bị từ chối). */
  frame_wait_ms: number | null;
};

export type CamProbe = {
  /** Mỗi cờ dạng "<api>:<lý do>", ví dụ "getUserMedia:non_native_tostring". */
  api_tamper_flags: string[];
  constraint_probes: ConstraintProbe[];
  device_label: string;
  track_settings: Record<string, unknown>;
  track_capabilities: Record<string, unknown>;
  /** Tỉ lệ cặp khung liên tiếp giống hệt nhau (0..1). Không có khóa này nếu không lấy được mẫu. */
  duplicate_frame_ratio?: number;
};

/** Số khung lấy mẫu để tính khung lặp. */
export const DUPLICATE_SAMPLE_FRAMES = 30;
/** Thời gian tối đa chờ lấy đủ mẫu khung (ms). */
export const DUPLICATE_SAMPLE_TIMEOUT_MS = 2500;
/** Thời gian tối đa chờ khung hình đổi kích thước sau applyConstraints (ms). */
export const FRAME_SIZE_SETTLE_MS = 1200;
/** Độ phân giải thăm dò, thử lần lượt; bỏ qua mốc trùng độ phân giải hiện tại. */
export const PROBE_RESOLUTIONS = [
  { width: 640, height: 480 },
  { width: 320, height: 240 },
] as const;
/** Tổng thời gian tối đa cho CamProbe (ms); quá hạn thì bỏ (thiếu tín hiệu → máy chủ ra "review"). */
export const CAMPROBE_TIMEOUT_MS = 8000;
/** Cạnh ảnh thu nhỏ dùng để so khung (px). */
const HASH_SIZE = 24;

type ProbeTarget = { label: string; read: (win: Window & typeof globalThis) => unknown };

/** Các hàm cần kiểm tra. `read` chạy trên cửa sổ hiện tại và trên <iframe> sạch. */
const TARGETS: readonly ProbeTarget[] = [
  { label: "getUserMedia", read: (w) => w.MediaDevices?.prototype?.getUserMedia },
  { label: "enumerateDevices", read: (w) => w.MediaDevices?.prototype?.enumerateDevices },
  { label: "getSettings", read: (w) => w.MediaStreamTrack?.prototype?.getSettings },
  { label: "getCapabilities", read: (w) => w.MediaStreamTrack?.prototype?.getCapabilities },
  { label: "applyConstraints", read: (w) => w.MediaStreamTrack?.prototype?.applyConstraints },
];

const NATIVE_CODE = /\{\s*\[native code\]\s*\}\s*$/;

function nativeToString(fn: unknown, toStringFn: (this: unknown) => string): string | null {
  try {
    return toStringFn.call(fn);
  } catch {
    return null;
  }
}

/**
 * Kiểm tra từng hàm camera: còn là hàm gốc không. Trả về danh sách cờ (rỗng = không thấy can thiệp).
 * `cleanWindow` là cửa sổ của <iframe> sạch; null thì bỏ qua phép so sánh với bản gốc.
 */
export function detectApiTampering(
  win: Window & typeof globalThis,
  cleanWindow: (Window & typeof globalThis) | null,
): string[] {
  const flags: string[] = [];
  // Dùng toString của cửa sổ sạch để không bị Function.prototype.toString đã vá của trang đánh lừa.
  const cleanToString = cleanWindow?.Function?.prototype?.toString ?? null;
  const pageToString = win.Function.prototype.toString;
  if (
    cleanToString &&
    nativeToString(pageToString, cleanToString) !== nativeToString(cleanToString, cleanToString)
  ) {
    // Hai bản toString khác nhau dạng chuỗi → toString của trang bị thay.
    flags.push("Function.toString:iframe_mismatch");
  }
  const toStringFn = cleanToString ?? pageToString;

  for (const { label, read } of TARGETS) {
    const fn = read(win);
    if (typeof fn !== "function") {
      // Chỉ là dấu hiệu khi bản gốc (iframe sạch) CÓ hàm này mà trang thì không. Trình duyệt cũ thiếu
      // hàm (ví dụ getCapabilities) thì cả hai cùng thiếu: không phải can thiệp.
      if (cleanWindow && typeof read(cleanWindow) === "function")
        flags.push(`${label}:not_function`);
      continue;
    }
    const text = nativeToString(fn, toStringFn);
    if (text === null || !NATIVE_CODE.test(text)) flags.push(`${label}:non_native_tostring`);
    // Hàm gốc của trình duyệt (phương thức WebIDL) không có thuộc tính `prototype`.
    if (Object.prototype.hasOwnProperty.call(fn, "prototype")) flags.push(`${label}:has_prototype`);
    const ownNames = Object.getOwnPropertyNames(fn).sort().join(",");
    if (ownNames !== "length,name") flags.push(`${label}:unexpected_own_properties`);
    if (cleanWindow) {
      const clean = read(cleanWindow);
      if (typeof clean === "function") {
        const cleanText = nativeToString(clean, toStringFn);
        const sameName = (fn as { name: string }).name === (clean as { name: string }).name;
        const sameLength =
          (fn as { length: number }).length === (clean as { length: number }).length;
        if (text !== cleanText || !sameName || !sameLength) flags.push(`${label}:iframe_mismatch`);
      }
    }
  }

  // Phương thức bị gán trực tiếp lên đối tượng thể hiện (thay vì prototype) là dấu hiệu gán đè.
  const md = win.navigator?.mediaDevices;
  if (md) {
    for (const name of ["getUserMedia", "enumerateDevices"] as const) {
      if (Object.prototype.hasOwnProperty.call(md, name))
        flags.push(`${name}:own_property_override`);
    }
  }
  return [...new Set(flags)];
}

/** Tạo <iframe> ẩn, cùng nguồn, để lấy bản hàm gốc. Trả về hàm dọn dẹp. */
function openCleanWindow(): { win: (Window & typeof globalThis) | null; dispose: () => void } {
  try {
    const iframe = document.createElement("iframe");
    iframe.style.display = "none";
    iframe.setAttribute("aria-hidden", "true");
    iframe.tabIndex = -1;
    document.body.appendChild(iframe);
    return {
      win: iframe.contentWindow as (Window & typeof globalThis) | null,
      dispose: () => iframe.remove(),
    };
  } catch {
    return { win: null, dispose: () => undefined };
  }
}

type Dimensions = { width: number | null; height: number | null };

function dimensionsOf(settings: MediaTrackSettings): Dimensions {
  return { width: settings.width ?? null, height: settings.height ?? null };
}

/** Hai kích thước bằng nhau, không phân biệt xoay dọc/ngang (điện thoại báo getSettings và khung lệch hướng). */
export function sameSize(
  a: { width: number | null; height: number | null },
  b: { width: number | null; height: number | null },
): boolean {
  if (a.width === null || a.height === null || b.width === null || b.height === null) return false;
  return (
    (a.width === b.width && a.height === b.height) || (a.width === b.height && a.height === b.width)
  );
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Chờ khung hình thật đổi sang kích thước mong muốn (tối đa FRAME_SIZE_SETTLE_MS). */
async function measureFrameSize(
  video: HTMLVideoElement,
  want: { width: number; height: number },
): Promise<{ size: { width: number; height: number } | null; waitedMs: number }> {
  const startedAt = performance.now();
  const deadline = startedAt + FRAME_SIZE_SETTLE_MS;
  let last: { width: number; height: number } | null = null;
  while (performance.now() < deadline) {
    if (video.videoWidth > 0 && video.videoHeight > 0) {
      last = { width: video.videoWidth, height: video.videoHeight };
      if (sameSize(last, want)) break;
    }
    await sleep(50);
  }
  return { size: last, waitedMs: Math.round(performance.now() - startedAt) };
}

/** Thăm dò `applyConstraints` bằng `exact`: thiết bị thật phải đổi cả getSettings() lẫn khung hình. */
export async function probeConstraints(
  track: MediaStreamTrack,
  video: HTMLVideoElement,
): Promise<ConstraintProbe[]> {
  const probes: ConstraintProbe[] = [];
  for (const requested of PROBE_RESOLUTIONS) {
    const before = dimensionsOf(track.getSettings());
    if (sameSize(before, requested)) continue;
    const startedAt = performance.now();
    let ok = true;
    try {
      await track.applyConstraints({
        width: { exact: requested.width },
        height: { exact: requested.height },
      });
    } catch {
      ok = false; // thiết bị không hỗ trợ độ phân giải này
    }
    const applyMs = performance.now() - startedAt;
    const after = dimensionsOf(track.getSettings());
    const settingsChanged = sameSize(after, requested);
    const measured = ok ? await measureFrameSize(video, requested) : null;
    const frame = measured?.size ?? null;
    const frameMatched = frame !== null && sameSize(frame, requested);
    probes.push({
      kind: "resolution",
      requested: { width: requested.width, height: requested.height },
      ok,
      apply_ms: Math.round(applyMs * 100) / 100,
      settings_before: before,
      settings_after: after,
      settings_changed: settingsChanged,
      frame_size_after: frame,
      // Chỉ false khi getSettings() báo đã đổi mà khung thật không đổi; còn lại không kết luận (null).
      frame_size_changed:
        frame === null ? null : frameMatched ? true : settingsChanged ? false : null,
      frame_wait_ms: measured?.waitedMs ?? null,
    });
  }
  return probes;
}

/** Dấu vân tay thô của một khung: ảnh xám HASH_SIZE×HASH_SIZE nối thành chuỗi. */
function frameFingerprint(video: HTMLVideoElement, context: CanvasRenderingContext2D): string {
  context.drawImage(video, 0, 0, HASH_SIZE, HASH_SIZE);
  const { data } = context.getImageData(0, 0, HASH_SIZE, HASH_SIZE);
  const gray: number[] = [];
  for (let i = 0; i < data.length; i += 4) {
    gray.push(Math.round(0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]));
  }
  return gray.join(",");
}

/** Tỉ lệ cặp khung liên tiếp giống hệt nhau; null nếu có ít hơn 2 mẫu. */
export function duplicateRatio(fingerprints: readonly string[]): number | null {
  if (fingerprints.length < 2) return null;
  let same = 0;
  for (let i = 1; i < fingerprints.length; i += 1)
    if (fingerprints[i] === fingerprints[i - 1]) same += 1;
  return same / (fingerprints.length - 1);
}

/** Lấy mẫu khung bằng requestVideoFrameCallback (mỗi khung mới một lần) và tính tỉ lệ lặp. */
export async function sampleDuplicateRatio(video: HTMLVideoElement): Promise<number | null> {
  if (typeof video.requestVideoFrameCallback !== "function") return null;
  const canvas = document.createElement("canvas");
  canvas.width = HASH_SIZE;
  canvas.height = HASH_SIZE;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return null;
  const prints: string[] = [];
  await new Promise<void>((resolve) => {
    const timeout = setTimeout(resolve, DUPLICATE_SAMPLE_TIMEOUT_MS);
    const onFrame = () => {
      try {
        prints.push(frameFingerprint(video, context));
      } catch {
        clearTimeout(timeout);
        resolve();
        return;
      }
      if (prints.length >= DUPLICATE_SAMPLE_FRAMES) {
        clearTimeout(timeout);
        resolve();
      } else {
        video.requestVideoFrameCallback(onFrame);
      }
    };
    video.requestVideoFrameCallback(onFrame);
  });
  return duplicateRatio(prints);
}

function hiddenVideoFor(stream: MediaStream): HTMLVideoElement {
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.setAttribute("aria-hidden", "true");
  // Không dùng display:none: iOS có thể ngừng cấp khung. Đặt ngoài màn hình, rất nhỏ.
  Object.assign(video.style, { position: "fixed", left: "-10000px", width: "2px", height: "2px" });
  video.srcObject = stream;
  document.body.appendChild(video);
  return video;
}

/**
 * Thu toàn bộ tín hiệu CamProbe từ luồng camera (không đổi track gốc: thăm dò chạy trên bản sao).
 * Có hạn `timeoutMs` và hủy được bằng `signal`; quá hạn hoặc bị hủy thì ném lỗi và TẮT bản sao track.
 */
export async function collectCamProbe(
  stream: MediaStream,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<CamProbe> {
  const track = stream.getVideoTracks()[0];
  if (!track) throw new Error("camprobe_no_video_track");
  if (options.signal?.aborted) throw new Error("camprobe_aborted");

  const clean = openCleanWindow();
  let apiFlags: string[] = [];
  try {
    apiFlags = detectApiTampering(window, clean.win);
  } finally {
    clean.dispose();
  }

  const probeTrack = track.clone();
  const video = hiddenVideoFor(new MediaStream([probeTrack]));
  const dispose = () => {
    probeTrack.stop();
    video.srcObject = null;
    video.remove();
  };

  let timer: ReturnType<typeof setTimeout> | undefined;
  let onAbort: (() => void) | undefined;
  const cutoff = new Promise<never>((_, reject) => {
    timer = setTimeout(
      () => reject(new Error("camprobe_timeout")),
      options.timeoutMs ?? CAMPROBE_TIMEOUT_MS,
    );
    onAbort = () => reject(new Error("camprobe_aborted"));
    options.signal?.addEventListener("abort", onAbort, { once: true });
  });
  const measure = (async () => {
    await video.play().catch(() => undefined);
    const duplicate = await sampleDuplicateRatio(video);
    const probes = await probeConstraints(probeTrack, video);
    return { duplicate, probes };
  })();
  measure.catch(() => undefined); // nếu `cutoff` thắng, lỗi muộn của phép đo không thành lỗi chưa xử lý

  let measured: Awaited<typeof measure>;
  try {
    measured = await Promise.race([measure, cutoff]);
  } finally {
    clearTimeout(timer);
    if (onAbort) options.signal?.removeEventListener("abort", onAbort);
    dispose();
  }

  const settings = { ...track.getSettings() } as Record<string, unknown>;
  // Bỏ định danh phần cứng ổn định: không cần cho chấm điểm.
  delete settings.deviceId;
  delete settings.groupId;
  const capabilities =
    typeof track.getCapabilities === "function"
      ? ({ ...track.getCapabilities() } as Record<string, unknown>)
      : {};
  delete capabilities.deviceId;
  delete capabilities.groupId;

  return {
    api_tamper_flags: apiFlags,
    constraint_probes: measured.probes,
    device_label: track.label,
    track_settings: settings,
    track_capabilities: capabilities,
    // Không gửi null: schema khai `number`; thiếu khóa nghĩa là không đo được.
    ...(measured.duplicate === null ? {} : { duplicate_frame_ratio: measured.duplicate }),
  };
}
