// Máy trạng thái của luồng /verify. Logic thuần: không DOM, không gọi API, không đọc đồng hồ.
// UI (VerifyFlow.tsx) gửi sự kiện vào `reduce`; việc gọi API nằm ở `runner.ts`.
//
// Luật cứng (AGENTS.md §6):
//  - chỉ `status === "pass"` của API mới thành kết quả "đạt";
//  - mọi lỗi (mạng, 401, 409, 413, 422, 5xx, phản hồi lạ) đi tới `error`, không bao giờ thành "đạt";
//  - người dân không thấy điểm số hay chữ "giả mạo"; gợi ý chụp lại chỉ nói về chất lượng.
//
// Hết hạn: KHÔNG so giờ máy với `expires_at` của máy chủ (đồng hồ điện thoại có thể lệch cả chục phút).
// Mỗi phiên/thử thách ghi mốc `performance.now()` lúc xin; hết hạn tính theo thời lượng trên đồng hồ đơn
// điệu đó. Máy chủ vẫn là bên quyết định cuối (401/409 → lỗi chung).

import type { ApiError, Challenge, FinalizeResponse, VoiceResponse } from "@/lib/api/client";

import { QUALITY_REQUIRED_FRAMES, type QualityGuidance } from "./quality";

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

/** Gợi ý chỉ có nghĩa ở bước đọc câu (âm thanh): không hiện ở bước chụp lại ảnh. */
export const AUDIO_ONLY_HINTS: readonly RetryHint[] = ["QUIET_PLACE"];

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

/**
 * Vì sao thiết bị/trình duyệt chưa đáp ứng: đây KHÔNG phải lỗi của người dùng và không đếm vào lượt thử lại
 * (không gửi gì lên máy chủ). FPS thấp không nằm trong danh sách chỉ dẫn mà có màn báo riêng.
 */
export type UnsupportedReason = "low_fps" | "low_resolution" | "no_frame_callback";

/** Thời sống thử thách theo ADR-0011 (CHALLENGE_TTL_SECONDS mặc định). */
export const CHALLENGE_TTL_MS = 120_000;
/**
 * Thời sống token theo ADR-0011 (SESSION_TTL_SECONDS mặc định = 300).
 * Máy chủ chưa gửi thời điểm cấp nên không tính được `expires_at − thời điểm cấp`; dùng mặc định này.
 * Khi API có trường thời điểm cấp (hoặc TTL), thay hằng số bằng giá trị từ phản hồi.
 */
export const TOKEN_TTL_MS = 300_000;
/** Cần còn ít nhất chừng này sau khi nháy xong để kịp gửi; không thì tạo phiên mới trước khi nháy. */
export const UPLOAD_SLACK_MS = 10_000;
/** Số lần hết hạn liên tiếp tối đa trước khi báo lỗi (chốt vòng lặp, ví dụ do đồng hồ hay TTL sai). */
export const MAX_EXPIRED_STREAK = 2;

/** Thông tin phiên giữ trong bộ nhớ (token KHÔNG được lưu ra localStorage hay log). */
export type SessionInfo = {
  sessionId: string;
  token: string;
  challenge: Challenge;
  /** Mã lần chạy: kết quả bất đồng bộ của lần chạy cũ bị bỏ qua. */
  run: number;
  /** `performance.now()` lúc BẮT ĐẦU xin phiên (đảm bảo thận trọng: hết hạn sớm hơn máy chủ, không muộn hơn). */
  tokenIssuedAtMono: number;
  /** `performance.now()` lúc bắt đầu xin thử thách này (phiên mới hoặc thử thách mới sau `retry`). */
  challengeIssuedAtMono: number;
  /** Số lần hết hạn liên tiếp tính tới phiên này. */
  expiredStreak: number;
};

