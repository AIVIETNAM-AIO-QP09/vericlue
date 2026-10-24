# apps/android — App Android cho người dân (Kotlin, Jetpack Compose)

**Phụ trách:** M1 (APP-01…04). **Quyết định:** ADR-0014 (app Kotlin native), ADR-0016 (giai đoạn B gọn còn 2 việc), ADR-0017 (thông báo làm lại, gián đoạn).

## Trạng thái

- **Giao diện (APP-01):** đủ các màn theo Figma "VeriClue eKYC App"; điều hướng 3 luồng (đăng ký, đăng nhập lại, khôi phục).
- **Bản dựng khung camera, micro, API** (nhánh `feat/APP-02-camera-mic-scaffold`): đã chạy hết luồng trên máy ảo với API mock. **Chưa thử trên điện thoại thật.**
- **Việc cần trưởng nhóm duyệt/chốt:** [`docs/can-chot.md`](docs/can-chot.md) (13 mục, có cột trả lời).
- **Kế hoạch đầy đủ:** [`docs/plan-camera-mic.md`](docs/plan-camera-mic.md) (giai đoạn, thư viện, đồng hồ thời gian, câu hỏi cần chốt). Mục 11 của file đó ghi đã làm tới đâu.

| Phần | Đã thật | Còn giả hoặc chưa làm |
|---|---|---|
| Gọi API | Tạo phiên, `media` (ảnh + MP4), `signals`, `finalize`, `voice`; header `X-Mock-Scenario` | Client viết tay (APP-01 muốn sinh từ `openapi.json`); HTTPS qua cloudflared |
| Camera trước | CameraX, ML Kit dò mặt, cổng chất lượng tự chụp, quay MP4 lúc nháy màu, khóa AE/AWB | Ngưỡng cần chỉnh trên máy thật. Đã gửi `region_means` (vùng theo hộp mặt ML Kit, chờ PRES-02 chốt định nghĩa) và `camprobe` (cờ `android:*`) |
| Nháy màu | Màu, nhịp từ `challenge` của server; ghi `color_events`, `frame_times` cùng một đồng hồ | Đo phản chiếu trên máy thật |
| Quay đầu | Góc quay từ ML Kit (`headEulerAngleY`) | Thứ tự trái/phải vẫn chọn trên máy (chờ LIVE-01); chiều dấu của góc phải kiểm trên máy thật |
| Chấm sáng | Giao diện | Đường đi và việc ghi `(t, x, y)` chờ hợp đồng LIVE-01 |
| Ghi âm | `AudioRecord` 16 kHz mono → WAV, câu đọc từ `voice_prompt`; quay MP4 cùng lúc (API thật) và gửi kèm ở `/voice` cho khớp môi (VOICE-05) | Video bắt đầu trước WAV khoảng 0,6 s; chưa gửi độ lệch (câu 16 trong `docs/can-chot.md`) |
| CCCD | Camera sau, đọc QR (ML Kit), đo nét/lóa, điền thông tin từ QR | Chưa có endpoint gửi CCCD (FLOW-03); thứ tự trường QR cần kiểm với thẻ thật |
| OTP | Giao diện, bàn phím | Chưa có endpoint (FLOW-02) |
| Gián đoạn | Xuống nền giữa lúc quay → bỏ lượt, màn "Xác minh bị gián đoạn" | Gia hạn phiên (LIVE-06) |
| Keystore, ký media | | SEC-02, LIVE-03 |

## Cài đặt lần đầu (Windows)

Cần JDK 17 và Android SDK (API 35). Cách nhanh nhất là cài **Android Studio** rồi mở thư mục `apps/android`.

Nếu không muốn cài Android Studio:
1. Tải JDK 17 bản zip (ví dụ Microsoft Build of OpenJDK 17), giải nén, đặt `JAVA_HOME`.
2. Tải *Command line tools only* của Android, giải nén vào `<sdk>/cmdline-tools/latest`, rồi chạy:
   ```bash
   sdkmanager --sdk_root=<sdk> "platform-tools" "platforms;android-35" "build-tools;35.0.0"
   ```
3. Tạo `apps/android/local.properties` (không commit) với dòng `sdk.dir=D\:/tools/android-sdk` (đổi theo đường dẫn của bạn).

Trên **macOS** (Apple Silicon): cài Android Studio, mở `apps/android`, tạo máy ảo Pixel ảnh `arm64-v8a`; trong Advanced Settings đặt Camera Front = Webcam0 để dùng webcam của Mac.

## Lệnh

```bash
cd apps/android
./gradlew assembleDebug          # APK theo loại chip: app/build/outputs/apk/debug/app-<abi>-debug.apk
./gradlew assembleRelease -Pvericlue.apiBaseUrl=https://<địa-chỉ>/   # bản rút gọn (R8), ~22 MB; thiếu https:// thì build dừng
./gradlew testDebugUnitTest      # test logic: luồng, API (MockWebServer), camera, WAV, CCCD, chữ cấm
./gradlew recordPaparazziDebug   # chụp ảnh mọi màn trên máy tính (không cần giả lập), ra app/src/test/snapshots/images
```

Địa chỉ API mặc định là `http://10.0.2.2:8000/` (máy ảo gọi về máy tính). Đổi khi build, không ghi cứng địa chỉ đường hầm vào code:

```bash
./gradlew assembleDebug -Pvericlue.apiBaseUrl=https://<địa-chỉ-cloudflared>/
```

