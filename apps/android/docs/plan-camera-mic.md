# Kế hoạch: gắn camera, micro và API vào app Android

- **Task:** APP-01 (phần API còn lại), APP-02, APP-03, APP-04, và phần việc trên app của LIVE-02.
- **Người làm:** Lý Anh Quân (+ AI). **Người duyệt:** Ngọc Quang, trưởng nhóm.
- **Ngày viết:** 23/10/2026. **Hạn nộp:** trước 06/11/2026.
- **Khung có sẵn:** nhánh `feat/APP-01-android-ui`: đủ màn, điều hướng 3 luồng, dữ liệu giả. Bảng "chỗ giả → thay bằng gì" ở `apps/android/README.md`.

## 1. Đọc trước (theo thứ tự)

1. `apps/android/README.md`: cách build, cấu trúc code, các chỗ đang giả.
2. ADR-0014 (app Kotlin, HTTPS qua cloudflared, cập nhật 21/10), ADR-0016 (giai đoạn B gọn còn 2 việc), ADR-0017 (thông báo làm lại, gián đoạn, tải media).
3. Hợp đồng: `packages/contracts/schemas/session.schema.json`, `packages/contracts/openapi.json`, `packages/contracts/chromapulse.json`.
4. **Bản web làm mẫu:** `apps/web/src/lib/capture/`. Web đã làm nháy màu, ghi tín hiệu, ghi âm WAV và máy trạng thái của luồng. Code này do nhóm viết, dịch sang Kotlin được, không vướng giấy phép:

   | File web | Dùng làm mẫu cho |
   |---|---|
   | `flow.ts`, `runner.ts` | Máy trạng thái, thứ tự gọi API, cách xử lý lỗi |
   | `chromapulse/sequence.ts`, `trial.ts`, `record.ts`, `assemble.ts` | Phát chuỗi màu, ghi thời điểm, gom `signals` |
   | `quality.ts`, `messages.ts` | Cổng chất lượng, câu nhắc theo `retry_hint` |
   | `voiceRecorder.ts`, `wav.ts` | Ghi âm, đóng gói WAV |

## 2. Luật phải giữ (AGENTS.md §6)

- **Server là trọng tài.** App chỉ quay, ghi, gửi. Không tự kết luận đạt hay không.
- **Người dân chỉ thấy** `pass | retry | review | voice_challenge`. Không hiện điểm số, không hiện chữ "giả mạo". `CitizenCopyTest` đang chặn chữ cấm, đừng tắt test này.
- **Lỗi mạng, phản hồi sai dạng, status lạ đều coi là lỗi**, không bao giờ coi là đạt (luật 4). Làm như `flow.ts` dòng 421: "Chỉ `pass` mới là đạt".
- **Không commit** ảnh, video, âm thanh thật, kể cả file để test. Dữ liệu test để ngoài repo.
- **Thư viện mới** ghi vào `third_party/README.md`. Code chép từ `eKYC-system` (MIT) phải giữ dòng giấy phép.
- **Màn camera và màn nháy màu không thêm hiệu ứng trang trí.**

## 3. Chọn thư viện

| Phần | Dùng | Ghi chú |
|---|---|---|
| Camera | CameraX 1.4 (`camera-camera2`, `camera-lifecycle`, `camera-view`, `camera-video`) | Dùng Camera2Interop để khóa phơi sáng (AE) và cân bằng trắng (AWB) lúc nháy màu |
| Dò mặt để hướng dẫn | ML Kit Face Detection, bản đóng gói sẵn trong app (`com.google.mlkit:face-detection`) | Lấy khung mặt, góc quay đầu `headEulerAngleY`, mắt mở. **Không dò mống mắt trên máy** (server làm, LIVE-02) |
| Đọc QR trên CCCD | ML Kit Barcode Scanning (`com.google.mlkit:barcode-scanning`) | |
| Ghi âm | `AudioRecord`, PCM 16-bit, mono, 16 kHz, rồi tự ghi đầu file WAV | Không dùng `MediaRecorder` vì nó chỉ ra AAC |
| Quay video | CameraX `VideoCapture`, ra MP4 (H.264) | Xem câu hỏi Q1 ở mục 9 |
| Gọi API | Retrofit + OkHttp + kotlinx.serialization; client sinh từ `openapi.json` bằng openapi-generator (`kotlin`, thư viện `jvm-retrofit2`) | Đúng tiêu chí APP-01 |
| Trạng thái, luồng | `ViewModel` + `StateFlow` + Coroutines | Chưa cần Hilt |
| Khóa, ký (sau) | Android Keystore | SEC-02, chưa làm trong plan này |

