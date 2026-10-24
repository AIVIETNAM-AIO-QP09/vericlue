# Việc cần trưởng nhóm duyệt và chốt (app Android)

- **Ngày:** 24/10/2026. **Người hỏi:** Ngọc Quang (+ Claude).
- **Cách trả lời:** điền vào cột **Trả lời** (ok / sửa / không), sửa thẳng file này trên GitHub hoặc nhắn lại.
- **Sau khi có trả lời:** app làm tiếp theo câu trả lời, và mỗi câu đã chốt sẽ được ghi lại trong file bàn giao.

## A. Duyệt code

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 1 | Duyệt và merge PR giao diện (nhánh `feat/APP-01-android-ui`) | Code chưa vào `main` thì cả nhóm chưa dùng được | Merge trước PR 2 | |
| 2 | Duyệt và merge PR camera/mic/API (nhánh `feat/APP-02-camera-mic-scaffold`) | Đã chạy hết luồng với API mock, 40 test qua, có CI Android | Merge sau PR 1 | |

## B. Đang chặn app

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 3 | **Q3 · Hợp đồng LIVE-01**: đường chấm sáng, thứ tự quay đầu | Chưa có trong `session.schema.json`; app đang tự random trên máy | `Challenge` thêm `turn_order` (ví dụ `["left","right"]`) và `dot_path: [{t_ms, x, y}]` (x, y trong 0–1 theo màn hình). `Signals` thêm `dot_events: [{index, x, y, painted_at}]`, cùng đồng hồ với `color_events`. M5 làm PR `[contract]` | |
| 4 | **Q4 · Endpoint OTP và CCCD** (FLOW-02, FLOW-03) | Chưa có trong `openapi.json`; app chỉ lưu dữ liệu trên máy | OTP: `POST /v1/sessions/{id}/otp` gửi `{phone}`, rồi `POST .../otp/verify` gửi `{code}`; trả `pass`/`retry` + `attempts_left`. CCCD: `POST .../id-card`, multipart `front`, `back`, `qr`; trả các trường đã đọc (họ tên, số CCCD, ngày sinh, giới tính, địa chỉ) | |
| 5 | **Q5 · Đọc câu luôn hay chỉ khi server yêu cầu** | ADR-0016 (22/10) ghi luôn đọc; API hiện chỉ cho đọc khi `finalize` trả `voice_challenge` | Chốt một cách. App đang theo API; đổi thì app sửa 1 dòng, server phải đổi luồng | |

## C. Tài liệu (luật 7: chỉ trưởng nhóm sửa ADR và hợp đồng)

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 6 | **Q1 · Video MP4 hay WebM** | ADR-0017 §3 ghi WebM; app Android quay ra MP4; server đã nhận `.mp4` (`services/api/.../storage.py`) | Sửa ADR-0017: "WebM trên web, MP4 trên app" | |
| 7 | **Q2 · ML Kit hay MediaPipe trên app** | ADR-0014 để ngỏ | ML Kit để căn mặt, đo góc quay đầu, đọc QR (mống mắt do server dò, LIVE-02). Ghi vào ADR-0014 | |
| 8 | **Q6 · Mô tả `frame_times`/`painted_at` cho app** | Schema đang mô tả theo web (`performance.now()`, `requestVideoFrameCallback`) | Giữ tên trường; app dùng đồng hồ `elapsedRealtime` (ms), ghi rõ ở `client_quality.clock`. Sửa phần mô tả schema bằng một PR `[contract]` nhỏ | |

## D. Cần nhóm thống nhất

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 9 | **CamProbe trên máy ảo** | Server coi mọi cờ trong `api_tamper_flags` là không đạt; app gắn `android:emulator` khi chạy trên máy ảo | Chấp nhận: demo với mô hình thật chạy trên điện thoại thật; máy ảo chỉ dùng với API mock | |
| 10 | **Định nghĩa `region_means`** | App đo vùng da theo tỉ lệ hộp mặt ML Kit; web đo theo điểm mốc MediaPipe | PRES-02 chốt một định nghĩa. Nếu theo web, app chuyển phần đo vùng sang MediaPipe | |

## E. Người và máy

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 11 | **Giao APP-02/03/04 cho anh Lý** | Backlog đang ghi "Ngọc Quang+Claude (khung), Lý Anh Quân" | Anh Lý làm tiếp trên khung có sẵn | |
| 12 | **Điện thoại thật + cloudflared** | Chưa thử trên máy thật; bản release chỉ gọi HTTPS | Chọn người có máy Android 10+, cài `app-arm64-v8a-release.apk` (22 MB). Cần địa chỉ cloudflared tới máy demo để build | |
| 13 | **Khóa ký app** | Bản release đang ký tạm bằng khóa debug | Nộp bài dùng khóa debug là đủ, hay cần tạo khóa riêng? | |

## F. Sau lần duyệt 24/10

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 14 | **Người không xem được màn nháy màu** (nút "Bỏ qua nháy màu") | Trước đây nút này bỏ luôn phần khuôn mặt. Giờ app dừng và hiện màn "Cần xác minh theo cách khác" (mời liên hệ ngân hàng). **Chưa gửi gì lên server**, nên không có hồ sơ nào trong bàn duyệt | Cần endpoint hoặc trạng thái để server mở ca duyệt thủ công (ví dụ `POST .../finalize` kèm `skip_flash: true` → `review`). Tạm thời giữ cách hiện tại | |
| 15 | **Tiêu chí "Build được APK trên máy Windows"** (E9, APP-01) | Duyệt yêu cầu bỏ tích nếu chưa build thật | Giữ tích: đã build `testDebugUnitTest assembleDebug assembleRelease` trên Windows 11 (JDK 17, Android SDK 35), README có bước cài Android Studio/SDK. Chi tiết trong bàn giao | |

Chi tiết kỹ thuật: [`plan-camera-mic.md`](plan-camera-mic.md) (mục 9 và 11), [`../README.md`](../README.md).
