import { type Page, expect, test } from "@playwright/test";

import { vi } from "../src/i18n/vi";

const t = vi.verify;

// MediaPipe (wasm) ghi cả dòng log thông tin bằng console.error, ví dụ
// "INFO: Created TensorFlow Lite XNNPACK delegate for CPU." hay "W1015 ... face_landmarker_graph.cc".
// Đó không phải lỗi của ứng dụng.
const MEDIAPIPE_LOG = /^(INFO:|[WIE]\d{4} \d{2}:\d{2}:\d{2})/;

// Lỗi thật trong trang: ngoại lệ chưa bắt và console.error không phải log của MediaPipe.
function collectPageErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error" && !MEDIAPIPE_LOG.test(message.text())) {
      errors.push(`console.error: ${message.text()}`);
    }
  });
  return errors;
}

async function acceptConsent(page: Page) {
  await expect(page.getByRole("heading", { name: t.consent.title })).toBeVisible();
  const checkbox = page.getByRole("checkbox");
  await expect(checkbox).not.toBeChecked(); // KHÔNG tích sẵn
  const next = page.getByRole("button", { name: t.consent.continue });
  await expect(next).toBeDisabled();
  await checkbox.check();
  await expect(next).toBeEnabled();
  await next.click();
}

const framingHeading = (page: Page) => page.getByRole("heading", { name: t.framing.title });

test.describe("luồng /verify trên Chromium thật với camera giả", () => {
  test("đồng ý → camera được cấp → hiện chỉ dẫn; không kẹt ở bước xin camera", async ({ page }) => {
    const errors = collectPageErrors(page);
    await page.goto("/verify");
    await acceptConsent(page);

    // Lỗi trước đây: kẹt mãi ở "Đang mở camera..." vì camera bị tắt và CAMERA_GRANTED không bao giờ được gửi.
    await expect(framingHeading(page)).toBeVisible();
    await expect(page.getByText(t.camera.asking)).toHaveCount(0);

    // Luồng camera thật sự đang chạy và gắn vào video.
    await expect
      .poll(() =>
        page.evaluate(() => {
          const video = document.querySelector("video");
          const stream = video?.srcObject as MediaStream | null | undefined;
          return stream?.getVideoTracks().some((track) => track.readyState === "live") ?? false;
        }),
      )
      .toBe(true);

    // Camera giả không có khuôn mặt: sau khi tải MediaPipe offline và đo FPS, cổng báo chưa thấy mặt.
    await expect(page.getByText(t.quality.NO_FACE)).toBeVisible();

    // Không sang màn lỗi hay màn "thiết bị chưa đáp ứng", và cũng không đi tiếp (cổng không cho qua).
    await expect(page.getByText(t.errors.title)).toHaveCount(0);
    await expect(page.getByText(t.deviceUnsupported.title)).toHaveCount(0);
    await expect(page.getByRole("heading", { name: t.flash.title })).toHaveCount(0);
    expect(errors).toEqual([]);
  });

  test("xin camera đúng MỘT lần cho mỗi lần xin, kể cả khi React StrictMode (dev) chạy effect hai lần", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      const w = window as unknown as { __gumCalls: number };
      w.__gumCalls = 0;
      const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
      navigator.mediaDevices.getUserMedia = (constraints) => {
        w.__gumCalls += 1;
        return original(constraints);
      };
    });
    await page.goto("/verify");
    await acceptConsent(page);
    await expect(framingHeading(page)).toBeVisible();
    await expect(page.getByText(t.quality.NO_FACE)).toBeVisible();

    const calls = await page.evaluate(
      () => (window as unknown as { __gumCalls: number }).__gumCalls,
    );
    expect(calls).toBe(1);
  });

  test("bị từ chối camera → báo rõ; bấm Thử lại sau khi cho phép thì vào đặt mặt (lần xin mới)", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      const w = window as unknown as { __allowCamera: boolean };
      w.__allowCamera = false;
      const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
      navigator.mediaDevices.getUserMedia = (constraints) =>
        w.__allowCamera
          ? original(constraints)
          : Promise.reject(new DOMException("Permission denied", "NotAllowedError"));
    });
    await page.goto("/verify");
    await acceptConsent(page);

    await expect(page.getByText(t.camera.denied)).toBeVisible();
    await expect(framingHeading(page)).toHaveCount(0); // chưa được cho đi tiếp

    // Vẫn từ chối lần nữa: vẫn ở bước xin quyền, vẫn báo rõ.
    await page.getByRole("button", { name: t.camera.retry }).click();
    await expect(page.getByText(t.camera.denied)).toBeVisible();

    // Cho phép rồi thử lại: vào đặt mặt.
    await page.evaluate(() => {
      (window as unknown as { __allowCamera: boolean }).__allowCamera = true;
    });
    await page.getByRole("button", { name: t.camera.retry }).click();
    await expect(framingHeading(page)).toBeVisible();
  });

  test("trình duyệt thiếu requestVideoFrameCallback → màn 'thiết bị chưa đáp ứng', không phải lỗi, không đi tiếp", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      // Giả lập trình duyệt cũ: không có API đo khung hình.
      Reflect.deleteProperty(HTMLVideoElement.prototype, "requestVideoFrameCallback");
    });
    await page.goto("/verify");
    await acceptConsent(page);

    await expect(page.getByRole("heading", { name: t.deviceUnsupported.title })).toBeVisible();
    await expect(page.getByText(t.deviceUnsupported.reasons.no_frame_callback)).toBeVisible();
    await expect(page.getByText(t.errors.title)).toHaveCount(0);
    await expect(page.getByRole("heading", { name: t.flash.title })).toHaveCount(0);
  });

  test("màn đồng ý và mọi màn của người dân không lộ điểm số hay chữ 'giả mạo'", async ({
    page,
  }) => {
    await page.goto("/verify");
    await acceptConsent(page);
    await expect(framingHeading(page)).toBeVisible();
    await expect(page.getByText(t.quality.NO_FACE)).toBeVisible();

    const body = (await page.locator("body").innerText()).toLowerCase();
    for (const forbidden of ["giả mạo", "deepfake", "score", "xác suất", "điểm số"]) {
      expect(body).not.toContain(forbidden);
    }
  });
});
