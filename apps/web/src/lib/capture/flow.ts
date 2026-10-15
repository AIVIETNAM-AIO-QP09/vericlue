// Máy trạng thái của luồng /verify. Logic thuần: không DOM, không gọi API, không đọc đồng hồ.
// UI (VerifyFlow.tsx) gửi sự kiện vào `reduce`; việc gọi API nằm ở `runner.ts`.
//
// Luật cứng (AGENTS.md §6):
//  - chỉ `status === "pass"` của API mới thành kết quả "đạt";
//  - mọi lỗi (mạng, 401, 409, 413, 422, 5xx, phản hồi lạ) đi tới `error`, không bao giờ thành "đạt";
//  - người dân không thấy điểm số hay chữ "giả mạo"; gợi ý chụp lại chỉ nói về chất lượng.

import type { ApiError, Challenge, FinalizeResponse, VoiceResponse } from "@/lib/api/client";

// ---------------------------------------------------------------------------------------------
// Kiểu dữ liệu

export const RETRY_HINTS = [
  "MORE_LIGHT",
  "MOVE_CLOSER",
  "MOVE_BACK",
  "FACE_CENTER",
  "HOLD_STILL",
  "QUIET_PLACE",
  "BRIGHTNESS_UP",
] as const satisfies readonly NonNullable<FinalizeResponse["retry_hint"]>[];
export type RetryHint = (typeof RETRY_HINTS)[number];

export type ErrorKind =
  | "network"
  | "session"
  | "conflict"
  | "tooLarge"
  | "invalid"
  | "server"
  | "unexpected"
  | "stopped"
  | "interrupted";

export type CameraProblem = "denied" | "unavailable" | "insecure";

/** Thông tin phiên giữ trong bộ nhớ (token KHÔNG được lưu ra localStorage hay log). */
export type SessionInfo = {
  sessionId: string;
  token: string;
  /** Hạn của token (ISO), tách khỏi hạn của thử thách. */
  tokenExpiresAt: string;
  challenge: Challenge;
};

export type FlowState =
  | { step: "consent"; accepted: boolean }
  | { step: "camera_permission"; problem: CameraProblem | null }
  | { step: "framing" }
  | { step: "quality_check" }
  | { step: "creating_session" }
  | { step: "flash_challenge"; session: SessionInfo }
  | { step: "uploading"; session: SessionInfo }
  | { step: "retry"; session: SessionInfo; hint: RetryHint | null; attemptsLeft: number | null }
  | {
      step: "voice_challenge";
      session: SessionInfo;
      prompt: string;
      rereadsLeft: number | null;
      sending: boolean;
    }
  | { step: "result"; outcome: "pass" | "review" }
  | { step: "error"; kind: ErrorKind };

export type FlowEvent =
  | { type: "TOGGLE_CONSENT"; accepted: boolean }
  | { type: "CONTINUE" }
  | { type: "CAMERA_GRANTED" }
  | { type: "CAMERA_FAILED"; problem: CameraProblem }
  | { type: "FRAMING_READY" }
  | { type: "QUALITY_PASSED" }
  | { type: "SESSION_CREATED"; session: SessionInfo }
  | { type: "FLASH_DONE" }
  | { type: "FLASH_STOPPED" }
  | { type: "FLASH_INTERRUPTED" }
  /** Thử thách hoặc phiên đã hết hạn: không gửi dữ liệu cũ, quay về tạo phiên mới. */
  | { type: "EXPIRED" }
  | { type: "FINALIZE_RESULT"; response: unknown }
  | { type: "RETRY_CONTINUE" }
  | { type: "VOICE_SENDING" }
  | { type: "VOICE_RESULT"; response: unknown }
  | { type: "FAILED"; kind: ErrorKind }
  | { type: "RESTART" };

export const initialState: FlowState = { step: "consent", accepted: false };

// ---------------------------------------------------------------------------------------------
// Phân loại lỗi

/** Đổi lỗi bất kỳ (ApiError, TypeError do mất mạng/CORS, ...) thành loại lỗi hiển thị. */
export function classifyError(error: unknown): ErrorKind {
  if (isApiError(error)) {
    const { status } = error;
    if (status === 401) return "session";
    if (status === 409) return "conflict";
    if (status === 413) return "tooLarge";
    if (status === 422) return "invalid";
    if (status >= 500) return "server";
    return "unexpected";
  }
  // fetch ném TypeError khi mất mạng, CORS hỏng hoặc máy chủ tắt.
  return "network";
}

function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === "object" &&
    error !== null &&
    (error as { name?: unknown }).name === "ApiError" &&
    typeof (error as { status?: unknown }).status === "number"
  );
}

// ---------------------------------------------------------------------------------------------
// Kiểm phản hồi API lúc chạy (cast kiểu ở client.ts không kiểm gì)

function isRetryHint(value: unknown): value is RetryHint {
  return typeof value === "string" && (RETRY_HINTS as readonly string[]).includes(value);
}

function isColorStep(step: unknown): boolean {
  if (typeof step !== "object" || step === null) return false;
  const s = step as { rgb?: unknown; hold_ms?: unknown; transition_ms?: unknown };
  return (
    typeof s.rgb === "string" && Number.isFinite(s.hold_ms) && Number.isFinite(s.transition_ms)
  );
}

function isChallenge(value: unknown): value is Challenge {
  if (typeof value !== "object" || value === null) return false;
  const seq = (value as { color_sequence?: unknown }).color_sequence;
  return (
    typeof (value as { challenge_id?: unknown }).challenge_id === "string" &&
    Array.isArray(seq) &&
    seq.length > 0 &&
    seq.every(isColorStep)
  );
}

function asNumberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function statusOf(response: unknown): string | null {
  if (typeof response !== "object" || response === null) return null;
  const status = (response as { status?: unknown }).status;
  return typeof status === "string" ? status : null;
}

/** Gợi ý lạ hoặc thiếu thì dùng câu chung (null), không để lọt giá trị không kiểm soát lên màn hình. */
export function normalizeHint(value: unknown): RetryHint | null {
  return isRetryHint(value) ? value : null;
}

// ---------------------------------------------------------------------------------------------
// Reducer

const error = (kind: ErrorKind): FlowState => ({ step: "error", kind });

export function reduce(state: FlowState, event: FlowEvent): FlowState {
  // Lỗi và bắt đầu lại hợp lệ ở mọi bước.
  if (event.type === "FAILED") return error(event.kind);
  if (event.type === "RESTART") return { step: "framing" };

  switch (state.step) {
    case "consent":
      if (event.type === "TOGGLE_CONSENT") return { step: "consent", accepted: event.accepted };
      // Chỉ đi tiếp khi người dùng đã tự tích đồng ý (không bao giờ tích sẵn).
      if (event.type === "CONTINUE" && state.accepted) {
        return { step: "camera_permission", problem: null };
      }
      return state;

    case "camera_permission":
      if (event.type === "CAMERA_GRANTED") return { step: "framing" };
      if (event.type === "CAMERA_FAILED")
        return { step: "camera_permission", problem: event.problem };
      if (event.type === "CONTINUE") return { step: "camera_permission", problem: null };
      return state;

    case "framing":
      if (event.type === "FRAMING_READY") return { step: "quality_check" };
      return state;

    case "quality_check":
      // TẠM — CAP-02 thay bằng cổng chất lượng thật (MediaPipe).
      if (event.type === "QUALITY_PASSED") return { step: "creating_session" };
      return state;

    case "creating_session":
      if (event.type === "SESSION_CREATED")
        return { step: "flash_challenge", session: event.session };
      return state;

    case "flash_challenge":
      if (event.type === "FLASH_DONE") return { step: "uploading", session: state.session };
      if (event.type === "FLASH_STOPPED") return error("stopped");
      if (event.type === "FLASH_INTERRUPTED") return error("interrupted");
      if (event.type === "EXPIRED") return { step: "creating_session" };
      return state;

    case "uploading":
      if (event.type === "EXPIRED") return { step: "creating_session" };
      if (event.type === "FINALIZE_RESULT") return fromFinalize(state.session, event.response);
      return state;

    case "retry":
      if (event.type === "EXPIRED") return { step: "creating_session" };
      if (event.type === "RETRY_CONTINUE")
        return { step: "flash_challenge", session: state.session };
      return state;

    case "voice_challenge":
      if (event.type === "VOICE_SENDING") return { ...state, sending: true };
      if (event.type === "VOICE_RESULT") return fromVoice(state, event.response);
      return state;

    case "result":
    case "error":
      return state;
  }
}

/** Kết quả finalize → trạng thái. Chỉ `pass` mới là đạt; thiếu dữ liệu cần thiết hoặc status lạ → lỗi. */
function fromFinalize(session: SessionInfo, response: unknown): FlowState {
  const status = statusOf(response);
  const r = response as Partial<FinalizeResponse>;
  switch (status) {
    case "pass":
      return { step: "result", outcome: "pass" };
    case "review":
      return { step: "result", outcome: "review" };
    case "retry": {
      // Lượt chụp lại bắt buộc có thử thách MỚI của máy chủ; thiếu thì không thể tiếp tục.
      if (!isChallenge(r.challenge)) return error("unexpected");
      return {
        step: "retry",
        session: { ...session, challenge: r.challenge },
        hint: normalizeHint(r.retry_hint),
        attemptsLeft: asNumberOrNull(r.attempts_left),
      };
    }
    case "voice_challenge": {
      const prompt = typeof r.voice_prompt === "string" ? r.voice_prompt.trim() : "";
      if (!prompt) return error("unexpected"); // web không tự đặt câu đọc
      return {
        step: "voice_challenge",
        session,
        prompt,
        rereadsLeft: asNumberOrNull(r.attempts_left),
        sending: false,
      };
    }
    default:
      return error("unexpected");
  }
}

function fromVoice(
  state: Extract<FlowState, { step: "voice_challenge" }>,
  response: unknown,
): FlowState {
  const status = statusOf(response);
  const r = response as Partial<VoiceResponse>;
  switch (status) {
    case "pass":
      return { step: "result", outcome: "pass" };
    case "review":
      return { step: "result", outcome: "review" };
    case "voice_challenge": {
      const prompt = typeof r.voice_prompt === "string" ? r.voice_prompt.trim() : "";
      if (!prompt) return error("unexpected");
      return {
        ...state,
        prompt,
        rereadsLeft: asNumberOrNull(r.attempts_left),
        sending: false,
      };
    }
    default:
      return error("unexpected");
  }
}

// ---------------------------------------------------------------------------------------------
// Hạn thử thách / phiên

/** Hạn (ISO) đã qua hoặc không đọc được → coi là hết hạn (không bao giờ gửi dữ liệu cũ). */
export function isExpired(expiresAt: string | null | undefined, nowMs: number): boolean {
  if (!expiresAt) return false; // thiếu hạn: để máy chủ quyết định
  const t = Date.parse(expiresAt);
  return Number.isNaN(t) || t <= nowMs;
}

/** Phiên dùng được khi cả token lẫn thử thách chưa hết hạn. */
export function sessionExpired(session: SessionInfo, nowMs: number): boolean {
  return isExpired(session.tokenExpiresAt, nowMs) || isExpired(session.challenge.expires_at, nowMs);
}
