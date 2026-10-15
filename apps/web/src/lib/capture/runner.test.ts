import { describe, expect, it } from "vitest";

import { createApiClient } from "@/lib/api/client";

import {
  CHALLENGE_TTL_MS,
  type FlowEvent,
  type FlowState,
  type SessionInfo,
  TOKEN_TTL_MS,
  initialState,
  reduce,
} from "./flow";
import { type RunnerDeps, sendVoiceAnswer, startSession, uploadAndFinalize } from "./runner";

// --- fetch giả -------------------------------------------------------------------------------

type Reply = { status?: number; body?: unknown; throws?: Error; raw?: string; hang?: boolean };
type Call = { url: string; init: RequestInit };

function fakeFetch(replies: Reply[]) {
  const calls: Call[] = [];
  const impl = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    const next = replies.shift();
    if (!next) throw new Error("hết phản hồi giả");
    if (next.throws) throw next.throws;
    if (next.hang) {
      // Lời gọi treo cho tới khi bị hủy (giống fetch thật với AbortSignal).
      return new Promise<Response>((_resolve, reject) => {
        init.signal?.addEventListener("abort", () =>
          reject(new DOMException("The operation was aborted.", "AbortError")),
        );
      });
    }
    return new Response(next.raw ?? JSON.stringify(next.body ?? {}), {
      status: next.status ?? 200,
      headers: { "Content-Type": "application/json" },
    });
  }) as unknown as typeof fetch;
  return { impl, calls };
}

/** Đồng hồ đơn điệu giả: có thể chỉnh tay giữa các lời gọi. */
function makeDeps(replies: Reply[], mono = { now: 0 }) {
  const { impl, calls } = fakeFetch(replies);
  const deps: RunnerDeps = {
    client: createApiClient({ baseUrl: "http://api.test", fetchImpl: impl }),
    monoMs: () => mono.now,
  };
  return { deps, calls, mono };
}

// --- dữ liệu mẫu -----------------------------------------------------------------------------

function challenge(id: string, expiresAt = "2026-10-15T08:02:00Z") {
  return {
    challenge_id: id,
    baseline_ms: 1000,
    expires_at: expiresAt,
    color_sequence: Array.from({ length: 8 }, (_, i) => ({
      rgb: i % 2 ? "#73d9ff" : "#ffcc73",
      hold_ms: 500,
      transition_ms: 150,
    })),
  };
}

const CREATE_OK = {
  session_id: "ses_1",
  token: "tok_1",
  expires_at: "2026-10-15T08:05:00Z",
  challenge: challenge("ch_1"),
};

const SESSION: SessionInfo = {
  sessionId: "ses_1",
  token: "tok_1",
  challenge: challenge("ch_1") as SessionInfo["challenge"],
  run: 3,
  tokenIssuedAtMono: 0,
  challengeIssuedAtMono: 0,
  expiredStreak: 0,
};

const PAYLOAD = {
  image: new Blob(["x"], { type: "image/jpeg" }),
  signals: { color_events: [], frame_times: [] },
};
const ACK_MEDIA = { status: 200, body: { step: "media", received: true } };
const ACK_SIGNALS = { status: 200, body: { step: "signals", received: true } };

/** Đưa luồng tới bước `uploading` bằng các sự kiện thật (mã lần chạy = SESSION.run). */
function toUploading(): FlowState {
  const events: FlowEvent[] = [
    { type: "TOGGLE_CONSENT", accepted: true },
    { type: "CONTINUE" },
    { type: "CAMERA_GRANTED" },
    { type: "FRAMING_READY" },
    { type: "QUALITY_PASSED", run: SESSION.run },
    { type: "SESSION_CREATED", session: SESSION },
    { type: "FLASH_DONE" },
  ];
  return events.reduce(reduce, initialState);
}

// --- startSession ----------------------------------------------------------------------------

