import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { ApiError, type Challenge } from "@/lib/api/client";

import {
  CHALLENGE_TTL_MS,
  classifyError,
  challengeRemainingMs,
  hasTimeToFlash,
  initialState,
  isValidIsoDate,
  normalizeHint,
  photoHint,
  reduce,
  RETRY_HINTS,
  sessionExpired,
  tokenRemainingMs,
  TOKEN_TTL_MS,
  UPLOAD_SLACK_MS,
  type ErrorKind,
  type FlowEvent,
  type FlowState,
  type SessionInfo,
} from "./flow";

const FUTURE = "2999-01-01T00:00:00.000Z";

function makeChallenge(id = "ch-1"): Challenge {
  return {
    challenge_id: id,
    color_sequence: Array.from({ length: 8 }, () => ({
      hold_ms: 400,
      rgb: "#ff0000",
      transition_ms: 150 as const,
    })),
    baseline_ms: 1000,
    expires_at: FUTURE,
  };
}

function makeSession(id = "ch-1"): SessionInfo {
  return {
    sessionId: "sess-1",
    token: "tok-1",
    challenge: makeChallenge(id),
    run: 0,
    tokenIssuedAtMono: 0,
    challengeIssuedAtMono: 0,
    expiredStreak: 0,
  };
}

function run(state: FlowState, ...events: FlowEvent[]): FlowState {
  return events.reduce(reduce, state);
}

const session = makeSession();

const uploading: FlowState = { step: "uploading", session };
const voiceState: FlowState = {
  step: "voice_challenge",
  session,
  prompt: "Một hai ba",
  rereadsLeft: 2,
  sending: false,
};

const ALL_STATES: FlowState[] = [
  { step: "consent", accepted: true },
  { step: "camera_permission", problem: null },
  { step: "framing" },
  { step: "quality_check" },
  { step: "creating_session", run: 0, expiredStreak: 0 },
  { step: "flash_challenge", session },
  uploading,
  { step: "retry", session, hint: null, attemptsLeft: 1 },
  voiceState,
  { step: "result", outcome: "pass" },
  { step: "result", outcome: "review" },
  { step: "error", kind: "network" },
];

const ALL_KINDS: ErrorKind[] = [
  "network",
  "session",
  "conflict",
  "tooLarge",
  "invalid",
  "server",
  "unexpected",
  "stopped",
  "interrupted",
];

describe("đồng ý", () => {
  it("trạng thái đầu là consent, chưa tích sẵn", () => {
    expect(initialState).toEqual({ step: "consent", accepted: false });
  });

  it("CONTINUE khi chưa tích thì không đi tiếp", () => {
    expect(reduce(initialState, { type: "CONTINUE" })).toEqual({
      step: "consent",
      accepted: false,
    });
  });

  it("tích rồi CONTINUE thì sang camera_permission", () => {
    const next = run(
      initialState,
      { type: "TOGGLE_CONSENT", accepted: true },
      { type: "CONTINUE" },
    );
    expect(next).toEqual({ step: "camera_permission", problem: null });
  });

  it("tích rồi bỏ tích thì CONTINUE không đi", () => {
    const next = run(
      initialState,
      { type: "TOGGLE_CONSENT", accepted: true },
      { type: "TOGGLE_CONSENT", accepted: false },
      { type: "CONTINUE" },
    );
    expect(next).toEqual({ step: "consent", accepted: false });
  });
});

describe("đường đi đầy đủ", () => {
  it("nhánh pass đi hết các bước", () => {
    let s = initialState;
    const seen: string[] = [s.step];
    const events: FlowEvent[] = [
      { type: "TOGGLE_CONSENT", accepted: true },
      { type: "CONTINUE" },
      { type: "CAMERA_GRANTED" },
      { type: "FRAMING_READY" },
      { type: "QUALITY_PASSED" },
      { type: "SESSION_CREATED", session },
      { type: "FLASH_DONE" },
      { type: "FINALIZE_RESULT", response: { status: "pass" } },
    ];
    for (const e of events) {
      s = reduce(s, e);
      seen.push(s.step);
    }
    expect(seen).toEqual([
      "consent",
      "consent",
      "camera_permission",
      "framing",
      "quality_check",
      "creating_session",
      "flash_challenge",
      "uploading",
      "result",
    ]);
    expect(s).toEqual({ step: "result", outcome: "pass" });
  });

  it("SESSION_CREATED giữ nguyên session", () => {
    const s = reduce(
      { step: "creating_session", run: 0, expiredStreak: 0 },
      { type: "SESSION_CREATED", session },
    );
    expect(s).toEqual({ step: "flash_challenge", session });
  });

  it("FLASH_DONE giữ session khi sang uploading", () => {
    const s = reduce({ step: "flash_challenge", session }, { type: "FLASH_DONE" });
    expect(s).toEqual({ step: "uploading", session });
  });
});