## 4. Một đồng hồ duy nhất (rất quan trọng)

Server so thời điểm đổi màu với thời điểm khung hình (lớp ① ánh sáng), và so đường chấm sáng với đường mắt (lớp ②). Nếu hai thứ dùng hai đồng hồ khác nhau, kết quả sai hết.

- Mọi mốc thời gian dùng **`SystemClock.elapsedRealtimeNanos()`**, đổi ra ms (số thực) khi gửi.
- Thời điểm màu thật sự hiện lên màn hình: lấy `frameTimeNanos` của `Choreographer.FrameCallback` ở khung vẽ đầu tiên sau khi đổi màu. Không lấy lúc gọi hàm đổi màu.
- Thời điểm của từng khung hình camera: `ImageProxy.imageInfo.timestamp`. Kiểm `CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE`:
  - nếu là `REALTIME` thì cùng gốc với `elapsedRealtimeNanos`;
  - nếu là `UNKNOWN` thì ghi cờ vào `client_quality` để server biết.
- Hợp đồng đang mô tả các trường theo cách của web (`performance.now()`, `requestVideoFrameCallback`). Bản app gửi cùng tên trường, giá trị lấy theo cách trên, và thêm `client_quality.clock = "elapsedRealtime"`. Nếu cần đổi mô tả trong schema thì mở PR riêng gắn `[contract]` (luật 1).

## 5. Kiến trúc thêm vào

```
app/src/main/java/vn/vericlue/app/
  data/api/            client sinh từ openapi + ApiRepository (bọc lỗi thành kết quả, không ném ra UI)
  data/config/         BuildConfig.API_BASE_URL (đọc từ gradle.properties hoặc local.properties, không cứng trong code)
  capture/camera/      CameraController: mở camera trước/sau, Preview, ImageAnalysis, VideoCapture, khóa AE/AWB
  capture/face/        FaceAnalyzer (ML Kit) → FaceSignal(box, yaw, độ sáng, nét)
  capture/quality/     QualityGate: FaceSignal → LowLight / TooFar / OffCenter / Good (giống quality.ts)
  capture/chroma/      ColorSequencePlayer (phát màu theo challenge), SignalRecorder (color_events, frame_times)
  capture/audio/       WavRecorder (AudioRecord → WAV), mức âm cho sóng âm
  capture/id/          IdCardAnalyzer (QR + kiểm lóa, mờ)
  flow/VerifyViewModel.kt   máy trạng thái thật, thay DemoOutcome và các hẹn giờ
```

**Giữ nguyên các màn trong `ui/screens`.** Chỉ đổi đầu vào:

| Hiện tại | Đổi thành |
|---|---|
| `FakeCameraFeed()` | `CameraPreview(controller)`, bọc `PreviewView` bằng `AndroidView` |
| `FramingScreen(start, auto)` chạy theo hẹn giờ | `FramingScreen(state: FramingState)` nhận trạng thái từ `QualityGate` |
| `HoldStillScreen` hẹn giờ 4 màu cố định | Nhận `color_sequence` của challenge (8 bước, `hold_ms`, `transition_ms`, `baseline_ms`) |
| `TurnHeadScreen(order)` thứ tự ngẫu nhiên trên máy | Thứ tự từ server (khi FLOW-04 / LIVE-01 có trong hợp đồng); sang bước kế khi góc quay đầu đạt ngưỡng |
| `FollowDot` đường ngẫu nhiên | Đường từ server (LIVE-01); ghi `(t, x, y)` từng điểm theo mục 4 |
| `VoiceScreen` nút giả | `WavRecorder.start/stop`, câu đọc lấy từ `voice_prompt` |
| `CheckingScreen` + `DemoOutcome` | Chờ kết quả `finalize` / `voice` thật |