describe("startSession", () => {
  it("tạo phiên, ghi mốc đồng hồ đơn điệu, gắn mã lần chạy và header kịch bản mock", async () => {
    const { deps, calls } = makeDeps([{ body: CREATE_OK }], { now: 5000 });
    const event = await startSession(deps, { run: 9 }, "low_quality");

    expect(event.type).toBe("SESSION_CREATED");
    if (event.type === "SESSION_CREATED") {
      expect(event.session.sessionId).toBe("ses_1");
      expect(event.session.token).toBe("tok_1");
      expect(event.session.run).toBe(9);
      expect(event.session.tokenIssuedAtMono).toBe(5000);
      expect(event.session.challengeIssuedAtMono).toBe(5000);
      expect(event.session.challenge.challenge_id).toBe("ch_1");
    }
    expect(calls[0].init.headers).toMatchObject({ "X-Mock-Scenario": "low_quality" });
  });

  it.each([
    ["thiếu token", { ...CREATE_OK, token: undefined }],
    ["thiếu thử thách", { ...CREATE_OK, challenge: undefined }],
    ["thử thách rỗng", { ...CREATE_OK, challenge: { ...CREATE_OK.challenge, color_sequence: [] } }],
    ["không phải đối tượng", "abc"],
  ])("phản hồi sai dạng (%s) thành lỗi phiên, không tạo phiên", async (_name, body) => {
    const { deps } = makeDeps([{ body }]);
    expect(await startSession(deps, { run: 1 })).toEqual({
      type: "FAILED",
      kind: "session",
      run: 1,
    });
  });

  it.each([
    ["expires_at của phiên hỏng", { ...CREATE_OK, expires_at: "không phải ngày" }],
    ["expires_at bị thiếu", { ...CREATE_OK, expires_at: undefined }],
    [
      "challenge.expires_at hỏng",
      { ...CREATE_OK, challenge: challenge("ch_1", "không phải ngày") },
    ],
  ])("%s bị từ chối bằng thông báo lỗi phiên", async (_name, body) => {
    const { deps } = makeDeps([{ body }]);
    const event = await startSession(deps, { run: 1 });
    expect(event).toEqual({ type: "FAILED", kind: "session", run: 1 });
    expect(reduce({ step: "creating_session", run: 1, expiredStreak: 0 }, event)).toEqual({
      step: "error",
      kind: "session",
    });
  });

  it.each([
    [422, "invalid"],
    [500, "server"],
    [404, "unexpected"],
  ])("HTTP %i thành lỗi %s", async (status, kind) => {
    const { deps } = makeDeps([{ status, body: { error_code: "x", message: "y" } }]);
    expect(await startSession(deps, { run: 2 })).toEqual({ type: "FAILED", kind, run: 2 });
  });

  it("mất mạng (fetch ném TypeError) thành lỗi network", async () => {
    const { deps } = makeDeps([{ throws: new TypeError("Failed to fetch") }]);
    expect(await startSession(deps, { run: 2 })).toEqual({
      type: "FAILED",
      kind: "network",
      run: 2,
    });
  });

  it("200 nhưng thân không phải JSON là lỗi máy chủ, không phải lỗi mạng", async () => {
    const { deps } = makeDeps([{ status: 200, raw: "<html>không phải JSON</html>" }]);
    expect(await startSession(deps, { run: 2 })).toEqual({
      type: "FAILED",
      kind: "server",
      run: 2,
    });
  });
});

// --- Giờ máy lệch không làm hỏng hạn ---------------------------------------------------------

