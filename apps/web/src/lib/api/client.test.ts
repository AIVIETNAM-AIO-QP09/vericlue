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
});
