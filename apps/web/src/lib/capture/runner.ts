// Các bước gọi API của luồng /verify. Mỗi hàm trả MỘT sự kiện cho `reduce` (flow.ts) và không bao giờ ném lỗi:
// mọi lỗi (ApiError, mất mạng/CORS, phản hồi sai dạng) đều thành sự kiện FAILED, không bao giờ thành "đạt".
// Gọi API chỉ qua src/lib/api/client.ts.
//
// Mọi sự kiện mang `run` (mã lần chạy) để reducer bỏ qua kết quả muộn của lần chạy cũ. Hết hạn tính trên
// đồng hồ đơn điệu `monoMs` (performance.now()), không so với giờ máy.

import type { ApiClient, CreateSessionResponse, Signals } from "@/lib/api/client";

import {
  type FlowEvent,
  type SessionInfo,
  classifyError,
  isValidIsoDate,
  sessionExpired,
} from "./flow";

export type RunnerDeps = {
  client: ApiClient;
  /** Đồng hồ đơn điệu (ms), thường là `performance.now()`. KHÔNG phải giờ treo tường. */
  monoMs: () => number;
};

/** Dữ liệu gửi lên ở bước uploading: ảnh JPEG thật, tín hiệu (có camprobe) và video webm nếu ghi được. */
export type UploadPayload = {
  image: Blob;
  signals: Signals;
  video?: Blob;
};

/** Mỗi lời gọi biết lần chạy của nó và có thể bị hủy (rời trang). */
export type CallContext = { run: number; signal?: AbortSignal };

function failed(error: unknown, ctx: CallContext): FlowEvent {
  // Bị hủy do rời trang: không phải lỗi mạng.
  if (ctx.signal?.aborted) return { type: "FAILED", kind: "interrupted", run: ctx.run };
  return { type: "FAILED", kind: classifyError(error), run: ctx.run };
}

/**
 * Phản hồi tạo phiên → SessionInfo, hoặc null nếu thiếu/sai dạng. `expires_at` chỉ được kiểm là mốc ISO
 * đọc được (phản hồi hỏng bị từ chối); KHÔNG dùng để so với giờ máy.
 */
function toSession(
  res: CreateSessionResponse,
  ctx: CallContext,
  issuedAtMono: number,
): SessionInfo | null {
  const challenge = res?.challenge;
  const ok =
    typeof res?.session_id === "string" &&
    typeof res?.token === "string" &&
    isValidIsoDate(res?.expires_at) &&
    typeof challenge?.challenge_id === "string" &&
    Array.isArray(challenge?.color_sequence) &&
    challenge.color_sequence.length > 0 &&
    (challenge.expires_at == null || isValidIsoDate(challenge.expires_at));
  if (!ok) return null;
  return {
    sessionId: res.session_id,
    token: res.token,
    challenge,
    run: ctx.run,
    tokenIssuedAtMono: issuedAtMono,
    challengeIssuedAtMono: issuedAtMono,
    expiredStreak: 0, // reducer ghi đè theo chuỗi hết hạn hiện tại
  };
}

/** Tạo phiên mới (gọi ngay trước bước nháy màu để thử thách 120 giây còn mới). */
export async function startSession(
  deps: RunnerDeps,
  ctx: CallContext,
  scenario?: string,
): Promise<FlowEvent> {
  // Mốc TRƯỚC khi gửi yêu cầu: máy chủ cấp sau mốc này nên hết hạn phía web luôn sớm hơn hoặc bằng máy chủ.
  const requestedAt = deps.monoMs();
  try {
    const res = await deps.client.createSession(scenario, ctx.signal);
    const session = toSession(res, ctx, requestedAt);
    // Phản hồi hỏng (thiếu trường, `expires_at` sai dạng) coi như phiên không dùng được.
    return session
      ? { type: "SESSION_CREATED", session }
      : { type: "FAILED", kind: "session", run: ctx.run };
  } catch (error) {
    return failed(error, ctx);
  }
}

/**
 * Gửi media → signals → finalize. Phiên hoặc thử thách đã hết hạn thì KHÔNG gửi gì và trả EXPIRED
 * (quay về bước tạo phiên mới). Dừng ngay ở lỗi đầu tiên hoặc khi bị hủy giữa các bước.
 */
export async function uploadAndFinalize(
  deps: RunnerDeps,
  session: SessionInfo,
  payload: UploadPayload,
  signal?: AbortSignal,
): Promise<FlowEvent> {
  const ctx: CallContext = { run: session.run, signal };
  if (sessionExpired(session, deps.monoMs())) return { type: "EXPIRED", run: session.run };
  const { client } = deps;
  try {
    await client.uploadMedia(
      session.sessionId,
      session.token,
      payload.image,
      payload.video,
      signal,
    );
    if (signal?.aborted) return failed(null, ctx);
    await client.sendSignals(session.sessionId, session.token, payload.signals, signal);
    if (signal?.aborted) return failed(null, ctx);
    const requestedAtMono = deps.monoMs(); // thử thách mới (nếu retry) được cấp sau mốc này
    const response = await client.finalize(session.sessionId, session.token, signal);
    return { type: "FINALIZE_RESULT", response, run: session.run, requestedAtMono };
  } catch (error) {
    return failed(error, ctx);
  }
}

/** Gửi câu đọc: WAV 16 kHz ghi thật (voiceRecorder.ts) và video nếu có. */
export async function sendVoiceAnswer(
  deps: RunnerDeps,
  session: SessionInfo,
  audio: Blob,
  video?: Blob,
  signal?: AbortSignal,
): Promise<FlowEvent> {
  const ctx: CallContext = { run: session.run, signal };
  try {
    const response = await deps.client.sendVoice(
      session.sessionId,
      session.token,
      audio,
      video,
      signal,
    );
    return { type: "VOICE_RESULT", response, run: session.run };
  } catch (error) {
    return failed(error, ctx);
  }
}