describe("FINALIZE_RESULT", () => {
  it("review ra outcome review, không phải pass", () => {
    const s = reduce(uploading, { type: "FINALIZE_RESULT", response: { status: "review" } });
    expect(s).toEqual({ step: "result", outcome: "review" });
  });

  describe("retry", () => {
    const fresh = makeChallenge("ch-2");
    const retryResponse = {
      status: "retry",
      retry_hint: "MORE_LIGHT",
      attempts_left: 1,
      challenge: fresh,
    };

    it("sang retry với hint, attemptsLeft và challenge mới", () => {
      const s = reduce(uploading, { type: "FINALIZE_RESULT", response: retryResponse });
      expect(s.step).toBe("retry");
      if (s.step !== "retry") return;
      expect(s.hint).toBe("MORE_LIGHT");
      expect(s.attemptsLeft).toBe(1);
      expect(s.session.challenge).toEqual(fresh);
      expect(s.session.challenge.challenge_id).not.toBe(session.challenge.challenge_id);
      expect(s.session.token).toBe(session.token);
      expect(s.session.sessionId).toBe(session.sessionId);
    });

    it("RETRY_CONTINUE sang flash_challenge với challenge mới", () => {
      const s = run(
        uploading,
        { type: "FINALIZE_RESULT", response: retryResponse },
        { type: "RETRY_CONTINUE" },
      );
      expect(s.step).toBe("flash_challenge");
      if (s.step !== "flash_challenge") return;
      expect(s.session.challenge.challenge_id).toBe("ch-2");
    });

    it("thiếu challenge thì lỗi unexpected", () => {
      const s = reduce(uploading, {
        type: "FINALIZE_RESULT",
        response: { status: "retry", retry_hint: "MORE_LIGHT", attempts_left: 1 },
      });
      expect(s).toEqual({ step: "error", kind: "unexpected" });
    });

    it.each([
      ["null", null],
      ["{}", {}],
      ["color_sequence rỗng", { challenge_id: "x", color_sequence: [] }],
      ["thiếu challenge_id", { color_sequence: [{}] }],
    ])("challenge không dùng được (%s) thì lỗi unexpected", (_name, challenge) => {
      const s = reduce(uploading, {
        type: "FINALIZE_RESULT",
        response: { status: "retry", challenge },
      });
      expect(s).toEqual({ step: "error", kind: "unexpected" });
    });

    it.each([["FOO"], [null], [42], [undefined]])("retry_hint lạ (%s) thì hint null", (hint) => {
      const s = reduce(uploading, {
        type: "FINALIZE_RESULT",
        response: { status: "retry", retry_hint: hint, challenge: fresh, attempts_left: 2 },
      });
      expect(s.step).toBe("retry");
      if (s.step === "retry") expect(s.hint).toBeNull();
    });

    it("thiếu retry_hint thì hint null", () => {
      const s = reduce(uploading, {
        type: "FINALIZE_RESULT",
        response: { status: "retry", challenge: fresh },
      });
      expect(s.step === "retry" && s.hint).toBeNull();
    });

    it("thiếu attempts_left thì attemptsLeft null", () => {
      const s = reduce(uploading, {
        type: "FINALIZE_RESULT",
        response: { status: "retry", challenge: fresh },
      });
      expect(s.step).toBe("retry");
      if (s.step === "retry") expect(s.attemptsLeft).toBeNull();
    });
  });

  describe("voice_challenge", () => {
    it("có voice_prompt thì sang voice_challenge, prompt được trim", () => {
      const s = reduce(uploading, {
        type: "FINALIZE_RESULT",
        response: { status: "voice_challenge", voice_prompt: "  Bảy tám chín  ", attempts_left: 2 },
      });
      expect(s).toEqual({
        step: "voice_challenge",
        session,
        prompt: "Bảy tám chín",
        rereadsLeft: 2,
        sending: false,
      });
    });

    it.each([
      ["thiếu", undefined],
      ["rỗng", ""],
      ["chỉ khoảng trắng", "   \n\t"],
      ["không phải chuỗi", 123],
    ])("voice_prompt %s thì lỗi unexpected", (_name, voice_prompt) => {
      const s = reduce(uploading, {
        type: "FINALIZE_RESULT",
        response: { status: "voice_challenge", voice_prompt },
      });
      expect(s).toEqual({ step: "error", kind: "unexpected" });
    });
  });
});

