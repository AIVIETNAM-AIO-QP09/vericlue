// Client API nhỏ: mọi lời gọi từ web đi qua file này (không gọi fetch rải rác).
// Type lấy từ OpenAPI của FastAPI (schema.d.ts, sinh bằng `npm run gen:api`).

import type { components } from "./schema";

type Schemas = components["schemas"];

export type CreateSessionResponse = Schemas["CreateSessionResponse"];
export type Challenge = Schemas["Challenge"];
export type Signals = Schemas["Signals"];
export type StepAck = Schemas["StepAck"];
export type FinalizeResponse = Schemas["FinalizeResponse"];
export type VoiceResponse = Schemas["VoiceResponse"];
export type ErrorResponse = Schemas["ErrorResponse"];

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly errorCode: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type ApiClientOptions = {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
};

type RequestOptions = {
  /** Hủy lời gọi (ví dụ khi người dùng rời trang). */
  signal?: AbortSignal;
  token?: string;
  json?: unknown;
  form?: FormData;
  headers?: Record<string, string>;
};

const DEFAULT_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function createApiClient(options: ApiClientOptions = {}) {
  const baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
  const doFetch = options.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args));

  async function request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
    const headers: Record<string, string> = { ...opts.headers };
    if (opts.token) headers.Authorization = `Bearer ${opts.token}`;
    let body: BodyInit | undefined;
    if (opts.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.json);
    } else if (opts.form) {
      body = opts.form; // trình duyệt tự đặt boundary
    }

    const res = await doFetch(`${baseUrl}${path}`, { method, headers, body, signal: opts.signal });
    if (!res.ok) {
      const err = (await res.json().catch(() => null)) as Partial<ErrorResponse> | null;
      throw new ApiError(
        res.status,
        err?.error_code ?? "unknown_error",
        err?.message ?? res.statusText,
      );
    }
    try {
      return (await res.json()) as T;
    } catch {
      // 2xx nhưng thân không phải JSON hợp lệ: lỗi phía máy chủ, không phải lỗi mạng.
      throw new ApiError(res.status, "invalid_response", "Phản hồi của máy chủ không hợp lệ");
    }
  }

  return {
    /** Tạo phiên. `scenario` chỉ có tác dụng khi API chạy mock (header X-Mock-Scenario). */
    createSession(scenario?: string, signal?: AbortSignal) {
      return request<CreateSessionResponse>("POST", "/v1/sessions", {
        headers: scenario ? { "X-Mock-Scenario": scenario } : undefined,
        signal,
      });
    },
    uploadMedia(sessionId: string, token: string, image: Blob, video?: Blob, signal?: AbortSignal) {
      const form = new FormData();
      form.append("image", image, "face.jpg");
      if (video) form.append("video", video, "face.webm");
      return request<StepAck>("POST", `/v1/sessions/${encodeURIComponent(sessionId)}/media`, {
        token,
        form,
        signal,
      });
    },
    sendSignals(sessionId: string, token: string, signals: Signals, signal?: AbortSignal) {
      return request<StepAck>("POST", `/v1/sessions/${encodeURIComponent(sessionId)}/signals`, {
        token,
        json: signals,
        signal,
      });
    },
    finalize(sessionId: string, token: string, signal?: AbortSignal) {
      return request<FinalizeResponse>(
        "POST",
        `/v1/sessions/${encodeURIComponent(sessionId)}/finalize`,
        { token, signal },
      );
    },
    sendVoice(sessionId: string, token: string, audio: Blob, video?: Blob, signal?: AbortSignal) {
      const form = new FormData();
      form.append("audio", audio, "voice.wav");
      if (video) form.append("video", video, "voice.webm");
      return request<VoiceResponse>("POST", `/v1/sessions/${encodeURIComponent(sessionId)}/voice`, {
        token,
        form,
        signal,
      });
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