Màn "Xem tất cả màn" và `DemoOutcome` giữ lại **chỉ cho bản debug**, để thiết kế vẫn xem được từng màn.

## 6. Các giai đoạn

Mỗi giai đoạn mở **một PR riêng** (nhánh `feat/APP-0x-...`). Mỗi PR phải chạy được trên máy ảo và qua test, rồi mới sang giai đoạn sau. Ước lượng tính theo ngày công.

### Giai đoạn 0 · Chuẩn bị (0,5 ngày)
- Cài Android Studio trên Mac; tạo máy ảo Pixel (ảnh `arm64-v8a`). Trong Advanced Settings đặt **Camera Front = Webcam0** và **Camera Back = VirtualScene** hoặc Webcam0.
- Chạy API ở máy: `docker compose up` (API ở cổng 8000, `USE_MOCK_MODELS=true`). Máy ảo gọi máy Mac qua `http://10.0.2.2:8000`, chỉ dùng ở bản debug và chỉ bật cleartext cho đúng địa chỉ đó (`network_security_config`).
- Thêm `API_BASE_URL` vào `buildConfigField`, đọc từ thuộc tính Gradle. Không ghi cứng địa chỉ cloudflared vào code.
- **Xong khi:** app debug gọi được `GET /healthz` và hiện kết quả trong log.

### Giai đoạn 1 · Lát cắt dọc qua API thật (1 ngày, APP-01)
- Sinh client từ `openapi.json`; viết `ApiRepository` bọc lỗi thành kiểu `Result` (lỗi mạng, 401, 409, 422, 503, phản hồi sai dạng).
- `VerifyViewModel` gọi: tạo phiên → `media` (tạm gửi một ảnh JPEG chụp từ camera) → `signals` (tạm gửi mảng rỗng) → `finalize` → nếu `voice_challenge` thì `voice` → hiện màn kết quả đúng `status`.
- Chọn kịch bản mock qua header `X-Mock-Scenario`; ở bản debug cho chọn trong màn "Xem tất cả màn", thay cho `DemoOutcome`.
- **Xong khi:** đi hết một luồng trên máy ảo, nhận đúng màn kết quả cho từng kịch bản mock; tắt API giữa chừng thì ra màn lỗi mạng, không ra màn "thành công".
- **Test:** unit test `status` → màn hình (gồm status lạ → lỗi); test `ApiRepository` với MockWebServer của OkHttp.

### Giai đoạn 2 · Camera trước, quyền, căn mặt (1 ngày, APP-02)
- Xin quyền bằng `ActivityResultContracts.RequestMultiplePermissions` ở màn "Cho phép dùng camera và micro". Người dùng từ chối thì ra màn lỗi đã có; từ chối hẳn thì nút mở Cài đặt.
- `CameraController`: camera trước, `Preview` + `ImageAnalysis` (640×480, `STRATEGY_KEEP_ONLY_LATEST`).
- `FaceAnalyzer` → `QualityGate`: thiếu sáng (độ sáng trung bình vùng mặt), xa (khung mặt nhỏ hơn ~45% chiều rộng khung oval), lệch tâm, nhiều mặt. **Ngưỡng là hằng số có tên**, lấy theo `quality.ts` của web nếu có. Chỉ dẫn luôn là một câu về chất lượng.
- Đạt liên tục khoảng 1 giây thì tự chụp ảnh chính diện (lúc nền xám, trước khi nháy màu: ADR-0016) và chuyển sang Giữ yên.
- Đo fps của ImageAnalysis; dưới 15 fps thì ghi vào `client_quality` (CAP-02).
- **Xong khi:** trên máy ảo dùng webcam, đưa mặt xa/gần/tối thì chỉ dẫn đổi đúng; tự chụp được.