describe("VOICE_*", () => {
  it("VOICE_SENDING đặt sending true", () => {
    const s = reduce(voiceState, { type: "VOICE_SENDING" });
    expect(s).toEqual({ ...voiceState, sending: true });
  });

  it("pass ra result pass", () => {
    expect(reduce(voiceState, { type: "VOICE_RESULT", response: { status: "pass" } })).toEqual({
      step: "result",
      outcome: "pass",
    });
  });

  it("review ra result review", () => {
    expect(reduce(voiceState, { type: "VOICE_RESULT", response: { status: "review" } })).toEqual({
      step: "result",
      outcome: "review",
    });
  });

  it("voice_challenge với prompt mới vẫn ở voice_challenge, sending false", () => {
    const sending = reduce(voiceState, { type: "VOICE_SENDING" });
    const s = reduce(sending, {
      type: "VOICE_RESULT",
      response: { status: "voice_challenge", voice_prompt: " Câu mới ", attempts_left: 1 },
    });
    expect(s).toEqual({
      step: "voice_challenge",
      session,
      prompt: "Câu mới",
      rereadsLeft: 1,
      sending: false,
    });
  });

  it("voice_challenge thiếu prompt thì lỗi", () => {
    const s = reduce(voiceState, {
      type: "VOICE_RESULT",
      response: { status: "voice_challenge" },
    });
    expect(s).toEqual({ step: "error", kind: "unexpected" });
  });

  it("status lạ thì lỗi", () => {
    const s = reduce(voiceState, { type: "VOICE_RESULT", response: { status: "retry" } });
    expect(s).toEqual({ step: "error", kind: "unexpected" });
  });
});

describe("an toàn: chỉ đúng {status:'pass'} mới ra pass", () => {
  const STRANGE: [string, unknown][] = [
    ["retry không challenge", { status: "retry" }],
    ["status ok", { status: "ok" }],
    ["PASS hoa", { status: "PASS" }],
    ["status số", { status: 1 }],
    ["status true", { status: true }],
    ["null", null],
    ["undefined", undefined],
    ["chuỗi 'pass'", "pass"],
    ["mảng", [{ status: "pass" }]],
    ["object rỗng", {}],
    ["'pass ' có dấu cách", { status: "pass " }],
    [" pass", { status: " pass" }],
  ];

  describe.each([
    ["uploading", uploading, "FINALIZE_RESULT"],
    ["voice_challenge", voiceState, "VOICE_RESULT"],
  ] as const)("ở bước %s", (_name, state, type) => {
    it.each(STRANGE)("%s không thành pass", (_label, response) => {
      const s = reduce(state, { type, response });
      expect(s).not.toEqual({ step: "result", outcome: "pass" });
      expect(s.step === "result" && s.outcome === "pass").toBe(false);
    });

    it.each(STRANGE)("%s đi tới error unexpected", (_label, response) => {
      // 'retry' không challenge cũng là lỗi ở uploading; ở voice thì status lạ cũng lỗi.
      expect(reduce(state, { type, response })).toEqual({ step: "error", kind: "unexpected" });
    });

    it("đúng {status:'pass'} thì ra pass", () => {
      expect(reduce(state, { type, response: { status: "pass" } })).toEqual({
        step: "result",
        outcome: "pass",
      });
    });
  });
});

