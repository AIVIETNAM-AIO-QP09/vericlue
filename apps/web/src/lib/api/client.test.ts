import { describe, expect, it } from "vitest";

import { ApiError, createApiClient } from "./client";

type Call = { url: string; init: RequestInit };

function fakeFetch(responses: Array<{ status?: number; body: unknown }>) {
  const calls: Call[] = [];
  const impl = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    const next = responses.shift();
    if (!next) throw new Error("hết phản hồi giả");
    const status = next.status ?? 200;
    return new Response(JSON.stringify(next.body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }) as unknown as typeof fetch;
  return { impl, calls };
}

const SESSION = {
  session_id: "ses_1",
  token: "tok_1",
  expires_at: "2026-10-15T08:05:00Z",
  challenge: {
    challenge_id: "ch_1",
    baseline_ms: 1000,
    color_sequence: Array.from({ length: 8 }, (_, i) => ({
      rgb: i % 2 ? "#73d9ff" : "#ffcc73",
      hold_ms: 500,
      transition_ms: 150 as const,
    })),
  },
};

describe("api client", () => {
  it("cấp chứng nhận theo bearer phiên và gửi chấp thuận đã ký, không lưu cache", async () => {
    const { impl, calls } = fakeFetch([
      { body: { key_id: "test-key", public_key: "test-public" } },
      { body: { message: "exact-server-bytes", expires_at: 123 } },
      { body: { claims: { assurance: "server-decision" } } },
    ]);
    const api = createApiClient({ baseUrl: "http://api.test", fetchImpl: impl });
    await api.credentialSigningKey();
    await api.credentialAuthorization("a/b", "session-token", {
      commitment: "test-commitment",
      consent: true,
    });
    await api.issueCredential("a/b", "session-token", {
      commitment: "test-commitment",
      consent: true,
      device_signature: "registered-device-signature",
    });
    expect(calls[1].url).toContain("/a%2Fb/credential-authorization");
    expect(calls[2].url).toContain("/a%2Fb/credential");
    for (const call of calls) expect(call.init.cache).toBe("no-store");
    for (const call of calls.slice(1))
      expect(call.init.headers).toMatchObject({ Authorization: "Bearer session-token" });
    expect(JSON.parse(calls[2].init.body as string)).toEqual({
      commitment: "test-commitment",
      consent: true,
      device_signature: "registered-device-signature",
    });
  });
  it("gửi giám định độc lập hoặc gắn ca bằng credential nhân viên và giữ nguyên JSON đã ký", async () => {
    const { impl, calls } = fakeFetch([
      { body: { job_id: "job_1", status: "queued" } },
      { body: { job_id: "job_2", status: "queued" } },
      {
        body: {
          ok: false,
          signature_valid: false,
          status: "invalid_signature",
          scope: "signed_json_review_audit",
        },
      },
      { body: { job_id: "a/b?c", status: "done", segments: [] } },
    ]);
    const api = createApiClient({
      baseUrl: "http://api.test",
      fetchImpl: impl,
      getStaffToken: () => "staff-test",
    });
    const signal = new AbortController().signal;
    await api.createForensicJob(new Blob(["synthetic"]), "material.mp4", { signal });
    await api.createForensicJob(new Blob(["synthetic"]), "material.mp4", {
      reviewCaseId: "case_1",
      signal,
    });
    expect((calls[0].init.body as FormData).has("review_case_id")).toBe(false);
    expect((calls[1].init.body as FormData).get("review_case_id")).toBe("case_1");
    for (const call of calls) {
      expect(call.init.headers).toMatchObject({ Authorization: "Bearer staff-test" });
      expect((call.init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
      expect(call.init.cache).toBe("no-store");
      expect(call.init.signal).toBe(signal);
    }
    const raw = '{"filename":"\\u0111","job":{}}';
    await api.verifyForensicReviewAudit(raw, "synthetic-signature");
    expect(JSON.parse(calls[2].init.body as string)).toEqual({
      report_json: raw,
      signature: "synthetic-signature",
    });
    expect(calls[2].url).toBe("http://api.test/v1/forensic/review-audit/verify");
    await api.getForensicJob("a/b?c");
    expect(calls[3].url).toBe("http://api.test/v1/forensic/jobs/a%2Fb%3Fc");
  });
  it("chỉ gửi credential nhân viên cho bàn duyệt, không lẫn với token phiên", async () => {
    const { impl, calls } = fakeFetch([
      { body: SESSION },
      { body: { status: "pass" } },
      { body: { items: [] } },
      { body: {} },
      { body: {} },
      { body: {} },
    ]);
    let staffLookups = 0;
    const api = createApiClient({
      baseUrl: "http://api.test",
      fetchImpl: impl,
      getStaffToken: () => {
        staffLookups += 1;
        return "staff-synthetic";
      },
    });
    await api.createSession();
    await api.finalize("ses_1", "citizen-synthetic");
    expect(staffLookups).toBe(0);
    await api.listReviewCases();
    await api.getReviewCase("case_1");
    await api.recordInitialDecision("case_1", "accept", "");
    await api.getAiOpinion("case_1");
    expect(staffLookups).toBe(4);
    expect(calls[0].init.headers).not.toHaveProperty("Authorization");
    expect(calls[1].init.headers).toMatchObject({ Authorization: "Bearer citizen-synthetic" });
    for (const call of calls.slice(2)) {
      expect(call.init.headers).toMatchObject({ Authorization: "Bearer staff-synthetic" });
      expect(call.init.cache).toBe("no-store");
      expect(call.url).not.toContain("staff-synthetic");
    }
  });

  it("lấy lại credential mỗi lần gọi và không giữ token cũ sau đăng xuất", async () => {
    const { impl, calls } = fakeFetch([
      { body: { items: [] } },
      { body: { items: [] } },
      {
        status: 401,
        body: { error_code: "unauthorized", message: "Thiếu hoặc sai quyền truy cập." },
      },
    ]);
    let token: string | undefined = "staff-first";
    const api = createApiClient({ fetchImpl: impl, getStaffToken: () => token });
    await api.listReviewCases();
    token = "staff-second";
    await api.listReviewCases();
    token = undefined;
    await expect(api.listReviewCases()).rejects.toMatchObject({
      status: 401,
      errorCode: "unauthorized",
    });
    expect(calls[0].init.headers).toMatchObject({ Authorization: "Bearer staff-first" });
    expect(calls[1].init.headers).toMatchObject({ Authorization: "Bearer staff-second" });
    expect(calls[2].init.headers).not.toHaveProperty("Authorization");
  });

  it("POST /v1/sessions trả challenge 8 màu", async () => {
    const { impl, calls } = fakeFetch([{ body: SESSION }]);
    const api = createApiClient({ baseUrl: "http://api.test/", fetchImpl: impl });

    const session = await api.createSession("genuine");

    expect(calls[0].url).toBe("http://api.test/v1/sessions");
    expect(calls[0].init.method).toBe("POST");
    expect(calls[0].init.headers).toMatchObject({ "X-Mock-Scenario": "genuine" });
    expect((calls[0].init.headers as Record<string, string>).Authorization).toBeUndefined();
    expect(session.challenge.color_sequence).toHaveLength(8);
    expect(session.token).toBe("tok_1");
  });

  it("gắn Bearer token cho mọi lời gọi của phiên", async () => {
    const { impl, calls } = fakeFetch([
      { body: { step: "signals", received: true } },
      { body: { status: "pass" } },
    ]);
    const api = createApiClient({ baseUrl: "http://api.test", fetchImpl: impl });

    await api.sendSignals("ses_1", "tok_1", { color_events: [], frame_times: [] });
    const result = await api.finalize("ses_1", "tok_1");

    for (const call of calls) {
      expect(call.init.headers).toMatchObject({ Authorization: "Bearer tok_1" });
    }
    expect(calls[0].url).toBe("http://api.test/v1/sessions/ses_1/signals");
    expect(result.status).toBe("pass");
  });

  it("gửi media dạng multipart, không tự đặt Content-Type", async () => {
    const { impl, calls } = fakeFetch([{ body: { step: "media", received: true } }]);
    const api = createApiClient({ baseUrl: "http://api.test", fetchImpl: impl });

    await api.uploadMedia("ses_1", "tok_1", new Blob(["x"], { type: "image/jpeg" }));

    expect(calls[0].init.body).toBeInstanceOf(FormData);
    expect((calls[0].init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("lỗi 401 thành ApiError có error_code", async () => {
    const { impl } = fakeFetch([
      { status: 401, body: { error_code: "unauthorized", message: "Thiếu hoặc sai token phiên." } },
    ]);
    const api = createApiClient({ baseUrl: "http://api.test", fetchImpl: impl });

    const failure = api.finalize("ses_1", "sai");
    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({ status: 401, errorCode: "unauthorized" });
  });

  it("mã hóa session_id trong đường dẫn", async () => {
    const { impl, calls } = fakeFetch([{ body: { status: "pass" } }]);
    const api = createApiClient({ baseUrl: "http://api.test", fetchImpl: impl });

    await api.finalize("a/b?c", "tok_1");

    expect(calls[0].url).toBe("http://api.test/v1/sessions/a%2Fb%3Fc/finalize");
  });

  it("nối AbortSignal tới fetch của mọi lời gọi", async () => {
    const { impl, calls } = fakeFetch([
      { body: SESSION },
      { body: { step: "media", received: true } },
      { body: { step: "signals", received: true } },
      { body: { status: "pass" } },
      { body: { status: "pass" } },
    ]);
    const api = createApiClient({ baseUrl: "http://api.test", fetchImpl: impl });
    const controller = new AbortController();
    const { signal } = controller;

    await api.createSession("genuine", signal);
    await api.uploadMedia("ses_1", "tok", new Blob(["x"]), undefined, signal);
    await api.sendSignals("ses_1", "tok", { color_events: [], frame_times: [] }, signal);
    await api.finalize("ses_1", "tok", signal);
    await api.sendVoice("ses_1", "tok", new Blob(["x"]), undefined, signal);

    expect(calls).toHaveLength(5);
    for (const call of calls) expect(call.init.signal).toBe(signal);
  });

  it("2xx nhưng thân không phải JSON là ApiError invalid_response (không phải lỗi mạng)", async () => {
    const impl = (async () =>
      new Response("{không phải json", { status: 200 })) as unknown as typeof fetch;
    const api = createApiClient({ baseUrl: "http://api.test", fetchImpl: impl });

    const failure = api.finalize("ses_1", "tok");
    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({ status: 200, errorCode: "invalid_response" });
  });
});