describe("hết hạn theo đồng hồ đơn điệu, bỏ qua giờ treo tường", () => {
  // Điện thoại nhanh +10 phút: expires_at của máy chủ trông như đã qua từ lâu.
  // Điện thoại chậm -10 phút: expires_at trông như còn rất lâu. Cả hai không được ảnh hưởng.
  const FAST_PHONE = {
    ...CREATE_OK,
    expires_at: "2000-01-01T00:00:00Z",
    challenge: challenge("ch_1", "2000-01-01T00:00:00Z"),
  };
  const SLOW_PHONE = {
    ...CREATE_OK,
    expires_at: "2999-01-01T00:00:00Z",
    challenge: challenge("ch_1", "2999-01-01T00:00:00Z"),
  };

  it.each([
    ["nhanh +10 phút", FAST_PHONE],
    ["chậm -10 phút", SLOW_PHONE],
  ])("điện thoại %s: phiên mới tạo vẫn dùng được và gửi bình thường", async (_name, body) => {
    const mono = { now: 1000 };
    const { deps, calls } = makeDeps(
      [{ body }, ACK_MEDIA, ACK_SIGNALS, { body: { status: "pass" } }],
      mono,
    );
    const created = await startSession(deps, { run: 1 });
    if (created.type !== "SESSION_CREATED") throw new Error("phải tạo được phiên");

    mono.now += 30_000; // 30 giây sau
    const result = await uploadAndFinalize(deps, created.session, PAYLOAD);
    expect(result.type).toBe("FINALIZE_RESULT");
    expect(calls).toHaveLength(4);
  });

  it.each([
    ["nhanh +10 phút", FAST_PHONE],
    ["chậm -10 phút", SLOW_PHONE],
  ])("điện thoại %s: quá 120 giây vẫn bị coi là hết hạn và không gửi gì", async (_name, body) => {
    const mono = { now: 1000 };
    const { deps, calls } = makeDeps([{ body }], mono);
    const created = await startSession(deps, { run: 1 });
    if (created.type !== "SESSION_CREATED") throw new Error("phải tạo được phiên");

    mono.now += CHALLENGE_TTL_MS;
    expect(await uploadAndFinalize(deps, created.session, PAYLOAD)).toEqual({
      type: "EXPIRED",
      run: 1,
    });
    expect(calls).toHaveLength(1); // chỉ có lần tạo phiên
  });
});

// --- uploadAndFinalize -----------------------------------------------------------------------

describe("uploadAndFinalize", () => {
  it("gửi media, signals, finalize theo thứ tự và gắn Bearer ở mọi bước", async () => {
    const { deps, calls } = makeDeps([ACK_MEDIA, ACK_SIGNALS, { body: { status: "pass" } }], {
      now: 777,
    });
    const event = await uploadAndFinalize(deps, SESSION, PAYLOAD);

    expect(calls.map((c) => c.url)).toEqual([
      "http://api.test/v1/sessions/ses_1/media",
      "http://api.test/v1/sessions/ses_1/signals",
      "http://api.test/v1/sessions/ses_1/finalize",
    ]);
    for (const call of calls) {
      expect(call.init.headers).toMatchObject({ Authorization: "Bearer tok_1" });
    }
    expect(event).toEqual({
      type: "FINALIZE_RESULT",
      response: { status: "pass" },
      run: 3,
      requestedAtMono: 777,
    });
  });

  it("thử thách hết hạn (120 giây): không gửi media cũ, trả EXPIRED kèm mã lần chạy", async () => {
    const { deps, calls } = makeDeps([], { now: CHALLENGE_TTL_MS });
    expect(await uploadAndFinalize(deps, SESSION, PAYLOAD)).toEqual({ type: "EXPIRED", run: 3 });
    expect(calls).toHaveLength(0);
  });

  it("token hết hạn (TTL mặc định) cũng không gửi gì", async () => {
    const { deps, calls } = makeDeps([], { now: TOKEN_TTL_MS });
    const session = { ...SESSION, challengeIssuedAtMono: TOKEN_TTL_MS - 1 };
    expect(await uploadAndFinalize(deps, session, PAYLOAD)).toEqual({ type: "EXPIRED", run: 3 });
    expect(calls).toHaveLength(0);
  });

  it.each([
    ["media", 401, "session", 1],
    ["media", 413, "tooLarge", 1],
    ["media", 409, "conflict", 1],
    ["media", 422, "invalid", 1],
    ["signals", 422, "invalid", 2],
    ["signals", 401, "session", 2],
    ["finalize", 409, "conflict", 3],
    ["finalize", 500, "server", 3],
    ["finalize", 503, "server", 3],
  ])("lỗi ở bước %s (HTTP %i) thành %s và dừng ngay", async (step, status, kind, callCount) => {
    const replies: Reply[] = [];
    if (step !== "media") replies.push(ACK_MEDIA);
    if (step === "finalize") replies.push(ACK_SIGNALS);
    replies.push({ status, body: { error_code: "x", message: "y" } });
    const { deps, calls } = makeDeps(replies);

    expect(await uploadAndFinalize(deps, SESSION, PAYLOAD)).toEqual({
      type: "FAILED",
      kind,
      run: 3,
    });
    expect(calls).toHaveLength(callCount); // không gọi tiếp các bước sau
  });

  it("mất mạng giữa chừng (ở finalize) thành network", async () => {
    const { deps } = makeDeps([
      ACK_MEDIA,
      ACK_SIGNALS,
      { throws: new TypeError("Failed to fetch") },
    ]);
    expect(await uploadAndFinalize(deps, SESSION, PAYLOAD)).toEqual({
      type: "FAILED",
      kind: "network",
      run: 3,
    });
  });

  it("máy chủ trả trang lỗi không phải JSON (502) vẫn thành server, không ném lỗi", async () => {
    const { deps } = makeDeps([{ status: 502, raw: "<html>Bad Gateway</html>" }]);
    expect(await uploadAndFinalize(deps, SESSION, PAYLOAD)).toEqual({
      type: "FAILED",
      kind: "server",
      run: 3,
    });
  });

  it("finalize trả 200 nhưng thân hỏng là lỗi máy chủ (không phải mạng, không phải đạt)", async () => {
    const { deps } = makeDeps([ACK_MEDIA, ACK_SIGNALS, { status: 200, raw: "{không phải json" }]);
    const event = await uploadAndFinalize(deps, SESSION, PAYLOAD);
    expect(event).toEqual({ type: "FAILED", kind: "server", run: 3 });
    expect(reduce(toUploading(), event)).toEqual({ step: "error", kind: "server" });
  });
});