export type FlowState =
  | { step: "consent"; accepted: boolean }
  /**
   * `attempt`: mã lần xin camera (tăng mỗi lần bấm "Thử lại"). Kết quả của lần xin cũ bị bỏ qua. UI so sánh
   * NỘI DUNG (step, problem, attempt), không so danh tính đối tượng state (stateRef và state React là hai đối tượng).
   */
  | { step: "camera_permission"; problem: CameraProblem | null; attempt: number }
  /**
   * Xem trước camera kèm cổng chất lượng (gộp bước đặt mặt và kiểm tra). `guidance` là chỉ dẫn của khung
   * mới nhất (null = khung đạt), `streak` là số khung đạt LIÊN TIẾP; đủ `QUALITY_REQUIRED_FRAMES` mới đi tiếp.
   */
  | {
      step: "framing";
      guidance: QualityGuidance | null;
      streak: number;
      /**
       * Có giá trị khi quay lại đặt mặt SAU `retry`: giữ phiên và thử thách mới của máy chủ; qua cổng xong
       * thì vào thẳng nháy màu với mã lần chạy mới (không tạo phiên lại).
       */
      resume: SessionInfo | null;
    }
  | { step: "device_unsupported"; reason: UnsupportedReason }
  | { step: "creating_session"; run: number; expiredStreak: number }
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
  | { type: "CAMERA_GRANTED"; attempt?: number }
  | { type: "CAMERA_FAILED"; problem: CameraProblem; attempt?: number }
  /**
   * Kết quả của MỘT lần đo chất lượng (đã phân loại bởi quality.ts). `run`: mã lần chạy mới do UI cấp,
   * chỉ dùng khi chính khung này làm đủ `QUALITY_REQUIRED_FRAMES` (xem `qualityWouldPass`); mọi kết quả
   * bất đồng bộ sau đó phải mang đúng mã này.
   */
  | { type: "QUALITY_FRAME"; guidance: QualityGuidance | null; run?: number }
  /** Camera/trình duyệt chưa đáp ứng (FPS < 15, độ phân giải thấp, thiếu requestVideoFrameCallback). */
  | { type: "DEVICE_UNSUPPORTED"; reason: UnsupportedReason }
  | { type: "SESSION_CREATED"; session: SessionInfo }
  | { type: "FLASH_DONE" }
  | { type: "FLASH_STOPPED" }
  | { type: "FLASH_INTERRUPTED" }
  /**
   * Thử thách hoặc phiên đã hết hạn: không gửi dữ liệu cũ, quay về tạo phiên mới.
   * `run`: lần chạy bị hết hạn (kết quả muộn của lần cũ bị bỏ); `nextRun`: mã cho phiên mới.
   */
  | { type: "EXPIRED"; run?: number; nextRun?: number }
  | { type: "FINALIZE_RESULT"; response: unknown; run?: number; requestedAtMono?: number }
  | { type: "RETRY_CONTINUE" }
  | { type: "VOICE_SENDING" }
  | { type: "VOICE_RESULT"; response: unknown; run?: number }
  | { type: "FAILED"; kind: ErrorKind; run?: number }
  | { type: "RESTART" };

export const initialState: FlowState = { step: "consent", accepted: false };

// ---------------------------------------------------------------------------------------------
// Phân loại lỗi

