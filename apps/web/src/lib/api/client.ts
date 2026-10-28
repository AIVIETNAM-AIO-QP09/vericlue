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
export type ReviewCase = Schemas["ReviewCase"];
export type ReviewCaseList = Schemas["ReviewCaseList"];
export type ReviewAiOpinion = Schemas["ReviewAiOpinion"];
export type PrivacyState = Schemas["PrivacyState"];
export type PrivacyConsentRequest = Schemas["PrivacyConsentRequest"];

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
  /** Credential nhân viên lấy từ bộ nhớ của bên gọi; không dùng public env hoặc URL. */
  getStaffToken?: () => string | undefined;
};

type RequestOptions = {
  /** Hủy lời gọi (ví dụ khi người dùng rời trang). */
  signal?: AbortSignal;
  token?: string;
  json?: unknown;
  form?: FormData;
  headers?: Record<string, string>;
  cache?: RequestCache;
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

    const res = await doFetch(`${baseUrl}${path}`, {
      method,
      headers,
      body,
      signal: opts.signal,
      cache: opts.cache,
    });
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

  function staffRequest<T>(method: string, path: string, opts: RequestOptions = {}) {
    return request<T>(method, path, {
      ...opts,
      token: options.getStaffToken?.(),
      cache: "no-store",
    });
  }

  return {
    sessionPrivacy(sessionId: string, token: string, signal?: AbortSignal) {
      return request<PrivacyState>("GET", `/v1/sessions/${encodeURIComponent(sessionId)}/privacy`, {
        token,
        signal,
        cache: "no-store",
      });
    },
    grantSessionConsent(
      sessionId: string,
      token: string,
      body: PrivacyConsentRequest,
      signal?: AbortSignal,
    ) {
      return request<PrivacyState>(
        "POST",
        `/v1/sessions/${encodeURIComponent(sessionId)}/privacy/consent`,
        { token, json: body, signal, cache: "no-store" },
      );
    },
    withdrawSessionConsent(sessionId: string, token: string, signal?: AbortSignal) {
      return request<PrivacyState>(
        "POST",
        `/v1/sessions/${encodeURIComponent(sessionId)}/privacy/withdraw`,
        { token, json: { confirm: true }, signal, cache: "no-store" },
      );
    },
    credentialSigningKey() {
      return request<Schemas["CredentialKey"]>("GET", "/v1/credential-signing-key", {
        cache: "no-store",
      });
    },
    credentialAuthorization(
      sessionId: string,
      token: string,
      body: Schemas["CredentialOfferRequest"],
    ) {
      return request<Schemas["CredentialAuthorization"]>(
        "POST",
        `/v1/sessions/${encodeURIComponent(sessionId)}/credential-authorization`,
        { token, json: body, cache: "no-store" },
      );
    },
    issueCredential(sessionId: string, token: string, body: Schemas["CredentialIssueRequest"]) {
      return request<Schemas["VerificationCredential"]>(
        "POST",
        `/v1/sessions/${encodeURIComponent(sessionId)}/credential`,
        { token, json: body, cache: "no-store" },
      );
    },
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
    // --- Bàn duyệt (chỉ trang thử nội bộ /lab/session dùng; người dân không bao giờ gọi) ---
    listReviewCases(signal?: AbortSignal) {
      return staffRequest<ReviewCaseList>("GET", "/v1/review/cases", { signal });
    },
    getReviewCase(caseId: string, signal?: AbortSignal) {
      return staffRequest<ReviewCase>("GET", `/v1/review/cases/${encodeURIComponent(caseId)}`, {
        signal,
      });
    },
    recordInitialDecision(
      caseId: string,
      decision: "accept" | "reject" | "request_retry",
      note: string,
      signal?: AbortSignal,
    ) {
      return staffRequest<Schemas["DecisionResponse"]>(
        "POST",
        `/v1/review/cases/${encodeURIComponent(caseId)}/initial`,
        { json: { decision, note }, signal },
      );
    },
    createForensicJob(
      file: Blob,
      fileName: string,
      opts: { reviewCaseId?: string; signal?: AbortSignal } = {},
    ) {
      const form = new FormData();
      form.append("file", file, fileName);
      if (opts.reviewCaseId !== undefined) form.append("review_case_id", opts.reviewCaseId);
      return staffRequest<Schemas["JobCreated"]>("POST", "/v1/forensic/jobs", {
        form,
        signal: opts.signal,
      });
    },
    getForensicJob(jobId: string, signal?: AbortSignal) {
      return staffRequest<Schemas["ForensicJob"]>(
        "GET",
        `/v1/forensic/jobs/${encodeURIComponent(jobId)}`,
        { signal },
      );
    },
    verifyForensicReviewAudit(reportJson: string, signature: string, signal?: AbortSignal) {
      return staffRequest<Schemas["ReviewAuditVerifyResponse"]>(
        "POST",
        "/v1/forensic/review-audit/verify",
        {
          json: { report_json: reportJson, signature },
          signal,
        },
      );
    },
    getAiOpinion(caseId: string, signal?: AbortSignal) {
      return staffRequest<ReviewAiOpinion>(
        "GET",
        `/v1/review/cases/${encodeURIComponent(caseId)}/ai`,
        {
          signal,
        },
      );
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
