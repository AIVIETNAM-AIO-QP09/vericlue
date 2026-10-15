// Thử cả 4 nhánh với API mock THẬT. Chỉ chạy khi đặt biến môi trường (CI bỏ qua):
//   1) uv run uvicorn vericlue_api.main:app --app-dir services/api/src      (API mock, cổng 8000)
//   2) cd apps/web && E2E_API_URL=http://localhost:8000 npx vitest run src/lib/capture/runner.e2e.test.ts
import { describe, expect, it } from "vitest";

import { createApiClient } from "@/lib/api/client";

import { type FlowEvent, type FlowState, initialState, reduce } from "./flow";
import { qualityGateEvents } from "./flowTestUtils";
import { type RunnerDeps, sendVoiceAnswer, startSession, uploadAndFinalize } from "./runner";

const API = process.env.E2E_API_URL;

const IMAGE = new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xd9])], { type: "image/jpeg" });
const SIGNALS = {
  color_events: [{ index: 0, rgb: "#ffcc73", painted_at: 1000 }],
  frame_times: [],
};

async function run(scenario: string, deps: RunnerDeps): Promise<FlowState> {
  const events: FlowEvent[] = [
    { type: "TOGGLE_CONSENT", accepted: true },
    { type: "CONTINUE" },
    { type: "CAMERA_GRANTED" },
    ...qualityGateEvents(1),
  ];
  let state = events.reduce(reduce, initialState);
  state = reduce(state, await startSession(deps, { run: 1 }, scenario));
  state = reduce(state, { type: "FLASH_DONE" });
  if (state.step !== "uploading") throw new Error(`mong đợi uploading, nhận ${state.step}`);
  return reduce(
    state,
    await uploadAndFinalize(deps, state.session, { image: IMAGE, signals: SIGNALS }),
  );
}

describe.skipIf(!API)("luồng /verify với API mock thật", () => {
  const deps = (): RunnerDeps => ({
    client: createApiClient({ baseUrl: API }),
    monoMs: () => performance.now(),
  });

  it("genuine → pass", async () => {
    expect(await run("genuine", deps())).toEqual({ step: "result", outcome: "pass" });
  });

  it.each(["print", "replay", "virtual_cam", "faceswap", "error"])("%s → review", async (name) => {
    expect(await run(name, deps())).toEqual({ step: "result", outcome: "review" });
  });

  it("low_quality → retry (thử thách mới, gợi ý chất lượng), rồi hết lượt thì review", async () => {
    const d = deps();
    let state = await run("low_quality", d);
    expect(state.step).toBe("retry");
    if (state.step !== "retry") return;
    expect(state.hint).toBe("MORE_LIGHT");
    expect(state.attemptsLeft).toBe(1);

    // lượt 2 và 3: gửi lại với thử thách mới
    let attempt = 0;
    for (const expected of ["retry", "result"]) {
      const gate = [...qualityGateEvents(2 + attempt)].reduce(
        reduce,
        reduce(state, { type: "RETRY_CONTINUE" }),
      );
      attempt += 1;
      const flash = reduce(gate, { type: "FLASH_DONE" });
      if (flash.step !== "uploading") throw new Error("phải ở uploading");
      state = reduce(
        flash,
        await uploadAndFinalize(d, flash.session, { image: IMAGE, signals: SIGNALS }),
      );
      expect(state.step).toBe(expected);
    }
    expect(state).toEqual({ step: "result", outcome: "review" });
  });

  it("voice_clone → voice_challenge, rồi review sau khi gửi giọng nói", async () => {
    const d = deps();
    const state = await run("voice_clone", d);
    expect(state.step).toBe("voice_challenge");
    if (state.step !== "voice_challenge") return;
    expect(state.prompt.length).toBeGreaterThan(0);
    const event = await sendVoiceAnswer(
      d,
      state.session,
      new Blob([new Uint8Array([0x52, 0x49, 0x46, 0x46])]),
    );
    expect(reduce(state, event)).toEqual({ step: "result", outcome: "review" });
  });

  it("token sai → lỗi session, không bao giờ pass", async () => {
    const d = deps();
    const created = await startSession(d, { run: 1 }, "genuine");
    if (created.type !== "SESSION_CREATED") throw new Error("không tạo được phiên");
    const bad = { ...created.session, token: "sai-token" };
    const event = await uploadAndFinalize(d, bad, { image: IMAGE, signals: SIGNALS });
    expect(event).toEqual({ type: "FAILED", kind: "session", run: 1 });
  });

  it("máy chủ không chạy → lỗi network", async () => {
    const down: RunnerDeps = {
      client: createApiClient({ baseUrl: "http://127.0.0.1:9" }),
      monoMs: () => performance.now(),
    };
    expect(await startSession(down, { run: 1 })).toEqual({
      type: "FAILED",
      kind: "network",
      run: 1,
    });
  });
});
