import { describe, expect, it } from "vitest";

import { detectBrowser, readCameraSettings } from "./device";
import { buildFileName } from "./record";

const UA = {
  chromeAndroid:
    "Mozilla/5.0 (Linux; Android 13; Redmi Note 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
  safariIphone:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
  chromeIphone:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0.0.0 Mobile/15E148 Safari/604.1",
  edge: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
  firefox: "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
  samsung:
    "Mozilla/5.0 (Linux; Android 13; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/24.0 Chrome/117.0.0.0 Mobile Safari/537.36",
};

describe("detectBrowser", () => {
  it("nhận ra từng trình duyệt, kể cả Chrome/Edge giả danh Safari", () => {
    expect(detectBrowser(UA.chromeAndroid)).toBe("chrome");
    expect(detectBrowser(UA.safariIphone)).toBe("safari");
    expect(detectBrowser(UA.chromeIphone)).toBe("chrome");
    expect(detectBrowser(UA.edge)).toBe("edge");
    expect(detectBrowser(UA.firefox)).toBe("firefox");
    expect(detectBrowser(UA.samsung)).toBe("samsung");
    expect(detectBrowser("curl/8.0")).toBe("other");
  });
});

describe("buildFileName với lần thử không hợp lệ", () => {
  it("NaN hoặc số âm thành lần 01", () => {
    const base = { device: "Redmi", browser: "chrome", scenario: "real" as const };
    expect(buildFileName({ ...base, take: Number.NaN })).toBe("redmi_chrome_real_01.json");
    expect(buildFileName({ ...base, take: -3 })).toBe("redmi_chrome_real_01.json");
  });
});

describe("readCameraSettings", () => {
  const fakeTrack = {
    getSettings: () => ({
      width: 1280,
      height: 720,
      deviceId: "abc123",
      groupId: "grp9",
      exposureMode: "continuous",
    }),
    getCapabilities: () => ({ exposureMode: ["manual", "continuous"], zoom: { max: 4 } }),
  } as unknown as MediaStreamTrack;

  it("bỏ deviceId và groupId nhưng giữ cài đặt khác và các chế độ phơi sáng", () => {
    const out = readCameraSettings(fakeTrack);
    expect(out).not.toHaveProperty("deviceId");
    expect(out).not.toHaveProperty("groupId");
    expect(out).toMatchObject({ width: 1280, height: 720, exposureMode: "continuous" });
    expect(out.capability_modes).toEqual({ exposureMode: ["manual", "continuous"] });
    expect(JSON.stringify(out)).not.toContain("abc123");
  });

  it("không có track thì trả về đối tượng rỗng", () => {
    expect(readCameraSettings(null)).toEqual({});
  });
});