/** Đổi lỗi bất kỳ (ApiError, TypeError do mất mạng/CORS, ...) thành loại lỗi hiển thị. */
export function classifyError(error: unknown): ErrorKind {
  if (isApiError(error)) {
    const { status, errorCode } = error;
    // Máy chủ trả 2xx nhưng thân không phải JSON hợp lệ: lỗi phía máy chủ, không phải mạng.
    if (errorCode === "invalid_response") return "server";
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

/** Gợi ý cho bước chụp lại ảnh: bỏ gợi ý chỉ có nghĩa với âm thanh (ví dụ QUIET_PLACE). */
export function photoHint(value: unknown): RetryHint | null {
  const hint = normalizeHint(value);
  return hint && !AUDIO_ONLY_HINTS.includes(hint) ? hint : null;
}

// ---------------------------------------------------------------------------------------------
// Hạn thử thách / phiên (đồng hồ đơn điệu)

/** Mốc ISO hợp lệ (đọc được); dùng để từ chối phản hồi hỏng, KHÔNG dùng để so với giờ máy. */
export function isValidIsoDate(value: unknown): boolean {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}

/** Còn bao nhiêu ms trước khi thử thách hết hạn (âm nếu đã hết). */
export function challengeRemainingMs(session: SessionInfo, monoNow: number): number {
  return session.challengeIssuedAtMono + CHALLENGE_TTL_MS - monoNow;
}

/** Còn bao nhiêu ms trước khi token hết hạn (âm nếu đã hết). */
export function tokenRemainingMs(session: SessionInfo, monoNow: number): number {
  return session.tokenIssuedAtMono + TOKEN_TTL_MS - monoNow;
}

/** Phiên dùng được khi cả token lẫn thử thách chưa hết hạn (theo đồng hồ đơn điệu). */
export function sessionExpired(session: SessionInfo, monoNow: number): boolean {
  return challengeRemainingMs(session, monoNow) <= 0 || tokenRemainingMs(session, monoNow) <= 0;
}

/** Còn đủ thời gian để nháy `flashMs` rồi gửi không? Không đủ thì tạo phiên mới trước khi nháy. */
export function hasTimeToFlash(session: SessionInfo, monoNow: number, flashMs: number): boolean {
  const needed = flashMs + UPLOAD_SLACK_MS;
  return (
    challengeRemainingMs(session, monoNow) > needed && tokenRemainingMs(session, monoNow) > needed
  );
}

// ---------------------------------------------------------------------------------------------
// Reducer

const error = (kind: ErrorKind): FlowState => ({ step: "error", kind });

/** Bước đặt mặt mới: chưa có khung nào đạt. */
const freshFraming = (resume: SessionInfo | null = null): FlowState => ({
  step: "framing",
  guidance: null,
  streak: 0,
  resume,
});

/** Kết quả xin camera của một lần xin khác lần hiện tại (đến muộn) thì bỏ qua. */
const staleAttempt = (current: number, eventAttempt: number | undefined): boolean =>
  eventAttempt !== undefined && eventAttempt !== current;

const deviceUnsupported = (reason: UnsupportedReason): FlowState => ({
  step: "device_unsupported",
  reason,
});

/**
 * Khung `guidance` này có làm luồng rời bước đặt mặt không? UI dùng để cấp mã lần chạy mới (`nextRun`)
 * ĐÚNG lúc cần, tránh tăng mã mỗi khung.
 */
export function qualityWouldPass(state: FlowState, guidance: QualityGuidance | null): boolean {
  return (
    state.step === "framing" && guidance === null && state.streak + 1 >= QUALITY_REQUIRED_FRAMES
  );
}

/** Mã lần chạy của trạng thái hiện tại (null nếu bước chưa gắn với lần chạy nào). */
function currentRun(state: FlowState): number | null {
  if (state.step === "creating_session") return state.run;
  if ("session" in state) return state.session.run;
  return null;
}

/** Sự kiện bất đồng bộ mang mã lần chạy khác lần hiện tại là kết quả muộn của lần cũ: bỏ qua. */
function isStale(state: FlowState, eventRun: number | undefined): boolean {
  const current = currentRun(state);
  return eventRun !== undefined && current !== null && eventRun !== current;
}

export function reduce(state: FlowState, event: FlowEvent): FlowState {
  // Bắt đầu lại hợp lệ ở mọi bước.
  if (event.type === "RESTART") return freshFraming();
  // Thiết bị chưa đáp ứng chỉ xét ở hai bước dùng camera (xử lý riêng trong từng case); bỏ qua ở bước khác.
  // Lỗi hợp lệ ở mọi bước TRỪ kết quả cuối (một lỗi đến muộn không được biến kết quả đã có thành lỗi),
  // và bỏ qua lỗi của lần chạy cũ.
  if (event.type === "FAILED") {
    if (state.step === "result" || isStale(state, event.run)) return state;
    return error(event.kind);
  }

  switch (state.step) {
    case "consent":
      if (event.type === "TOGGLE_CONSENT") return { step: "consent", accepted: event.accepted };
      // Chỉ đi tiếp khi người dùng đã tự tích đồng ý (không bao giờ tích sẵn).
      if (event.type === "CONTINUE" && state.accepted) {
        return { step: "camera_permission", problem: null, attempt: 0 };
      }
      return state;

    case "camera_permission":
      if (event.type === "CAMERA_GRANTED") {
        return staleAttempt(state.attempt, event.attempt) ? state : freshFraming();
      }
      if (event.type === "DEVICE_UNSUPPORTED") return deviceUnsupported(event.reason);
      if (event.type === "CAMERA_FAILED") {
        if (staleAttempt(state.attempt, event.attempt)) return state;
        return { step: "camera_permission", problem: event.problem, attempt: state.attempt };
      }
      // "Thử lại": lần xin mới, kết quả của lần cũ đến muộn sẽ bị bỏ qua.
      if (event.type === "CONTINUE") {
        return { step: "camera_permission", problem: null, attempt: state.attempt + 1 };
      }
      return state;

    case "framing":
      if (event.type === "DEVICE_UNSUPPORTED") return deviceUnsupported(event.reason);
      if (event.type === "QUALITY_FRAME") {
        // Khung kém: đặt lại bộ đếm và hiện chỉ dẫn mới. Chỉ đi tiếp khi đủ N khung đạt LIÊN TIẾP.
        if (event.guidance !== null) {
          return { step: "framing", guidance: event.guidance, streak: 0, resume: state.resume };
        }
        const streak = state.streak + 1;
        if (streak >= QUALITY_REQUIRED_FRAMES) {
          // Sau `retry`: vào thẳng nháy màu với thử thách mới, mã lần chạy MỚI. Lần đầu: tạo phiên.
          if (state.resume) {
            return {
              step: "flash_challenge",
              session: { ...state.resume, run: event.run ?? state.resume.run },
            };
          }
          return { step: "creating_session", run: event.run ?? 0, expiredStreak: 0 };
        }
        return { step: "framing", guidance: null, streak, resume: state.resume };
      }
      return state;

    case "device_unsupported":
      return state; // chỉ RESTART mới rời khỏi (xử lý ở đầu hàm)

    case "creating_session":
      if (event.type === "SESSION_CREATED") {
        // Phiên của lần chạy khác (ví dụ lần cũ trả muộn) bị bỏ qua.
        if (event.session.run !== state.run) return state;
        return {
          step: "flash_challenge",
          session: { ...event.session, expiredStreak: state.expiredStreak },
        };
      }
      return state;

    case "flash_challenge":
      if (event.type === "FLASH_DONE") return { step: "uploading", session: state.session };
      if (event.type === "FLASH_STOPPED") return error("stopped");
      if (event.type === "FLASH_INTERRUPTED") return error("interrupted");
      if (event.type === "EXPIRED") return expire(state, state.session, event);
      return state;

    case "uploading":
      if (event.type === "EXPIRED") return expire(state, state.session, event);
      if (event.type === "FINALIZE_RESULT") {
        if (isStale(state, event.run)) return state;
        return fromFinalize(state.session, event.response, event.requestedAtMono);
      }
      return state;

    case "retry":
      if (event.type === "EXPIRED") return expire(state, state.session, event);
      // Chụp lại phải qua cổng chất lượng LẠI (ánh sáng, vị trí có thể đã đổi), rồi mới nháy màu.
      if (event.type === "RETRY_CONTINUE") return freshFraming(state.session);
      return state;

    case "voice_challenge":
      if (event.type === "VOICE_SENDING") return { ...state, sending: true };
      if (event.type === "VOICE_RESULT") {
        if (isStale(state, event.run)) return state;
        return fromVoice(state, event.response);
      }
      return state;

    case "result":
    case "error":
      return state;
  }
}

/**
 * Hết hạn: quay về tạo phiên mới và không gửi dữ liệu cũ. Chốt vòng lặp: hết hạn liên tiếp
 * `MAX_EXPIRED_STREAK` lần (ví dụ TTL hay đồng hồ sai) thì báo lỗi phiên thay vì lặp mãi.
 */
function expire(
  state: FlowState,
  session: SessionInfo,
  event: Extract<FlowEvent, { type: "EXPIRED" }>,
): FlowState {
  if (isStale(state, event.run)) return state; // báo hết hạn muộn của lần cũ
  const streak = session.expiredStreak + 1;
  if (streak >= MAX_EXPIRED_STREAK) return error("session");
  return { step: "creating_session", run: event.nextRun ?? session.run + 1, expiredStreak: streak };
}

/** Kết quả finalize → trạng thái. Chỉ `pass` mới là đạt; thiếu dữ liệu cần thiết hoặc status lạ → lỗi. */
function fromFinalize(
  session: SessionInfo,
  response: unknown,
  requestedAtMono: number | undefined,
): FlowState {
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
        session: {
          ...session,
          challenge: r.challenge,
          // Không biết mốc xin thì coi là đã hết hạn (thận trọng): sẽ tạo phiên mới thay vì dùng nhầm.
          challengeIssuedAtMono: requestedAtMono ?? Number.NEGATIVE_INFINITY,
          expiredStreak: 0, // luồng đã tiến triển
        },
        hint: photoHint(r.retry_hint),
        attemptsLeft: asNumberOrNull(r.attempts_left),
      };
    }
    case "voice_challenge": {
      const prompt = typeof r.voice_prompt === "string" ? r.voice_prompt.trim() : "";
      if (!prompt) return error("unexpected"); // web không tự đặt câu đọc
      return {
        step: "voice_challenge",
        session: { ...session, expiredStreak: 0 },
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
