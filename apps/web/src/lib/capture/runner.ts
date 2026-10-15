// Các bước gọi API của luồng /verify. Mỗi hàm trả MỘT sự kiện cho `reduce` (flow.ts) và không bao giờ ném lỗi:
// mọi lỗi (ApiError, mất mạng/CORS, phản hồi sai dạng) đều thành sự kiện FAILED, không bao giờ thành "đạt".
// Gọi API chỉ qua src/lib/api/client.ts.

import type { ApiClient, CreateSessionResponse, Signals } from "@/lib/api/client";

import { type FlowEvent, type SessionInfo, classifyError, sessionExpired } from "./flow";

export type RunnerDeps = {
  client: ApiClient;
  /** Đồng hồ treo tường (ms) để so với `expires_at` do máy chủ gửi; không dùng để đo độ trễ. */
  nowMs: () => number;
};

/** Dữ liệu gửi lên ở bước uploading. TẠM — CAP-06 thay bằng ảnh/video chụp thật tại `capture_at_ms`. */
export type UploadPayload = {
  image: Blob;
  signals: Signals;
  video?: Blob;
};

function toSession(res: CreateSessionResponse): SessionInfo | null {
  const challenge = res?.challenge;
  const ok =
    typeof res?.session_id === "string" &&
    typeof res?.token === "string" &&
    typeof res?.expires_at === "string" &&
    typeof challenge?.challenge_id === "string" &&
    Array.isArray(challenge?.color_sequence) &&
    challenge.color_sequence.length > 0;
  if (!ok) return null;
  return {
    sessionId: res.session_id,
    token: res.token,
    tokenExpiresAt: res.expires_at,
    challenge,
  };
}

/** Tạo phiên mới (gọi ngay trước bước nháy màu để thử thách 120 giây còn mới). */
export async function startSession(deps: RunnerDeps, scenario?: string): Promise<FlowEvent> {
  try {
    const session = toSession(await deps.client.createSession(scenario));
    return session ? { type: "SESSION_CREATED", session } : { type: "FAILED", kind: "unexpected" };
  } catch (error) {
    return { type: "FAILED", kind: classifyError(error) };
  }
}

/**
 * Gửi media → signals → finalize. Phiên hoặc thử thách đã hết hạn thì KHÔNG gửi gì và trả EXPIRED
 * (quay về bước tạo phiên mới). Dừng ngay ở lỗi đầu tiên.
 */
export async function uploadAndFinalize(
  deps: RunnerDeps,
  session: SessionInfo,
  payload: UploadPayload,
): Promise<FlowEvent> {
  if (sessionExpired(session, deps.nowMs())) return { type: "EXPIRED" };
  const { client } = deps;
  try {
    await client.uploadMedia(session.sessionId, session.token, payload.image, payload.video);
    await client.sendSignals(session.sessionId, session.token, payload.signals);
    const response = await client.finalize(session.sessionId, session.token);
    return { type: "FINALIZE_RESULT", response };
  } catch (error) {
    return { type: "FAILED", kind: classifyError(error) };
  }
}

/** Gửi câu đọc. TẠM — CAP-07 thay bằng ghi âm thật. */
export async function sendVoiceAnswer(
  deps: RunnerDeps,
  session: SessionInfo,
  audio: Blob,
  video?: Blob,
): Promise<FlowEvent> {
  try {
    const response = await deps.client.sendVoice(session.sessionId, session.token, audio, video);
    return { type: "VOICE_RESULT", response };
  } catch (error) {
    return { type: "FAILED", kind: classifyError(error) };
  }
}