### Giai đoạn 3 · Nháy màu theo thử thách và gửi tín hiệu (1,5 ngày, APP-02, lớp ①)
- `ColorSequencePlayer` phát đúng `baseline_ms` nền xám, rồi 8 bước của `challenge.color_sequence` (`hold_ms` + `transition_ms`), rồi `tail_ms`. Không tự đặt màu: màu, nhịp, giới hạn an toàn lấy từ challenge và `chromapulse.json`.
- Trong lúc phát: độ sáng màn hình tối đa (`WindowManager.LayoutParams.screenBrightness = 1f`), giữ màn hình sáng, khóa AE/AWB sau giai đoạn nền (Camera2Interop: `CONTROL_AE_LOCK`, `CONTROL_AWB_LOCK`).
- Quay video bằng `VideoCapture` suốt chuỗi màu và chấm sáng. Chụp ảnh chất lượng cao ở các mốc `capture_at_ms` (lấy khung từ ImageAnalysis rồi nén JPEG).
- `SignalRecorder` ghi `color_events` (index, rgb, `painted_at`) và `frame_times`; có thể thêm `region_means` (trung vị RGB 5 vùng da + nền, giống `chromapulse/regions.ts`) nếu kịp.
- Gửi `media` (ảnh + video MP4) → `signals` → `finalize`.
- **An toàn:** giữ cảnh báo nhạy cảm ánh sáng và nút Dừng (đã có). Không phát nhanh hơn `max_changes_per_second`.
- **Xong khi:** test đơn vị kiểm lịch phát màu đúng challenge và không vượt giới hạn; trên máy ảo gửi đủ 3 bước và nhận `finalize`. **Phải thử trên điện thoại thật** (giai đoạn 9) mới biết màu phản chiếu có đo được không.

### Giai đoạn 4 · Quay đầu (0,5 ngày, APP-02 / FLOW-04)
- Dùng `headEulerAngleY` của ML Kit. Đạt khi quay quá ngưỡng (hằng số, khởi đầu khoảng 25°) và giữ khoảng 300 ms, rồi quay về nhìn thẳng. Có giới hạn thời gian; quá thì ra màn "Làm lại thử thách" (ADR-0017: hướng dẫn cách làm, không nói lớp nào không đạt).
- Thứ tự trái/phải: lấy từ server khi hợp đồng có (Q3). Trước đó dùng thứ tự trên máy và ghi TODO kèm mã task.
- Mũi tên nhích nhẹ là chuyển động chỉ dẫn, được phép.

### Giai đoạn 5 · Chấm sáng, phần trên app của LIVE-02 (0,5 ngày)
- Chấm chạy theo đường server gửi (Q3). Ghi `(t, x, y)` từng điểm theo đồng hồ ở mục 4, tọa độ chuẩn hóa 0–1 theo màn hình.
- Theo dõi góc đầu trong lúc chạy; đầu xoay quá ngưỡng thì nhắc "Giữ đầu yên, chỉ đưa mắt theo chấm sáng".
- Video phải liền mạch qua cả chuỗi màu và chấm sáng, camera không tắt (ADR-0013, nguyên tắc 4).
- App **không** dò mống mắt.

### Giai đoạn 6 · Ghi âm đọc câu (1 ngày, APP-03)
- `WavRecorder`: `AudioRecord` 16 kHz, mono, PCM 16-bit, tối đa khoảng 8 giây, ghi đầu WAV giống `wav.ts`. Lấy mức âm để vẽ sóng âm.
- Câu đọc lấy từ `voice_prompt`; `voice_challenge` thì cho đọc lại 1 lần với câu mới.
- Gửi `voice` (audio + video nếu có). Camera vẫn bật trong lúc đọc.
- **Xong khi:** test đơn vị đầu WAV đúng (44 byte, 16 kHz, mono, 16 bit); trên máy ảo, mic của Mac ghi được và server nhận được.

### Giai đoạn 7 · CCCD và OTP (1,5 ngày, APP-04)
- Camera sau; ML Kit đọc QR. Các trường trong QR CCCD ngăn bằng dấu `|`; phải kiểm thứ tự trường với thẻ thật trước khi dùng.
- Kiểm chất lượng ảnh thẻ: đủ 4 góc (khung thẻ), mờ (độ nét), lóa (vùng quá sáng). Đây là cổng chất lượng trên máy, không phải phán quyết.
- Màn "Kiểm tra ảnh" đã có; nối kết quả kiểm thật vào 3 dòng của màn đó.
- OTP: theo FLOW-02 (OTP mô phỏng).
- **Phụ thuộc:** hợp đồng chưa có endpoint cho CCCD và OTP (Q4). Chưa có thì giữ giả và chỉ làm phần camera, QR.