// --- Hủy khi rời trang -----------------------------------------------------------------------

describe("hủy lời gọi khi rời trang (AbortSignal)", () => {
  it("signal được nối tới fetch của từng bước", async () => {
    const controller = new AbortController();
    const { deps, calls } = makeDeps([ACK_MEDIA, ACK_SIGNALS, { body: { status: "pass" } }]);
    await uploadAndFinalize(deps, SESSION, PAYLOAD, controller.signal);
    for (const call of calls) expect(call.init.signal).toBe(controller.signal);
  });

  it("hủy giữa lúc đang gửi media: fetch bị hủy, trả FAILED interrupted, không gọi bước sau", async () => {
    const controller = new AbortController();
    const { deps, calls } = makeDeps([{ hang: true }]);
    const pending = uploadAndFinalize(deps, SESSION, PAYLOAD, controller.signal);
    controller.abort();
    expect(await pending).toEqual({ type: "FAILED", kind: "interrupted", run: 3 });
    expect(calls).toHaveLength(1);
  });

  it("hủy giữa các bước (sau media) thì không gửi signals và finalize", async () => {
    const controller = new AbortController();
    const { deps, calls } = makeDeps([ACK_MEDIA, ACK_SIGNALS, { body: { status: "pass" } }]);
    // hủy ngay khi lời gọi media vừa trả về
    const originalFetch = deps.client;
    const wrapped: RunnerDeps = {
      ...deps,
      client: {
        ...originalFetch,
        uploadMedia: async (...args) => {
          const res = await originalFetch.uploadMedia(...args);
          controller.abort();
          return res;
        },
      },
    };
    const event = await uploadAndFinalize(wrapped, SESSION, PAYLOAD, controller.signal);
    expect(event).toEqual({ type: "FAILED", kind: "interrupted", run: 3 });
    expect(calls).toHaveLength(1); // chỉ có media
  });

  it("hủy khi đang tạo phiên trả FAILED interrupted (không phải lỗi mạng)", async () => {
    const controller = new AbortController();
    const { deps } = makeDeps([{ hang: true }]);
    const pending = startSession(deps, { run: 4, signal: controller.signal });
    controller.abort();
    expect(await pending).toEqual({ type: "FAILED", kind: "interrupted", run: 4 });
  });
});

// --- Bốn nhánh đi qua reducer ----------------------------------------------------------------

async function finalizeWith(body: unknown): Promise<FlowState> {
  const { deps } = makeDeps([ACK_MEDIA, ACK_SIGNALS, { body }]);
  const event = await uploadAndFinalize(deps, SESSION, PAYLOAD);
  return reduce(toUploading(), event);
}