describe("FAILED, RESTART và trạng thái cuối", () => {
  it.each(
    ALL_STATES.map((s) => [s.step + (s.step === "result" ? `:${s.outcome}` : ""), s] as const),
  )("FAILED từ %s: ra error đúng kind (trừ kết quả cuối, giữ nguyên)", (_name, state) => {
    for (const kind of ALL_KINDS) {
      const s = reduce(state, { type: "FAILED", kind });
      if (state.step === "result") {
        expect(s).toBe(state); // result là trạng thái cuối: lỗi đến muộn không đổi được
      } else {
        expect(s).toEqual({ step: "error", kind });
        expect(s.step).not.toBe("result");
      }
    }
  });

  it("error không rời đi khi nhận sự kiện khác", () => {
    const err: FlowState = { step: "error", kind: "server" };
    const events: FlowEvent[] = [
      { type: "FINALIZE_RESULT", response: { status: "pass" } },
      { type: "VOICE_RESULT", response: { status: "pass" } },
      { type: "FLASH_DONE" },
      { type: "CONTINUE" },
      { type: "CAMERA_GRANTED" },
      { type: "EXPIRED" },
      { type: "RETRY_CONTINUE" },
      { type: "SESSION_CREATED", session },
    ];
    for (const e of events) expect(reduce(err, e)).toBe(err);
  });

  it("result là trạng thái cuối với sự kiện thường", () => {
    const res: FlowState = { step: "result", outcome: "review" };
    const events: FlowEvent[] = [
      { type: "FINALIZE_RESULT", response: { status: "pass" } },
      { type: "VOICE_RESULT", response: { status: "pass" } },
      { type: "CONTINUE" },
      { type: "EXPIRED" },
    ];
    for (const e of events) expect(reduce(res, e)).toBe(res);
  });

  it("RESTART từ error về framing", () => {
    expect(reduce({ step: "error", kind: "session" }, { type: "RESTART" })).toEqual({
      step: "framing",
    });
  });
});

describe("dừng, gián đoạn, hết hạn", () => {
  const flash: FlowState = { step: "flash_challenge", session };

  it("FLASH_STOPPED ra error stopped", () => {
    expect(reduce(flash, { type: "FLASH_STOPPED" })).toEqual({ step: "error", kind: "stopped" });
  });

  it("FLASH_INTERRUPTED ra error interrupted", () => {
    expect(reduce(flash, { type: "FLASH_INTERRUPTED" })).toEqual({
      step: "error",
      kind: "interrupted",
    });
  });

  it.each([
    ["flash_challenge", flash],
    ["uploading", uploading],
    ["retry", { step: "retry", session, hint: null, attemptsLeft: 1 } as FlowState],
  ])("EXPIRED từ %s về creating_session, không giữ session", (_name, state) => {
    const s = reduce(state, { type: "EXPIRED" });
    // hết hạn lần đầu: tạo phiên mới (mã lần chạy tăng, chuỗi hết hạn = 1), không giữ session cũ
    expect(s).toEqual({ step: "creating_session", run: 1, expiredStreak: 1 });
    expect("session" in s).toBe(false);
  });
});

describe("sự kiện sai bước bị bỏ qua", () => {
  it.each([
    [
      "FLASH_DONE ở consent",
      { step: "consent", accepted: true } as FlowState,
      { type: "FLASH_DONE" } as FlowEvent,
    ],
    [
      "FINALIZE_RESULT ở framing",
      { step: "framing" } as FlowState,
      { type: "FINALIZE_RESULT", response: { status: "pass" } } as FlowEvent,
    ],
    [
      "VOICE_RESULT ở uploading",
      uploading,
      { type: "VOICE_RESULT", response: { status: "pass" } } as FlowEvent,
    ],
    [
      "QUALITY_PASSED ở framing",
      { step: "framing" } as FlowState,
      { type: "QUALITY_PASSED" } as FlowEvent,
    ],
    [
      "SESSION_CREATED ở quality_check",
      { step: "quality_check" } as FlowState,
      { type: "SESSION_CREATED", session } as FlowEvent,
    ],
    [
      "FRAMING_READY ở consent",
      { step: "consent", accepted: true } as FlowState,
      { type: "FRAMING_READY" } as FlowEvent,
    ],
  ])("%s trả đúng state cũ", (_name, state, event) => {
    expect(reduce(state, event)).toBe(state);
  });
});