### Giai đoạn 8 · Gián đoạn và lỗi (0,5 ngày, ADR-0017 §2)
- Đang ở giai đoạn A (đồng ý, OTP, CCCD) mà app bị đưa xuống nền thì quay lại làm tiếp; gia hạn phiên khi server hỗ trợ (LIVE-06).
- Đang ở giai đoạn B hoặc C mà app xuống nền hoặc có cuộc gọi: dừng camera, **bỏ dữ liệu khuôn mặt của lượt dở**, hiện màn "Xác minh bị gián đoạn", rồi làm lại phần khuôn mặt với thử thách mới.
- Hết phiên, 401, 409, 503, mất mạng: mỗi loại có màn riêng (đã có). Chuỗi lỗi luôn kết thúc ở một màn lỗi, không bao giờ ở màn thành công.

### Giai đoạn 9 · Thử trên điện thoại thật (1 ngày)
- Đường hầm `cloudflared` tới API trên máy demo (ADR-0014). Cài APK lên điện thoại Android 10+ của nhóm.
- Đo và ghi lại (không bịa số; ghi rõ máy, phiên bản app, số lần thử):
  - fps ImageAnalysis;
  - dung lượng và thời gian gửi video qua 4G (ADR-0017 §3);
  - số lần nháy màu bị máy tự chỉnh sáng làm hỏng.
- Ghi kết quả vào file bàn giao.

**Tổng:** khoảng 8,5 ngày công. Nếu thiếu thời gian, ưu tiên đi một luồng đầu–cuối trước: giai đoạn 0 → 1 → 2 → 3 → 6 → 9 (khoảng 5,5 ngày). Giai đoạn 4, 5, 7, 8 làm sau.

**Lịch gợi ý:** 24–25/10 làm giai đoạn 0–2 · 26–27/10 giai đoạn 3 · 28/10 giai đoạn 6 · 29/10 giai đoạn 4–5 · 30–31/10 giai đoạn 7 · 01/11 giai đoạn 8 · 02–04/11 giai đoạn 9 và sửa lỗi.

## 7. Kiểm thử

- **Unit test (JVM):** máy trạng thái (`status` → màn, lỗi không bao giờ thành đạt), lịch phát màu, đầu WAV, `QualityGate` với `FaceSignal` giả, đọc QR từ chuỗi mẫu tự tạo (không dùng dữ liệu thẻ thật).
- **Paparazzi:** giữ `ScreensSnapshotTest` chạy được; màn nào đổi tham số thì cập nhật test.
- **Thử tay trên máy ảo**, mỗi PR một lượt:
  1. Đăng ký: đi hết luồng, ra màn thành công.
  2. Đăng nhập lại: không qua CCCD và giọng nói.
  3. Kịch bản mock `retry`, `review`, `voice_challenge` ra đúng màn.
  4. Từ chối quyền camera, micro.
  5. Tắt API giữa chừng.
  6. Đưa app xuống nền giữa lúc nháy màu.
- **Lệnh trước khi mở PR:** `./gradlew testDebugUnitTest assembleDebug` xanh; dán kết quả thật vào PR.

## 8. Định nghĩa xong cho mỗi PR

- [ ] Đạt mục "Xong khi" của giai đoạn.
- [ ] Có test cho logic mới; test xanh.
- [ ] Khớp hợp đồng; đổi hợp đồng thì PR riêng gắn `[contract]`.
- [ ] Không có ảnh, video, âm thanh thật hay khóa bí mật trong commit.
- [ ] Thư viện mới đã ghi `third_party/README.md`.
- [ ] Cập nhật `apps/android/README.md` (bảng "chỗ giả") và dòng task trong `docs/plan/backlog.md`.
- [ ] Có file bàn giao (`uv run python scripts/new_handoff.py --task <MÃ> --who "Lý Anh Quân+<AI>"`).

## 9. Câu hỏi cần trưởng nhóm chốt trước hoặc trong lúc làm

Bản đầy đủ để trưởng nhóm trả lời (13 mục, gồm cả Q1–Q6 dưới đây): [`can-chot.md`](can-chot.md).

