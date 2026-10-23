# apps/android — App Android cho người dân (Kotlin, Jetpack Compose)

**Phụ trách:** M1 (APP-01…04). **Quyết định:** ADR-0014 (app Kotlin native), ADR-0016 (giai đoạn B gọn còn 2 việc), ADR-0017 (thông báo làm lại, gián đoạn).

## Trạng thái

Bản hiện tại là **phần giao diện** của APP-01: đủ các màn theo Figma "VeriClue eKYC App", điều hướng 3 luồng (đăng ký, đăng nhập lại, khôi phục), dữ liệu giả.

**Chưa có:** camera thật (CameraX), ghi âm, gọi API, HTTPS, Keystore. Các phần này làm ở APP-01 (API), APP-02 (camera), APP-03 (ghi âm), APP-04 (OTP, CCCD), SEC-02 (Keystore).

| Chỗ giả | Thay bằng |
|---|---|
| `FakeCameraFeed` (hình bóng người vẽ bằng Canvas) | Preview CameraX (APP-02) |
| Hẹn giờ tự chuyển màn ở căn mặt, giữ yên, quay đầu, kiểm tra | Tín hiệu từ ML Kit/MediaPipe và kết quả API |
| `DemoOutcome` trong `flow/Flow.kt` | `status` từ API (`pass`, `retry`, `review`, `voice_challenge`) |
| Thứ tự quay đầu ngẫu nhiên trên máy | Gói thử thách của server (LIVE-01) |
| Câu đọc, họ tên, số CCCD, số tài khoản | Dữ liệu thật từ API và mã QR (đang hiện nhãn "Dữ liệu mẫu") |

## Cài đặt lần đầu (Windows)

Cần JDK 17 và Android SDK (API 35). Cách nhanh nhất là cài **Android Studio** rồi mở thư mục `apps/android`.

Nếu không muốn cài Android Studio:
1. Tải JDK 17 bản zip (ví dụ Microsoft Build of OpenJDK 17), giải nén, đặt `JAVA_HOME`.
2. Tải *Command line tools only* của Android, giải nén vào `<sdk>/cmdline-tools/latest`, rồi chạy:
   ```bash
   sdkmanager --sdk_root=<sdk> "platform-tools" "platforms;android-35" "build-tools;35.0.0"
   ```
3. Tạo `apps/android/local.properties` (không commit) với dòng `sdk.dir=D\:/tools/android-sdk` (đổi theo đường dẫn của bạn).

## Lệnh

```bash
cd apps/android
./gradlew assembleDebug          # APK: app/build/outputs/apk/debug/app-debug.apk
./gradlew testDebugUnitTest      # test logic luồng + kiểm chữ cấm hiển thị cho người dân
./gradlew recordPaparazziDebug   # chụp ảnh mọi màn trên máy tính (không cần giả lập), ra app/src/test/snapshots/images
```

Cài lên điện thoại Android 10+: bật *Gỡ lỗi USB*, rồi `adb install -r app/build/outputs/apk/debug/app-debug.apk`. Hoặc chép file APK sang máy và mở.

Bản debug có nút **"Xem tất cả màn (bản demo giao diện)"** ở màn ngân hàng mẫu: mở thẳng từng màn, chọn luồng và kết quả mô phỏng (đạt, chờ duyệt, chụp lại, làm lại thử thách, đọc lại câu).

## Cấu trúc

```
app/src/main/java/vn/vericlue/app/
  MainActivity.kt
  flow/Flow.kt              luật điều hướng, OTP, số điện thoại, cổng điều khoản (Kotlin thuần, có test)
  ui/App.kt                 NavHost, FlowState, màn "tất cả màn"
  ui/theme/Theme.kt         màu (khớp biến Figma "VeriClue / Màu"), kiểu chữ, theme sáng/tối
  ui/components/            thanh trên, thanh tiến độ 3 bước, nút, bàn phím số, khung camera, thẻ danh sách
  ui/screens/               Bắt đầu, Danh tính, Khuôn mặt, Giọng nói + Kết quả
```

## Quy ước

- Người dân **không bao giờ** thấy điểm số, %, màu đỏ hay chữ "giả mạo". `CitizenCopyTest` quét mọi chuỗi trong `src/main` để chặn.
- Chỉ dẫn trên camera là **một câu về chất lượng** (ánh sáng, khoảng cách). Thông báo làm lại chia hai loại theo ADR-0017.
- Màn camera và màn nháy màu **không có hiệu ứng trang trí**; chỉ chấm sáng, mũi tên quay đầu và thanh tiến độ được chuyển động.
- Màu và cỡ chữ lấy từ `ui/theme`, không viết mã màu trong màn.
- Phông Be Vietnam Pro (SIL OFL 1.1) đóng gói trong `res/font`, chạy offline. Giấy phép: `third_party/licenses/BeVietnamPro-OFL.txt`.
- Chưa dùng lại code từ `AIVIETNAM-AIO-QP09/eKYC-system`; khi chép CameraX hay Keystore từ đó (APP-02, SEC-02) phải giữ dòng giấy phép MIT và ghi vào `third_party/README.md`.
