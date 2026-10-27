# apps/android — App Android cho người dân (Kotlin, Jetpack Compose)

**Phụ trách:** M1 (APP-01…04). **Quyết định:** ADR-0014 (app Kotlin native), ADR-0016 (giai đoạn B gọn còn 2 việc), ADR-0017 (thông báo làm lại, gián đoạn).

## Trạng thái

- **Giao diện (APP-01):** đủ các màn theo Figma "VeriClue eKYC App"; điều hướng 3 luồng (đăng ký, đăng nhập lại, khôi phục).
- **Bản dựng khung camera, micro, API** (nhánh `feat/APP-02-camera-mic-scaffold`): đã chạy hết luồng trên máy ảo với API mock.
- **Điện thoại thật (27/10):** Galaxy S24 FE, bản debug qua `adb reverse`, API mock nhánh FLOW-01: đăng ký `genuine` → đạt không đọc câu, `low_quality` → chụp lại, `voice_clone` → đọc câu → chờ duyệt. Chưa thử qua HTTPS và bản release; chưa kiểm chiều quay đầu, rung, gián đoạn. Chi tiết: `docs/status/handoffs/2026-10-27-2000-app-01-ng-c-quang-claude.md`.
- **Việc cần trưởng nhóm duyệt/chốt:** [`docs/can-chot.md`](docs/can-chot.md) (33 mục, có cột trả lời; nhóm H là luồng gọn, nhóm I là khi chạy identity lab).
- **Luồng đăng ký gọn (24/10, Figma "Đề xuất · Luồng gọn"):** Điều khoản + đồng ý (1 màn) → Số điện thoại → OTP (tự điền, vẫn gõ tay được) → CCCD tự chụp mặt trước, dừng 1 nhịp → mặt sau → Xem lại 2 mặt → Chuẩn bị → Căn mặt → phần mặt (1 video) → **Kiểm tra thông tin** (bấm "Thông tin đúng" xong mới gửi video) → Đọc câu → Kết quả. Không còn màn Giới thiệu và Xin quyền: camera xin lúc mở camera, micro xin ở bước đọc câu. App gửi `id-card/confirm` trước media và `finalize` (server nhánh FLOW-05 không nhận xác nhận sau media).
- **Kế hoạch đầy đủ:** [`docs/plan-camera-mic.md`](docs/plan-camera-mic.md) (giai đoạn, thư viện, đồng hồ thời gian, câu hỏi cần chốt). Mục 11 của file đó ghi đã làm tới đâu.

