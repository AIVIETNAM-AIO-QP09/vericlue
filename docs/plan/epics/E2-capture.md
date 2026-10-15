# E2 — Web thu nhận eKYC (CAP)

> Mục tiêu epic: người dân đi hết một phiên trên điện thoại thật trong < 60 giây, kèm thu đủ tín hiệu cho ChromaPulse và CamProbe.
> Đọc chung: proposal §2.7, Phụ lục A; ADR-0003, ADR-0007; `apps/web/README.md`.

---

### CAP-01 · Luồng /verify và màn hình đồng ý

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S0–S1 | P0 | PLAT-02, PLAT-04 |

**Mục tiêu:** khung luồng xác minh chạy với API mock, có máy trạng thái rõ ràng.

**Đầu ra:**
- `src/lib/capture/flow.ts`: máy trạng thái (xstate hoặc reducer) gồm các bước `consent → camera_permission → framing → quality_check → flash_challenge → uploading → result | retry | voice_challenge`.
- Màn hình đồng ý tách riêng, **không tích sẵn**. Ghi rõ "dữ liệu sinh trắc học là dữ liệu nhạy cảm", nêu mục đích và thời hạn lưu.
- Màn hình kết quả: "Xác minh thành công" / "Vui lòng thử lại" + 1 gợi ý / "Hồ sơ đang được kiểm tra".
- Chữ tiếng Việt trong `src/i18n/vi.ts`.

**Tiêu chí hoàn thành:**
- [x] Với API mock đi được cả 4 nhánh: pass, retry, voice_challenge, review (test `runner.e2e.test.ts` với API mock thật; chọn kịch bản bằng `?scenario=`).
- [x] Không có màn hình nào hiển thị điểm số hay chữ "giả mạo" (test quét toàn bộ chuỗi `vi.verify` trong `messages.test.ts`).
- [x] Test Vitest cho máy trạng thái (`flow.test.ts`, `runner.test.ts`).

> **Chỗ giữ chỗ trong CAP-01 (mỗi chỗ có chú thích "TẠM — CAP-0x thay" trong code):** `quality_check` luôn cho qua (CAP-02); `flash_challenge` chỉ phát màu theo thử thách, chưa có bộ lấy mẫu và `frame_times` (CAP-04); `uploading` gửi ảnh giữ chỗ (CAP-06); bước đọc câu chỉ hiện câu cần đọc, có nút gửi âm thanh giả ở môi trường dev (CAP-07).

---

### CAP-02 · Camera, khung oval, cổng chất lượng phía trình duyệt

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1,5 | S1 | P0 | CAP-01 |

**Mục tiêu:** mở camera trước, dò mặt bằng MediaPipe Face Landmarker, hướng dẫn đặt mặt, chặn ảnh kém trước khi gửi.
**Đọc trước:** `docs/research/github-references.md` §8.1 (Amplify: khung oval, IoU, khoảng cách mặt; **không** chép `estimateIllumination` vì có lỗi).

**Đầu ra:** `src/lib/capture/camera.ts`, `quality.ts`, component `<CameraView>`.
- **Ràng buộc camera:** `facingMode: user`, 640×480 trở lên, ≥ 15 khung/giây.
- **Chỉ số chất lượng:**
  - 1 khuôn mặt;
  - IoU với oval ≥ 0,6;
  - góc quay đầu ≤ 20°;
  - độ nét (phương sai Laplacian);
  - tỷ lệ điểm ảnh quá tối hoặc cháy sáng;
  - mặt chiếm 35–60% chiều rộng khung.
- **Mỗi lần chỉ hiện 1 chỉ dẫn**, theo thứ tự ưu tiên.

**Tiêu chí hoàn thành:**
- [ ] Chạy ≥ 15 khung/giây trên 1 điện thoại Android tầm trung.
- [ ] Phòng tối → hiện "Ra chỗ sáng hơn"; mặt xa → "Lại gần hơn".
- [ ] Test hàm chất lượng với ảnh mẫu tổng hợp.

---

### CAP-03 · Trang thử ChromaPulse (spike, quyết định sớm)

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 (+M3) | 1 | **S0** | P0 | PLAT-02 |

**Mục tiêu:** trả lời câu hỏi "tín hiệu phản chiếu trên điện thoại thật có đủ mạnh không?" **trước 17/10**.

**Đầu ra:** trang `src/app/lab/chromapulse/page.tsx` (chỉ dùng nội bộ):
- Phát 8 màu theo bảng ở proposal Phụ lục A.
- Ghi thời điểm vẽ bằng `requestAnimationFrame` và thời điểm khung bằng `requestVideoFrameCallback` (`captureTime`, `mediaTime`, `presentedFrames`).
- Tính màu trung vị 5 vùng da + nền bằng MediaPipe.
- Xuất file JSON tải về.

> **Code xong (PR CAP-03), chờ thu dữ liệu.** Trang `/lab/chromapulse` và runbook `docs/runbooks/chromapulse-lab.md` đã có. Ba tiêu chí dưới đây cần người thu trên máy thật (14 file: mỗi máy × tình huống × 2 lần); dòng CAP-03 ở `review` cho tới khi có dữ liệu.

**Tiêu chí hoàn thành:**
- [ ] Thu được JSON trên ≥ 3 máy: Android tầm trung, iPhone, laptop. Mỗi máy 3 tình huống: người thật, video phát lại trên màn hình khác, OBS Virtual Camera (trên laptop).
- [ ] Ghi rõ trình duyệt nào có `captureTime`.
- [ ] Bàn giao JSON cho PRES-01.

