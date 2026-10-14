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

    const res = await doFetch(`${baseUrl}${path}`, { method, headers, body });
    if (!res.ok) {
      const err = (await res.json().catch(() => null)) as Partial<ErrorResponse> | null;
      throw new ApiError(
        res.status,
        err?.error_code ?? "unknown_error",
        err?.message ?? res.statusText,
      );
    }
    return (await res.json()) as T;
  }

  return {
    /** Tạo phiên. `scenario` chỉ có tác dụng khi API chạy mock (header X-Mock-Scenario). */
    createSession(scenario?: string) {
      return request<CreateSessionResponse>("POST", "/v1/sessions", {
        headers: scenario ? { "X-Mock-Scenario": scenario } : undefined,
      });
    },
    uploadMedia(sessionId: string, token: string, image: Blob, video?: Blob) {
      const form = new FormData();
      form.append("image", image, "face.jpg");
      if (video) form.append("video", video, "face.webm");
      return request<StepAck>("POST", `/v1/sessions/${encodeURIComponent(sessionId)}/media`, {
        token,
        form,
      });
    },
    sendSignals(sessionId: string, token: string, signals: Signals) {
      return request<StepAck>("POST", `/v1/sessions/${encodeURIComponent(sessionId)}/signals`, {
        token,
        json: signals,
      });
    },
    finalize(sessionId: string, token: string) {
      return request<FinalizeResponse>(
        "POST",
        `/v1/sessions/${encodeURIComponent(sessionId)}/finalize`,
        { token },
      );
    },
    sendVoice(sessionId: string, token: string, audio: Blob, video?: Blob) {
      const form = new FormData();
      form.append("audio", audio, "voice.wav");
      if (video) form.append("video", video, "voice.webm");
      return request<VoiceResponse>("POST", `/v1/sessions/${encodeURIComponent(sessionId)}/voice`, {
        token,
        form,
      });
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