| Phần | Đã thật | Còn giả hoặc chưa làm |
|---|---|---|
| Gọi API | Tạo phiên có `purpose` + `nonce` (FLOW-01), OTP, CCCD (`id-card`, `id-card/confirm`), `challenge` (thử thách mới trước mỗi lượt quay mặt), `media` (ảnh + MP4), `signals`, `finalize`, `voice`; header `X-Mock-Scenario` | Client viết tay (APP-01 muốn sinh từ `openapi.json`); HTTPS qua cloudflared |
| Camera trước | CameraX, ML Kit dò mặt, cổng chất lượng tự chụp, quay MP4 lúc nháy màu, khóa AE/AWB | Ngưỡng cần chỉnh trên máy thật. Đã gửi `region_means` (vùng theo hộp mặt ML Kit, chờ PRES-02 chốt định nghĩa) và `camprobe` (cờ `android:*`) |
| Nháy màu | Màu, nhịp từ `challenge` của server; cả phần mặt (nền xám → màu → chấm → quay đầu) là một video liên tục, chạy theo lịch server (`FaceTimeline`); ghi `color_events`, `frame_times` cùng một đồng hồ | Đo phản chiếu trên máy thật |
| Quay đầu | Theo `challenge.dynamic.head_turns` (trái/phải rồi nhìn thẳng, mỗi đoạn 2 giây), cùng một bản ghi với màu và chấm | Chiều dấu `yaw` phải kiểm trên máy thật |
| Chấm sáng | Theo 8 `gaze_points` của `challenge.dynamic`, chạy trên toàn màn hình, mốc `at_ms` tính từ khung đầu của video | Server đo ánh mắt trên video (LIVE-02) |
| Ghi âm | `AudioRecord` 16 kHz mono → WAV, câu đọc từ `voice_prompt`; quay MP4 cùng lúc (API thật) và gửi kèm ở `/voice` cho khớp môi (VOICE-05) | Video bắt đầu trước WAV khoảng 0,6 s; app gửi độ lệch ở `audio_offset_ms` (PR #47), server mới chuyển cho mô-đun, SyncNet chưa dùng |
| CCCD | Camera sau, tự chụp khi 2 khung liền nhau đủ nét và không lóa (`IdAutoCapture`, vẫn có nút chụp), đọc QR (ML Kit), điền thông tin từ QR | Gửi 2 ảnh + chuỗi QR lên server, thông tin xác nhận theo server; thứ tự trường QR cần kiểm với thẻ thật |
| OTP | Gửi/kiểm mã qua server; tự điền từ `simulated_sms` hoặc SMS thật (SMS User Consent, không cần quyền SMS); bàn phím vẫn gõ tay được | SMS thật chưa có (kênh mô phỏng) |
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

Máy ảo không có mặt người trước camera nên bản debug có nút **"Chụp ngay (debug)"** ở màn căn mặt và **"Bỏ qua (debug)"** ở màn quay đầu. Camera máy ảo cũng không đọc được QR, nên màn xem lại CCCD có nút **"Dùng mã QR mẫu (debug)"**: thay chuỗi QR và ảnh mặt sau bằng ảnh QR mẫu (dữ liệu giả, `src/debug/res/raw/sample_cccd_qr.jpg`), dùng được cả khi server bật identity lab. Các nút này không có trong bản release. Mở máy ảo với `-camera-back virtualscene` để camera sau có hình.

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
- Ảnh CCCD 2 mặt và chuỗi QR gửi ở `id-card` (QR mặt sau, không có thì QR mặt trước).
- Phông Be Vietnam Pro (SIL OFL 1.1) đóng gói trong `res/font`, chạy offline. Giấy phép: `third_party/licenses/BeVietnamPro-OFL.txt`.
- Phong cách **A · Tối giản ấm**: nền trắng ngà, nút navy dạng pill, điểm nhấn cam nhỏ; nội dung tách bằng khoảng trắng/đường kẻ, nút chính trong tấm đáy. Minh họa CCCD vẽ bằng Canvas, không thêm ảnh hay thư viện.
- Kiểu chữ dùng `VcType`: tiêu đề 32 sp/Bold, dòng 1,2; thân chữ 15 sp, dòng 1,5. Các màn căn mặt/nháy màu/quay đầu/đọc câu giữ cỡ chữ và bố cục camera cũ (`cameraTitle`, `cameraButton`, `Banner(cameraLayout = true)`). Mọi kiểu chữ Material cũng dùng Be Vietnam Pro.
- Màu chữ/nền và màu khi nhấn nút nằm trong `Theme.kt`. Chữ nút được chọn theo nền đang chuyển để giữ tương phản. Xanh đạt/cam minh họa có token chữ riêng đạt tương phản; không dùng cam làm màu chữ nhỏ trên nền sáng. Màu nháy và chấm sáng không đổi.
- Số tài khoản trong tấm đáy thành công là **dữ liệu mẫu**, luôn có nhãn tương ứng; các nhãn đã xác minh chỉ hiện theo danh sách `checked` từ phiên hiện tại.
- Hiệu ứng trang trí dùng `Vc.motion` (`ui/theme/Motion.kt`). Theme theo dõi `Settings.Global.ANIMATOR_DURATION_SCALE`; bằng 0 thì hiện trạng thái cuối ngay, kể cả khi đổi cài đặt lúc app đang mở. Chuyển màn tắt ở cả hai chiều khi đi vào/ra camera. Không dùng thời lượng này cho lịch màu/chấm sáng do server cấp.
- Rung nhẹ sau khi chụp CCCD và khi thành công dùng phản hồi hệ thống (`CONTEXT_CLICK`), tôn trọng cài đặt rung của máy, không xin thêm quyền.
- Ảnh Paparazzi đặt `motionEnabled = false` để so bố cục ở trạng thái tĩnh. Chạy `recordPaparazziDebug --tests '*ScreensSnapshotTest*'` trước/sau khi sửa; không commit ảnh trong `app/src/test/snapshots/`.
- Chưa dùng lại code từ `AIVIETNAM-AIO-QP09/eKYC-system`; khi chép Keystore từ đó (SEC-02) phải giữ dòng giấy phép MIT và ghi vào `third_party/README.md`.

Kiểm tra giảm chuyển động trên máy ảo: khi app đang ở màn đăng ký/đăng nhập, chạy `adb shell settings put global animator_duration_scale 0`, kiểm tra các thẻ đứng yên và nút/OTP đổi ngay. Đặt lại giá trị ban đầu sau khi thử (thường là `1`; nếu ban đầu chưa có giá trị thì dùng `adb shell settings delete global animator_duration_scale`). Vẫn phải thử cảm giác rung trên điện thoại thật.
