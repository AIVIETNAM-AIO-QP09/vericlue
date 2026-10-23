# Bàn giao · APP-02 (+ APP-01 API, APP-03, APP-04) · Ngọc Quang+Claude · 2026-10-24 00:10

**Nhánh:** `feat/APP-02-camera-mic-scaffold` (tách từ `feat/APP-01-android-ui`)
**Trạng thái task sau phiên này:** doing. Bản dựng khung đã chạy trên máy ảo; chờ anh Lý thử trên điện thoại thật và làm tiếp.

## Đã xong
- **Gọi API phiên** (`data/api/Api.kt`, OkHttp + kotlinx.serialization): tạo phiên (có `X-Mock-Scenario`), `media` (JPEG + MP4), `signals`, `finalize`, `voice`.
  - Lỗi mạng, HTTP lỗi, JSON hỏng đều thành `ApiError`, ra màn lỗi.
  - Status lạ không bao giờ thành đạt.
- **`flow/LiveFlow.kt`:** chuỗi phiên → media → signals → finalize → voice.
  - `retry` nhận thử thách mới; `voice_challenge` nhận câu đọc.
  - Câu nhắc chụp lại và số lần còn lại lấy từ server.
- **`capture/CameraSession.kt`:**
  - CameraX trước/sau, dùng chung một `PreviewView` cho mọi màn.
  - ML Kit: dò mặt, góc quay đầu; đọc QR CCCD.
  - Chụp JPEG chính diện; quay MP4 suốt chuỗi màu.
  - Ghi `frame_times` theo đồng hồ elapsedRealtime; khóa AE/AWB sau nền xám; `client_quality` ghi fps, nguồn timestamp, có video không.
- **`capture/Signals.kt`:**
  - `QualityGate` (thiếu sáng, xa, lệch, đạt → tự chụp sau 1 giây).
  - `TurnTracker`.
  - `ColorSchedule` lấy màu từ `challenge`, kèm kiểm giới hạn nháy.
- **`capture/WavRecorder.kt`:** AudioRecord 16 kHz mono → WAV, có mức âm cho sóng âm.
- **`capture/IdCard.kt`:** đo nét (phương sai Laplacian), đo lóa, đọc QR CCCD. Màn xem lại hiện ảnh thật và câu nhắc đúng lỗi. Màn xác nhận điền thông tin từ QR.
- **Gián đoạn (ADR-0017 §2):** đưa app xuống nền giữa lúc quay/ghi âm thì bỏ lượt và hiện màn "Xác minh bị gián đoạn".
- **Bản debug:**
  - Công tắc "API thật" kèm chọn kịch bản mock.
  - Nút "Chụp ngay (debug)" và "Bỏ qua (debug)" để thử trên máy ảo không có mặt người. Bản release không có.
- **30 test JVM**, gồm `LiveFlowTest` chạy với MockWebServer.
- **Tài liệu:** `apps/android/README.md` (bảng đã thật / còn giả, cách chạy API mock bằng SQLite), mục 11 trong `docs/plan-camera-mic.md`, `third_party/README.md`.

## Đang dở
- Chưa thử trên điện thoại thật: ngưỡng `QualityGate`, chiều dấu góc quay đầu, khóa AE/AWB có ăn không, fps.
- Chấm sáng chưa ghi đường đi; thứ tự quay đầu vẫn chọn trên máy. Cả hai chờ hợp đồng LIVE-01.
- CCCD và OTP chưa gửi server, vì chưa có endpoint (FLOW-02, FLOW-03).
- Chưa có `region_means`, `camprobe`, ký media (LIVE-03, SEC-02), HTTPS qua cloudflared.

## Bước tiếp theo
1. **Anh Lý:** lấy nhánh, mở bằng Android Studio, chạy API mock theo `apps/android/README.md` rồi cài lên điện thoại thật. Kiểm theo giai đoạn 9 của kế hoạch và ghi số đo thật.
2. Chỉnh hằng số trong `QualityGate`, `TurnTracker`, `IdQuality` theo số đo thật.
3. Khi có hợp đồng LIVE-01: nối đường chấm sáng và thứ tự quay đầu (`HoldStillScreen` / `FollowDot`, `TurnHeadScreen`).
4. Cloudflared: build với `-Pvericlue.apiBaseUrl=https://...`.

## Quyết định, lưu ý, bẫy
- **Mỗi màn tạo `PreviewView` mới sẽ làm camera cấu hình lại và hủy đoạn quay đang chạy** (`ERROR_SOURCE_INACTIVE`). Vì vậy dùng một `PreviewView` chung (`CameraSession.previewView`), và đợi 600 ms sau khi chuyển màn rồi mới quay.
- **Gián đoạn xử lý ở `ON_STOP`, không ở `ON_START`,** vì activity có thể bị tạo lại trước khi app quay lại.
- **Làm lại phần khuôn mặt sau gián đoạn sẽ tạo phiên mới,** vì API chưa cấp thử thách mới riêng (LIVE-06).
- **Giọng nói chỉ gửi khi `finalize` trả `voice_challenge`,** đúng API hiện tại. ADR-0016 muốn luôn đọc câu (câu hỏi Q5 trong kế hoạch).
- **Video là MP4.** Server đã nhận `.mp4` (Q1).
- **API chạy được không cần Postgres:** đặt `DATABASE_URL=sqlite:///...` rồi chạy `alembic upgrade head`.
- **QR CCCD:** test chỉ dùng dữ liệu bịa; thứ tự trường phải kiểm với thẻ thật.

## Câu hỏi cho nhóm
- Q1–Q6 trong `apps/android/docs/plan-camera-mic.md` mục 9: MP4/WebM, ML Kit/MediaPipe, hợp đồng LIVE-01, endpoint OTP/CCCD, thứ tự đọc câu, `frame_times`/`camprobe` cho app native.

## Test đã chạy
```
cd apps/android
./gradlew testDebugUnitTest assembleDebug   → BUILD SUCCESSFUL, 30/30 test qua
                                              (CaptureTest 7, CitizenCopyTest 1, FlowRulesTest 6, IdCardTest 5, LiveFlowTest 6, ScreensSnapshotTest 5)
Máy ảo Pixel 6 (Android 14) + API mock (SQLite):
  genuine → thành công · voice_clone → đọc câu → chờ duyệt · low_quality → chụp lại (gợi ý + số lần từ server)
  error → chờ duyệt · print → chờ duyệt · server nhận face_image.jpg + face_video.mp4 (243 KB) + signals
  Xuống nền giữa lúc căn mặt → màn "Xác minh bị gián đoạn"
  Camera sau: chụp, đo nét/lóa, mặt sau không có QR → "Chưa ổn" + câu nhắc
uv run python scripts/plan_check.py → 0 lỗi, 9 cảnh báo (có sẵn)
```