describe("bốn nhánh kết quả của finalize", () => {
  it("pass → result pass", async () => {
    expect(await finalizeWith({ status: "pass" })).toEqual({ step: "result", outcome: "pass" });
  });

  it("review → result review (không phải pass)", async () => {
    expect(await finalizeWith({ status: "review" })).toEqual({ step: "result", outcome: "review" });
  });

  it("retry → bước retry với gợi ý chất lượng và thử thách MỚI", async () => {
    const state = await finalizeWith({
      status: "retry",
      retry_hint: "MORE_LIGHT",
      attempts_left: 1,
      challenge: challenge("ch_2"),
    });
    expect(state.step).toBe("retry");
    if (state.step === "retry") {
      expect(state.hint).toBe("MORE_LIGHT");
      expect(state.attemptsLeft).toBe(1);
      expect(state.session.challenge.challenge_id).toBe("ch_2");
      expect(state.session.token).toBe("tok_1");
      // thử thách mới có mốc xin riêng (thời điểm trước khi gọi finalize)
      expect(state.session.challengeIssuedAtMono).toBe(0);
      // bấm "Thử lại" quay về nháy màu với thử thách mới
      const next = reduce(state, { type: "RETRY_CONTINUE" });
      expect(next.step).toBe("flash_challenge");
      if (next.step === "flash_challenge") {
        expect(next.session.challenge.challenge_id).toBe("ch_2");
      }
    }
  });

  it("voice_challenge → bước đọc câu, rồi review sau khi gửi giọng nói", async () => {
    const state = await finalizeWith({
      status: "voice_challenge",
      voice_prompt: "Hôm nay trời đẹp.",
      attempts_left: 1,
    });
    expect(state.step).toBe("voice_challenge");
    if (state.step !== "voice_challenge") return;
    expect(state.prompt).toBe("Hôm nay trời đẹp.");

    const { deps, calls } = makeDeps([{ body: { status: "review" } }]);
    const sending = reduce(state, { type: "VOICE_SENDING" });
    const event = await sendVoiceAnswer(deps, state.session, new Blob(["RIFF"]));
    expect(calls[0].url).toBe("http://api.test/v1/sessions/ses_1/voice");
    expect(reduce(sending, event)).toEqual({ step: "result", outcome: "review" });
  });

  it("voice pass là cách duy nhất để đạt sau voice_challenge", async () => {
    const state = await finalizeWith({ status: "voice_challenge", voice_prompt: "Câu thử." });
    if (state.step !== "voice_challenge") throw new Error("phải ở voice_challenge");
    const { deps } = makeDeps([{ body: { status: "pass" } }]);
    const event = await sendVoiceAnswer(deps, state.session, new Blob(["RIFF"]));
    expect(reduce(state, event)).toEqual({ step: "result", outcome: "pass" });
  });

  it("đọc sai câu: voice_challenge lần nữa với câu mới", async () => {
    const state = await finalizeWith({ status: "voice_challenge", voice_prompt: "Câu một." });
    if (state.step !== "voice_challenge") throw new Error("phải ở voice_challenge");
    const { deps } = makeDeps([
      { body: { status: "voice_challenge", voice_prompt: "Câu hai.", attempts_left: 0 } },
    ]);
    const next = reduce(state, await sendVoiceAnswer(deps, state.session, new Blob(["RIFF"])));
    expect(next.step).toBe("voice_challenge");
    if (next.step === "voice_challenge") {
      expect(next.prompt).toBe("Câu hai.");
      expect(next.rereadsLeft).toBe(0);
    }
  });
});

// --- Lỗi không bao giờ hiện như "đạt" --------------------------------------------------------