---

### CAP-04 · ChromaPulse bản chính thức (chép từ AWS Amplify)

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1,5 | S1 | P0 | CAP-03, PRES-01, PLAT-04 |

**Mục tiêu:** phát chuỗi màu do server cấp, an toàn cho mắt, và gửi tín hiệu đúng schema `Signals`.
**Đọc trước:** `docs/research/github-references.md` §8.1, ADR-0007, `third_party/README.md`.

**Các bước:**
1. Chép `ColorSequenceDisplay.ts`, `fillOverlayCanvasFractional`, các hàm khung oval và IoU từ `amplify-ui/packages/react-liveness` vào `src/lib/capture/vendor/amplify/`. Giữ dòng giấy phép Apache-2.0, ghi bảng trong `third_party/README.md`.
2. Đổi sang **bảng màu và thời gian của nhóm**: 8 màu từ server, `hold_ms` 400–650, chuyển màu 150 ms, ≤ 2,5 lần đổi màu/giây.
3. Trước khi nháy: cảnh báo ánh sáng nhấp nháy, có nút "Bỏ qua" (chuyển sang đọc câu); bật `wakeLock`; nhắc tăng độ sáng; giữ yên 1 giây.
4. Ghi `color_events` và `frame_times` theo `Signals`; gửi kèm `region_means`.

**Tiêu chí hoàn thành:**
- [ ] Chạy trên Android Chrome và iPhone Safari.
- [ ] Nút "Bỏ qua" hoạt động.
- [ ] Payload `signals` hợp lệ với schema (test).
- [ ] Đã ghi `third_party/README.md`.

---

### CAP-05 · CamProbe phía trình duyệt

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S1 | P0 | CAP-02 |

**Mục tiêu:** thu tín hiệu cho thấy camera bị thay thế hoặc can thiệp.
**Đọc trước:** ADR-0007; `docs/research/github-references.md` §7.1, §8.2.

**Đầu ra:** `src/lib/capture/camprobe.ts` trả về object `camprobe` theo schema.
- **`api_tamper_flags`:** kiểm tra `getUserMedia`, `enumerateDevices`, `MediaStreamTrack.prototype.getSettings`, `getCapabilities`, `applyConstraints`:
  - `Function.prototype.toString` có còn `[native code]`;
  - có thuộc tính `prototype` lạ;
  - so với bản lấy từ một `<iframe>` sạch.

  Chép kỹ thuật từ CreepJS (MIT) vào `vendor/creepjs/`.
- **`constraint_probes`:** đổi độ phân giải hoặc tốc độ khung hình 2–3 lần, đo thời gian `applyConstraints`, **đọc lại `getSettings()`** và kích thước khung thật.
- **Phần còn lại:** `duplicate_frame_ratio` (so hash khung liên tiếp), `device_label`, `track_settings`, `track_capabilities`.

**Tiêu chí hoàn thành:**
- [ ] Trên trình duyệt thường: không có cờ can thiệp.
- [ ] Với tiện ích giả camera (máy red-team): có cờ.
- [ ] Với OBS: `constraint_probes` cho thấy phản hồi bất thường.
- [ ] Test đơn vị cho hàm phát hiện can thiệp: giả lập hàm bị gán đè.

---

### CAP-06 · Gửi media và xử lý kết quả

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S1 | P0 | CAP-04, CAP-05, PLAT-06 |

**Mục tiêu:** gửi ảnh mặt chất lượng cao (chụp tại các thời điểm trong `capture_at_ms` do server chọn) và video ngắn, rồi gọi `finalize`.

**Đầu ra:**
- **Chụp ảnh:** dùng canvas, PNG hoặc JPEG chất lượng 0,95.
- **Video:** MediaRecorder, bitrate khoảng 4–6 Mbps. Chỉ dùng để lưu video, **không** dùng để đo thời gian.
- **Gửi:** mọi request gắn token.
- **Xử lý `retry_hint`:** đổi thành 1 câu hướng dẫn.

**Tiêu chí hoàn thành:**
- [ ] Đi hết một phiên thật với API thật (mô hình mock hoặc thật).
- [ ] Mạng chậm thì có trạng thái chờ, không treo giao diện.

---

### CAP-07 · Màn hình đọc câu tiếng Việt (VoiceGate)

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S2 | P0 | CAP-06, VOICE-04 |

**Mục tiêu:** khi nhận `voice_challenge`, hiển thị câu, ghi âm và ghi hình khoảng 6 giây, rồi gửi `/voice`.

**Tiêu chí hoàn thành:**
- [ ] Câu hiển thị chữ to, rõ.
- [ ] Ghi âm 16 kHz trở lên; xin quyền micro trước.
- [ ] Đọc sai câu → được thử lại 1 lần với câu mới.

---

### CAP-08 · Hoàn thiện UX và thử trên nhiều máy

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 0,5 | S3 | P1 | CAP-07 |

**Tiêu chí hoàn thành:**
- [ ] Chạy trên ≥ 3 máy (Android rẻ, Android tầm trung, iPhone).
- [ ] Một phiên < 60 giây.
- [ ] Chữ to, rõ cho người lớn tuổi.
- [ ] Ghi kết quả thử vào `docs/status/STATUS.md`.