Bản debug cho phép HTTP thường **chỉ** tới `10.0.2.2` và `localhost` (`src/debug/res/xml/network_security_config.xml`); bản release chỉ dùng HTTPS.

### Chọn file APK

| File | Dùng cho |
|---|---|
| `app-arm64-v8a-*.apk` | Hầu hết điện thoại Android hiện nay |
| `app-armeabi-v7a-*.apk` | Điện thoại cũ 32-bit |
| `app-x86_64-*.apk` | Máy ảo trên máy tính Windows/Intel |
| `app-universal-*.apk` | Mọi máy (nặng nhất) |

Bản **release** dùng API thật ngay (không có chế độ giả lập, không có màn "Xem tất cả màn"), chỉ gọi HTTPS. Build release phải truyền `-Pvericlue.apiBaseUrl=https://...`; thiếu hoặc không phải `https://` thì task `checkReleaseApiUrl` dừng build. Bản release hiện ký bằng khóa debug để cài thử; phải đổi sang khóa thật trước khi phát hành.

## Chạy thử với API mock (không cần Postgres, không cần điện thoại)

```bash
# ở thư mục gốc repo
uv sync --frozen --all-packages
export DATABASE_URL="sqlite:///$PWD/tmp/dev.db" MEDIA_DIR="$PWD/tmp/media" USE_MOCK_MODELS=true
uv run --frozen alembic -c services/api/alembic.ini upgrade head
uv run --frozen uvicorn vericlue_api.main:app --app-dir services/api/src --host 0.0.0.0 --port 8000
```

Trong app (bản debug): màn ngân hàng mẫu → **"Xem tất cả màn (bản demo giao diện)"** → chọn **"API thật"** và một kịch bản mock (`genuine`, `low_quality`, `voice_clone`, `error`…) → mở **"Chuẩn bị"** → "Tôi đã sẵn sàng".

Máy ảo không có mặt người trước camera nên bản debug có nút **"Chụp ngay (debug)"** ở màn căn mặt và **"Bỏ qua (debug)"** ở màn quay đầu. Hai nút này không có trong bản release.

Kết quả đã thử trên máy ảo (23–24/10): `genuine` → thành công; `voice_clone` → đọc câu → chờ duyệt; `low_quality` → chụp lại (câu nhắc và số lần còn lại lấy từ server); `error`, `print` → chờ duyệt. Server nhận được ảnh JPEG, video MP4 và tín hiệu.

## Cấu trúc

```
app/src/main/java/vn/vericlue/app/
  MainActivity.kt
  data/api/Api.kt           client API phiên (OkHttp + kotlinx.serialization); lỗi nào cũng thành ApiError, không ném ra UI
  flow/Flow.kt              luật điều hướng, status → màn, OTP, số điện thoại, cổng điều khoản (Kotlin thuần, có test)
  flow/LiveFlow.kt          một lượt xác minh thật: phiên → media → signals → finalize → voice
  capture/CameraSession.kt  CameraX (trước/sau), ML Kit (mặt, QR), ảnh JPEG, quay MP4, frame_times, khóa AE/AWB
  capture/Signals.kt        đồng hồ chung, cổng chất lượng, theo dõi quay đầu, lịch nháy màu
  capture/WavRecorder.kt    ghi âm WAV 16 kHz
  capture/IdCard.kt         đo nét/lóa, đọc QR CCCD
  ui/App.kt                 NavHost, quyền, nối camera/API vào màn, màn "tất cả màn"
  ui/theme/Theme.kt         màu (khớp biến Figma "VeriClue / Màu"), kiểu chữ, theme sáng/tối
  ui/components/            thanh trên, thanh tiến độ, nút, bàn phím số, khung camera, thẻ danh sách
  ui/screens/               Bắt đầu, Danh tính, Khuôn mặt, Giọng nói + Kết quả
```

## Quy ước

- Người dân **không bao giờ** thấy điểm số, %, màu đỏ hay chữ "giả mạo". `CitizenCopyTest` quét mọi chuỗi trong `src/main` để chặn.
- **Chỉ `pass` mới là đạt.** Lỗi mạng, phản hồi sai dạng, status lạ (`error`, `degraded`…) đều ra màn lỗi (`FlowRules.routeForStatus`, `errorRoute`).
- Chỉ dẫn trên camera là **một câu về chất lượng** (ánh sáng, khoảng cách). Thông báo làm lại chia hai loại theo ADR-0017.
- Mọi mốc thời gian gửi server dùng `CaptureClock` (elapsedRealtime, ms). Xem mục 4 của kế hoạch.
- Màn camera và màn nháy màu **không có hiệu ứng trang trí**; chỉ chấm sáng, mũi tên quay đầu và thanh tiến độ được chuyển động.
- Màu và cỡ chữ lấy từ `ui/theme`, không viết mã màu trong màn.
- Ảnh CCCD và dữ liệu QR hiện chỉ nằm trên máy, không gửi đi (chưa có endpoint).
- Phông Be Vietnam Pro (SIL OFL 1.1) đóng gói trong `res/font`, chạy offline. Giấy phép: `third_party/licenses/BeVietnamPro-OFL.txt`.
- Chưa dùng lại code từ `AIVIETNAM-AIO-QP09/eKYC-system`; khi chép Keystore từ đó (SEC-02) phải giữ dòng giấy phép MIT và ghi vào `third_party/README.md`.