describe("camera", () => {
  it("CAMERA_FAILED giữ ở camera_permission kèm problem", () => {
    const s = reduce(
      { step: "camera_permission", problem: null },
      { type: "CAMERA_FAILED", problem: "denied" },
    );
    expect(s).toEqual({ step: "camera_permission", problem: "denied" });
  });

  it("CONTINUE xóa problem để thử lại", () => {
    const s = reduce({ step: "camera_permission", problem: "denied" }, { type: "CONTINUE" });
    expect(s).toEqual({ step: "camera_permission", problem: null });
  });
});

describe("classifyError", () => {
  it.each([
    [401, "session"],
    [409, "conflict"],
    [413, "tooLarge"],
    [422, "invalid"],
    [500, "server"],
    [502, "server"],
    [503, "server"],
    [404, "unexpected"],
    [400, "unexpected"],
    [429, "unexpected"],
  ] as const)("ApiError %i ra %s", (status, kind) => {
    expect(classifyError(new ApiError(status, "code", "msg"))).toBe(kind);
  });

  it("TypeError mất mạng ra network", () => {
    expect(classifyError(new TypeError("Failed to fetch"))).toBe("network");
  });

  it.each([
    ["Error thường", new Error("boom")],
    ["chuỗi", "oops"],
    ["null", null],
    ["undefined", undefined],
  ])("%s ra network", (_name, value) => {
    expect(classifyError(value)).toBe("network");
  });

  it("đối tượng giả tên ApiError nhưng status không phải số ra network", () => {
    expect(classifyError({ name: "ApiError", status: "500" })).toBe("network");
    expect(classifyError({ name: "ApiError" })).toBe("network");
  });
});

describe("normalizeHint / RETRY_HINTS", () => {
  it.each(RETRY_HINTS.map((h) => [h]))("giữ nguyên %s", (hint) => {
    expect(normalizeHint(hint)).toBe(hint);
  });

  it.each([["FOO"], ["more_light"], [""], [5], [null], [undefined], [{}]])(
    "giá trị lạ %s ra null",
    (value) => {
      expect(normalizeHint(value)).toBeNull();
    },
  );

  it("RETRY_HINTS có đúng 7 phần tử", () => {
    expect(RETRY_HINTS).toHaveLength(7);
    expect(new Set(RETRY_HINTS).size).toBe(7);
  });

  it("RETRY_HINTS khớp enum retry_hint trong schema.d.ts", () => {
    const file = path.resolve(import.meta.dirname, "../api/schema.d.ts");
    const text = readFileSync(file, "utf8");
    const line = text.split("\n").find((l) => l.includes("retry_hint?:"));
    expect(line).toBeDefined();
    const fromSchema = new Set([...(line ?? "").matchAll(/"([A-Z_]+)"/g)].map((m) => m[1]));
    expect(fromSchema.size).toBe(7);
    expect(fromSchema).toEqual(new Set<string>(RETRY_HINTS));
  });
});

