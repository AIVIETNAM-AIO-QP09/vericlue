# Bàn giao · APP-01 · Ngọc Quang+Claude · 2026-10-23 20:27

**Nhánh:** `feat/APP-01-android-ui`
**Trạng thái task sau phiên này:** doing (xong phần giao diện; còn API, HTTPS, chạy trên điện thoại thật)

## Đã xong
- Dựng `apps/android/`: Kotlin 2.0, Jetpack Compose (BOM 2024.12), Navigation Compose, minSdk 29, compileSdk 35, AGP 8.7.3, Gradle wrapper 8.11.1.
- Làm đủ các màn theo Figma "VeriClue eKYC App" (bản chốt 23/10), dùng dữ liệu giả:
  - Bắt đầu: màn chào, đăng nhập/đăng ký, điều khoản phải kéo đọc hết mới tích được, đồng ý từng mục.
  - Danh tính: giới thiệu, quyền camera/micro, số điện thoại và OTP có bàn phím số, chụp CCCD (thường, lóa, mặt sau), kiểm tra và sửa thông tin.
  - Khuôn mặt (ADR-0016, gọn 2 việc): chuẩn bị; căn mặt (thiếu sáng → xa → đạt); giữ yên (nền xám → nháy 4 màu → chấm sáng); quay đầu theo thứ tự ngẫu nhiên.
  - Giọng nói: đọc câu, đang nghe, đọc lại câu mới.
  - Kết quả: đang gửi, đang kiểm tra (danh sách 3 bước), thành công (3 biến thể theo luồng), chờ duyệt, chụp lại, làm lại thử thách.
  - Lỗi và gián đoạn (ADR-0017): camera, micro, mạng, hết phiên, dịch vụ, thiết bị, gián đoạn, không thu được giọng, gửi thất bại, kiểm tra lâu, xác nhận dừng, đã dừng.
- Điều hướng 3 luồng: đăng nhập lại bỏ CCCD và giọng nói; khôi phục đi như đăng ký. Màn ngân hàng mẫu mở app và nhận kết quả.
- Theme sáng/tối theo hệ thống. Màu khớp 22 biến Figma, cỡ chữ khớp 14 kiểu chữ Figma. Phông Be Vietnam Pro đóng gói (OFL).
- Bản debug có màn "Xem tất cả màn" để mở thẳng từng màn và chọn kết quả mô phỏng.
- Test JVM: luật luồng, OTP, số điện thoại, cổng điều khoản; `CitizenCopyTest` chặn chữ cấm trong mọi chuỗi (`giả mạo`, `deepfake`, `%`, `điểm số`…).
- Paparazzi chụp 48 ảnh màn trên máy tính, không cần giả lập (ảnh không commit).

## Đang dở
- Chưa gọi API, chưa có HTTPS (phần còn lại của APP-01).
- Chưa chạy trên điện thoại thật; mới xem qua ảnh Paparazzi.

## Bước tiếp theo
1. Cài APK lên điện thoại Android 10+ (`adb install -r apps/android/app/build/outputs/apk/debug/app-debug.apk`) và bấm thử hết luồng.
2. APP-01 phần còn lại: sinh API client từ `packages/contracts/openapi.json`; thay `DemoOutcome` bằng `status` thật; đường hầm `cloudflared` theo ADR-0014 (cập nhật 21/10).
3. APP-02: thay `FakeCameraFeed` bằng CameraX. Thay các hẹn giờ trong `FramingScreen`, `HoldStillScreen`, `TurnHeadScreen` bằng tín hiệu dò mặt. Lấy màu nháy, đường chấm sáng và thứ tự quay từ gói thử thách (LIVE-01).
4. APP-03: nút micro ở `VoiceScreen` gọi AudioRecord (WAV 16 kHz). APP-04: OTP và CCCD gọi API.

## Quyết định, lưu ý, bẫy
- Chia việc với Lý Anh Quân: nhánh này chỉ làm giao diện; camera, ghi âm, API làm tiếp trên cùng khung. Các chỗ cần thay đã ghi trong bảng ở `apps/android/README.md`.
- Không dùng ảnh khuôn mặt thật trong app. Preview camera là hình bóng người vẽ bằng Canvas.
- Họ tên, số CCCD, số tài khoản, "Ngân hàng Mẫu" là dữ liệu mẫu và có nhãn "Dữ liệu mẫu" trên màn.
- Màn camera và màn nháy màu không có hiệu ứng trang trí; chỉ chấm sáng, mũi tên quay đầu và thanh tiến độ chuyển động.
- Chưa chép code từ `eKYC-system`. Khi chép (APP-02, SEC-02) phải ghi `third_party/README.md`.
- APK debug khoảng 58 MB vì `material-icons-extended`. Khi bật R8 ở bản release, các icon không dùng sẽ bị loại.
- CI chưa build Android (đúng tiêu chí APP-01).

## Câu hỏi cho nhóm
- Nội dung điều khoản và các mục đồng ý vẫn là chữ mẫu (Q9).
- Đăng nhập lại và khôi phục: đang chỉ khác màn kết quả. Cần chốt các bước riêng (ví dụ khôi phục có cần chụp lại CCCD không).
- Có ẩn hình khuôn mặt trong lúc nháy màu không? Hiện vẫn hiện hình nhỏ trong khung oval.

## Test đã chạy
```
cd apps/android
./gradlew testDebugUnitTest assembleDebug   → BUILD SUCCESSFUL, 7/7 test qua (FlowRulesTest 6, CitizenCopyTest 1)
./gradlew recordPaparazziDebug              → BUILD SUCCESSFUL, 48 ảnh màn
uv run python scripts/plan_check.py          → 0 lỗi, 9 cảnh báo (có sẵn, không do thay đổi này)
```
