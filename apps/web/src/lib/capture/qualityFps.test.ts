import { describe, expect, it } from "vitest";

import {
  FPS_LOW_WINDOWS_REQUIRED,
  FPS_WARMUP_CALLBACKS,
  FPS_WINDOW,
  MIN_FPS,
  estimateFps,
  evaluateFpsWindows,
} from "./quality";

// Chống báo oan "Thiết bị hoặc trình duyệt chưa đáp ứng": một cửa sổ FPS thấp (khởi động, camera hạ FPS
// trong phòng tối...) chưa đủ để kết luận; phải thấp LIÊN TIẾP nhiều cửa sổ.
describe("evaluateFpsWindows", () => {
  it("chưa có cửa sổ nào hoặc chưa ước lượng được thì chưa kết luận", () => {
    expect(evaluateFpsWindows([])).toBe("need_more");
    expect(evaluateFpsWindows([null])).toBe("need_more");
  });

  it("cửa sổ đạt (>= 15 fps) là ổn, kể cả đúng 15", () => {
    expect(evaluateFpsWindows([30])).toBe("ok");
    expect(evaluateFpsWindows([MIN_FPS])).toBe("ok");
  });

  it("một cửa sổ thấp chưa đủ để báo thiết bị chưa đáp ứng", () => {
    expect(evaluateFpsWindows([MIN_FPS - 0.1])).toBe("need_more");
    expect(evaluateFpsWindows([5])).toBe("need_more");
  });

  it("thấp liên tiếp đủ số cửa sổ yêu cầu thì mới báo thấp", () => {
    const low = Array.from({ length: FPS_LOW_WINDOWS_REQUIRED }, () => 10);
    expect(evaluateFpsWindows(low)).toBe("low");
    expect(evaluateFpsWindows([...low, 8])).toBe("low");
  });

  it("cửa sổ thấp rồi hồi phục thì ổn, không báo oan", () => {
    expect(evaluateFpsWindows([10, 24])).toBe("ok");
    expect(evaluateFpsWindows([10, 10, 22])).toBe("ok");
  });

  it("thấp xen kẽ không liên tiếp không báo thấp", () => {
    expect(evaluateFpsWindows([10, 20, 10])).toBe("need_more");
  });

  it("cửa sổ cuối không ước lượng được thì chưa kết luận, kể cả khi trước đó thấp", () => {
    expect(evaluateFpsWindows([10, 10, null])).toBe("need_more");
  });
});

describe("tham số đo FPS", () => {
  it("bỏ qua khung khởi động và dùng cửa sổ đủ lớn cho trung vị", () => {
    expect(FPS_WARMUP_CALLBACKS).toBeGreaterThan(0);
    expect(FPS_WINDOW).toBeGreaterThanOrEqual(10); // estimateFps cần ít nhất 10 mốc
    expect(FPS_LOW_WINDOWS_REQUIRED).toBeGreaterThanOrEqual(2);
  });

  it("một cửa sổ camera 24 fps đo được ổn dù có vài khung bị trễ", () => {
    const times: number[] = [];
    let t = 0;
    for (let i = 0; i < FPS_WINDOW; i += 1) {
      t += i % 7 === 0 ? 120 : 1000 / 24; // vài khung trễ do việc nặng
      times.push(t);
    }
    expect(evaluateFpsWindows([estimateFps(times)])).toBe("ok");
  });

  it("cửa sổ camera chỉ 8 fps thật sự thấp (hai cửa sổ liên tiếp) thì báo thấp", () => {
    const window = Array.from({ length: FPS_WINDOW }, (_, i) => i * (1000 / 8));
    const fps = estimateFps(window);
    expect(fps).not.toBeNull();
    expect(evaluateFpsWindows([fps, fps])).toBe("low");
  });
});