describe("hết hạn theo đồng hồ đơn điệu (không so giờ máy)", () => {
  const issued = (mono: number): SessionInfo => ({
    ...session,
    tokenIssuedAtMono: mono,
    challengeIssuedAtMono: mono,
  });

  it("thử thách sống 120 giây tính từ mốc xin", () => {
    const s = issued(1000);
    expect(challengeRemainingMs(s, 1000)).toBe(CHALLENGE_TTL_MS);
    expect(sessionExpired(s, 1000 + CHALLENGE_TTL_MS - 1)).toBe(false);
    expect(sessionExpired(s, 1000 + CHALLENGE_TTL_MS)).toBe(true);
  });

  it("token hết hạn theo TTL mặc định, tách khỏi thử thách", () => {
    const s: SessionInfo = { ...issued(0), challengeIssuedAtMono: 250_000 };
    expect(tokenRemainingMs(s, 250_000)).toBe(TOKEN_TTL_MS - 250_000);
    expect(sessionExpired(s, 250_000)).toBe(false);
    expect(sessionExpired(s, TOKEN_TTL_MS)).toBe(true);
  });

  it("giờ máy lệch (nhanh hay chậm 10 phút) không ảnh hưởng: expires_at trong phản hồi bị bỏ qua", () => {
    // Điện thoại nhanh +10 phút: expires_at của máy chủ tưởng như đã qua. Điện thoại chậm -10 phút: tưởng như còn lâu.
    const tooEarly = {
      ...issued(0),
      challenge: { ...session.challenge, expires_at: "2000-01-01T00:00:00Z" },
    };
    const tooLate = { ...issued(0), challenge: { ...session.challenge, expires_at: FUTURE } };
    for (const s of [tooEarly, tooLate]) {
      expect(sessionExpired(s, 60_000)).toBe(false);
      expect(sessionExpired(s, CHALLENGE_TTL_MS + 1)).toBe(true);
    }
  });

  it("mốc xin là -Infinity (không biết) thì coi là đã hết hạn", () => {
    expect(sessionExpired({ ...session, challengeIssuedAtMono: Number.NEGATIVE_INFINITY }, 0)).toBe(
      true,
    );
  });

  it("hasTimeToFlash cần đủ thời gian nháy cộng khoảng gửi", () => {
    const s = issued(0);
    const flash = 7000;
    expect(hasTimeToFlash(s, 0, flash)).toBe(true);
    expect(hasTimeToFlash(s, CHALLENGE_TTL_MS - flash - UPLOAD_SLACK_MS, flash)).toBe(false);
    expect(hasTimeToFlash(s, CHALLENGE_TTL_MS - flash - UPLOAD_SLACK_MS - 1, flash)).toBe(true);
  });

  it("isValidIsoDate chỉ nhận mốc ISO đọc được", () => {
    expect(isValidIsoDate("2026-10-15T08:00:00Z")).toBe(true);
    for (const bad of ["không phải ngày", "", null, undefined, 5, {}]) {
      expect(isValidIsoDate(bad)).toBe(false);
    }
  });
});

describe("chốt vòng lặp hết hạn", () => {
  it("hết hạn một lần thì tạo phiên mới; hai lần liên tiếp thì báo lỗi phiên", () => {
    const first = reduce(
      { step: "flash_challenge", session },
      { type: "EXPIRED", run: 0, nextRun: 1 },
    );
    expect(first).toEqual({ step: "creating_session", run: 1, expiredStreak: 1 });

    // phiên mới tạo xong (mang chuỗi hết hạn = 1) rồi lại hết hạn ngay
    const created = reduce(first, { type: "SESSION_CREATED", session: { ...session, run: 1 } });
    expect(created.step).toBe("flash_challenge");
    const second = reduce(created, { type: "EXPIRED", run: 1, nextRun: 2 });
    expect(second).toEqual({ step: "error", kind: "session" });
  });

  it("luồng có tiến triển (finalize trả retry) thì chuỗi hết hạn được đặt lại về 0", () => {
    const afterExpiry = reduce(
      reduce({ step: "uploading", session }, { type: "EXPIRED", run: 0, nextRun: 1 }),
      { type: "SESSION_CREATED", session: { ...session, run: 1 } },
    );
    if (afterExpiry.step !== "flash_challenge") throw new Error("phải ở flash_challenge");
    expect(afterExpiry.session.expiredStreak).toBe(1);

    const retry = reduce(
      { step: "uploading", session: afterExpiry.session },
      {
        type: "FINALIZE_RESULT",
        run: 1,
        requestedAtMono: 5,
        response: { status: "retry", challenge: makeChallenge("ch-2") },
      },
    );
    if (retry.step !== "retry") throw new Error("phải ở retry");
    expect(retry.session.expiredStreak).toBe(0);
    expect(retry.session.challengeIssuedAtMono).toBe(5);
  });

  it("retry thiếu mốc xin thì thử thách coi như đã hết hạn (không dùng nhầm)", () => {
    const retry = reduce(uploading, {
      type: "FINALIZE_RESULT",
      response: { status: "retry", challenge: makeChallenge("ch-2") },
    });
    if (retry.step !== "retry") throw new Error("phải ở retry");
    expect(sessionExpired(retry.session, 0)).toBe(true);
  });
});