describe("lỗi không bao giờ thành kết quả đạt", () => {
  it.each([400, 401, 403, 404, 409, 413, 422, 429, 500, 502, 503])(
    "HTTP %i ở bất kỳ bước nào kết thúc ở error",
    async (status) => {
      for (const failAt of [0, 1, 2]) {
        const replies: Reply[] = [ACK_MEDIA, ACK_SIGNALS, { body: { status: "pass" } }];
        replies[failAt] = { status, body: { error_code: "x", message: "y" } };
        const { deps } = makeDeps(replies);
        const state = reduce(toUploading(), await uploadAndFinalize(deps, SESSION, PAYLOAD));
        expect(state.step).toBe("error");
      }
    },
  );

  it("mất mạng ở bất kỳ bước nào kết thúc ở error", async () => {
    for (const failAt of [0, 1, 2]) {
      const replies: Reply[] = [ACK_MEDIA, ACK_SIGNALS, { body: { status: "pass" } }];
      replies[failAt] = { throws: new TypeError("Failed to fetch") };
      const { deps } = makeDeps(replies);
      const state = reduce(toUploading(), await uploadAndFinalize(deps, SESSION, PAYLOAD));
      expect(state).toEqual({ step: "error", kind: "network" });
    }
  });

  it("phản hồi 200 nhưng sai dạng thành error, không thành pass", async () => {
    for (const body of [{}, { status: "PASS" }, { status: "ok" }, { status: 1 }, null, "pass"]) {
      expect((await finalizeWith(body)).step).toBe("error");
    }
  });

  it("lỗi khi gửi giọng nói thành error, không thành pass", async () => {
    const state = await finalizeWith({ status: "voice_challenge", voice_prompt: "Câu thử." });
    if (state.step !== "voice_challenge") throw new Error("phải ở voice_challenge");
    for (const reply of [
      { status: 409, body: { error_code: "voice_not_requested", message: "x" } },
      { status: 413, body: { error_code: "upload_too_large", message: "x" } },
      { throws: new TypeError("Failed to fetch") },
    ] as Reply[]) {
      const { deps } = makeDeps([reply]);
      const next = reduce(state, await sendVoiceAnswer(deps, state.session, new Blob(["RIFF"])));
      expect(next.step).toBe("error");
    }
  });

  it("sau error, không sự kiện nào đưa luồng sang kết quả đạt (chỉ RESTART mới thoát)", () => {
    const failed = reduce(toUploading(), { type: "FAILED", kind: "network" });
    const after = reduce(failed, { type: "FINALIZE_RESULT", response: { status: "pass" } });
    expect(after).toEqual(failed);
    expect(reduce(failed, { type: "RESTART" }).step).toBe("framing");
  });

  it("thử thách hết hạn đưa về tạo phiên mới và không gửi lại dữ liệu cũ", async () => {
    const { deps, calls } = makeDeps([], { now: CHALLENGE_TTL_MS + 1 });
    const event = await uploadAndFinalize(deps, SESSION, PAYLOAD);
    const state = reduce(toUploading(), { ...event, nextRun: 10 } as FlowEvent);
    expect(state).toEqual({ step: "creating_session", run: 10, expiredStreak: 1 });
    expect(calls).toHaveLength(0);
  });

  it("kết quả muộn của lần chạy cũ không ghi đè lần chạy mới", async () => {
    // lần chạy 3 đang gửi; người dùng bắt đầu lại (lần 8) rồi kết quả cũ mới về
    const { deps } = makeDeps([ACK_MEDIA, ACK_SIGNALS, { body: { status: "pass" } }]);
    const late = await uploadAndFinalize(deps, SESSION, PAYLOAD);
    const newer: FlowState = { step: "uploading", session: { ...SESSION, run: 8 } };
    expect(reduce(newer, late)).toBe(newer);
  });

  it("chuỗi hết hạn liên tiếp dừng ở lỗi phiên thay vì lặp mãi", async () => {
    const mono = { now: 0 };
    let state: FlowState = {
      step: "creating_session",
      run: 1,
      expiredStreak: 0,
    };
    for (let round = 1; round <= 3 && state.step === "creating_session"; round += 1) {
      const { deps } = makeDeps([{ body: CREATE_OK }], mono);
      state = reduce(state, await startSession(deps, { run: state.run }));
      if (state.step !== "flash_challenge") break;
      mono.now += CHALLENGE_TTL_MS + 1000; // người dùng nán lại, hết hạn trước khi gửi
      const { deps: d2 } = makeDeps([], mono);
      const expired = await uploadAndFinalize(d2, state.session, PAYLOAD);
      state = reduce({ step: "uploading", session: state.session }, {
        ...(expired as object),
        nextRun: round + 1,
      } as FlowEvent);
    }
    expect(state).toEqual({ step: "error", kind: "session" });
  });
});