| # | Câu hỏi | Vì sao cần | Đề xuất |
|---|---|---|---|
| Q1 | Video từ app là MP4, ADR-0017 đang ghi WebM | Server đã nhận `.mp4` (`services/api/.../storage.py`), chỉ cần sửa ADR | Ghi "WebM trên web, MP4 trên app" |
| Q2 | Dùng ML Kit hay MediaPipe trên app | ADR-0014 để ngỏ | ML Kit (gọn, có góc quay đầu và QR; mống mắt do server dò) |
| Q3 | Hợp đồng cho đường chấm sáng và thứ tự quay đầu (LIVE-01, FLOW-04) | Chưa có trong `session.schema.json` | M5 làm LIVE-01 trước giai đoạn 4–5 |
| Q4 | Endpoint cho OTP và CCCD (FLOW-02, FLOW-03) | Chưa có trong `openapi.json` | Làm phần camera và QR trước, chờ endpoint |
| Q5 | Thứ tự đọc câu | ADR-0016 (22/10): luôn đọc câu sau giai đoạn B. API MVP: chỉ đọc khi `finalize` trả `voice_challenge` | Chốt một cách; app làm theo API hiện tại cho tới khi hợp đồng đổi |
| Q6 | `signals.frame_times` và `camprobe` trên app native | Schema đang mô tả theo web | Gửi cùng tên trường theo mục 4; `camprobe` để rỗng và ghi cờ, kiểm root/hook làm sau |

## 10. Cách review plan và PR

- **Quang:** kiểm màn hình và chữ hiển thị vẫn khớp Figma; luồng đúng ADR-0016/0017.
- **Trưởng nhóm:** chốt Q1–Q6; duyệt từng PR theo mục 8.
- Mỗi PR kèm ảnh chụp màn hình trên máy ảo hoặc điện thoại thật.

## 11. Đã làm tới đâu (cập nhật 24/10, nhánh `feat/APP-02-camera-mic-scaffold`)

Bản dựng khung do Ngọc Quang + Claude làm trước để anh Lý lấy về làm tiếp. Đã chạy hết luồng trên máy ảo với API mock. **Chưa thử trên điện thoại thật.**

| Giai đoạn | Trạng thái | Ghi chú |
|---|---|---|
| 0 · Chuẩn bị | Xong | `API_BASE_URL` qua `-Pvericlue.apiBaseUrl`; debug cho HTTP tới `10.0.2.2` |
| 1 · Lát cắt dọc API | Xong (client viết tay) | Chưa sinh từ `openapi.json` |
| 2 · Camera trước, căn mặt | Xong phần khung | Ngưỡng `QualityGate` cần chỉnh trên máy thật |
| 3 · Nháy màu, tín hiệu | Xong phần khung | Có khóa AE/AWB, quay MP4, `color_events`, `frame_times`, `region_means` (vùng theo hộp mặt ML Kit), `camprobe` (máy ảo, root, hook, khung lặp) |
| 4 · Quay đầu | Một phần | Dùng góc ML Kit; thứ tự chờ LIVE-01; chưa kiểm chiều dấu góc |
| 5 · Chấm sáng | Chưa | Chờ hợp đồng đường đi (Q3) |
| 6 · Ghi âm | Xong | WAV 16 kHz; câu từ `voice_prompt` |
| 7 · CCCD, OTP | Một phần | Camera sau, QR, đo nét/lóa, điền từ QR; chưa gửi server (Q4) |
| 8 · Gián đoạn | Xong phần app | Phiên mới khi làm lại vì chưa có LIVE-06 |
| 9 · Máy thật | Chưa | |

Cập nhật 24/10 (sáng):
- Không còn văng app khi thiếu camera: tự chuyển camera khác, bỏ quay video nếu máy không hỗ trợ, hoặc hiện "Thiết bị chưa đáp ứng".
- `ContractTest` đối chiếu model của app với `session.schema.json`.
- Bản release bật R8 và tách APK theo loại chip: bản arm64 còn 22 MB.
- CI có job Android (chạy khi mở PR hoặc push vào `main`).
- Màn chụp lại: icon và câu nhắc theo `retry_hint` của server.

Cách chạy thử với API mock: xem `apps/android/README.md`, mục "Chạy thử với API mock".