describe("mã lần chạy: bỏ kết quả muộn của lần cũ", () => {
  const current: SessionInfo = { ...session, run: 5 };
  const uploadingNow: FlowState = { step: "uploading", session: current };

  it("FINALIZE_RESULT của lần chạy khác bị bỏ qua, đúng lần thì xử lý", () => {
    expect(
      reduce(uploadingNow, { type: "FINALIZE_RESULT", run: 4, response: { status: "pass" } }),
    ).toBe(uploadingNow);
    expect(
      reduce(uploadingNow, { type: "FINALIZE_RESULT", run: 5, response: { status: "pass" } }),
    ).toEqual({ step: "result", outcome: "pass" });
  });

  it("FAILED của lần chạy cũ không phá lần chạy hiện tại; FAILED không mã vẫn có tác dụng", () => {
    expect(reduce(uploadingNow, { type: "FAILED", kind: "network", run: 4 })).toBe(uploadingNow);
    expect(reduce(uploadingNow, { type: "FAILED", kind: "network", run: 5 })).toEqual({
      step: "error",
      kind: "network",
    });
    expect(reduce(uploadingNow, { type: "FAILED", kind: "network" })).toEqual({
      step: "error",
      kind: "network",
    });
  });

  it("VOICE_RESULT của lần chạy cũ bị bỏ qua", () => {
    const voice: FlowState = { ...voiceState, session: current };
    expect(reduce(voice, { type: "VOICE_RESULT", run: 3, response: { status: "pass" } })).toBe(
      voice,
    );
    expect(reduce(voice, { type: "VOICE_RESULT", run: 5, response: { status: "pass" } })).toEqual({
      step: "result",
      outcome: "pass",
    });
  });

  it("SESSION_CREATED của lần chạy khác bị bỏ qua", () => {
    const creating: FlowState = { step: "creating_session", run: 7, expiredStreak: 0 };
    expect(reduce(creating, { type: "SESSION_CREATED", session: { ...session, run: 6 } })).toBe(
      creating,
    );
    expect(
      reduce(creating, { type: "SESSION_CREATED", session: { ...session, run: 7 } }).step,
    ).toBe("flash_challenge");
  });

  it("FAILED của lần cũ khi đang tạo phiên mới bị bỏ qua", () => {
    const creating: FlowState = { step: "creating_session", run: 7, expiredStreak: 0 };
    expect(reduce(creating, { type: "FAILED", kind: "network", run: 6 })).toBe(creating);
  });

  it("EXPIRED muộn của lần cũ không đặt lại lần hiện tại", () => {
    expect(reduce(uploadingNow, { type: "EXPIRED", run: 4, nextRun: 9 })).toBe(uploadingNow);
  });

  it("QUALITY_PASSED mang mã lần chạy mới vào bước tạo phiên", () => {
    expect(reduce({ step: "quality_check" }, { type: "QUALITY_PASSED", run: 12 })).toEqual({
      step: "creating_session",
      run: 12,
      expiredStreak: 0,
    });
  });
});

describe("QUIET_PLACE chỉ có nghĩa ở bước đọc câu", () => {
  it("photoHint bỏ gợi ý âm thanh nhưng giữ gợi ý chất lượng ảnh", () => {
    expect(photoHint("QUIET_PLACE")).toBeNull();
    expect(photoHint("MORE_LIGHT")).toBe("MORE_LIGHT");
    expect(photoHint("FOO")).toBeNull();
  });

  it("retry ở bước chụp lại với QUIET_PLACE dùng câu chung (hint null)", () => {
    const retry = reduce(uploading, {
      type: "FINALIZE_RESULT",
      response: { status: "retry", retry_hint: "QUIET_PLACE", challenge: makeChallenge("ch-2") },
    });
    if (retry.step !== "retry") throw new Error("phải ở retry");
    expect(retry.hint).toBeNull();
  });
});
