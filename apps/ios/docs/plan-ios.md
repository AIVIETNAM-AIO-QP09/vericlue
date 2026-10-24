# Kế hoạch app iOS (người làm: anh Lý, trên Mac)

- **Ngày:** 24/10/2026. **Người soạn:** Ngọc Quang + Claude.
- **Trạng thái:** trưởng nhóm đồng ý làm bản iOS (nói miệng 24/10). **Chưa sửa ADR-0014** (đang ghi "iOS không làm"): trưởng nhóm sửa, xem mục 12.
- **Hạn:** nộp vòng 2 trước **06/11/2026**. App Android vẫn là bản nộp chính. iOS là bản thêm: nếu không kịp phần nào thì cắt theo mục 9, không kéo trễ Android.

## 1. Mục tiêu

App iPhone cho người dân chạy **đúng luồng của app Android**, gọi **cùng server, cùng hợp đồng**:

> đăng ký → OTP → chụp CCCD → xác nhận thông tin → căn mặt → nháy màu → chấm sáng → quay đầu → (đọc câu nếu server yêu cầu) → kết quả.

Không cần làm mới server, hợp đồng hay mô hình: tất cả đã có (PR #46 app Android, PR #47 hợp đồng).

Luật dự án vẫn giữ nguyên (AGENTS.md §6), đặc biệt:
- **Luật 3:** người dân không bao giờ thấy điểm số hay chữ "giả mạo". App chỉ đổi màn theo `pass | retry | review | voice_challenge`. Câu nhắc chụp lại chỉ nói về chất lượng.
- **Luật 4:** trạng thái lạ, lỗi mạng, JSON hỏng thì ra màn lỗi, **không bao giờ** thành đạt.

## 2. Cần chuẩn bị

| Thứ | Ghi chú |
|---|---|
| Mac, Xcode 16 trở lên | Miễn phí trên App Store |
| **iPhone thật**, iOS 16 trở lên | **Simulator không có camera** (không dùng webcam như máy ảo Android). Phần mặt, nháy màu, quay đầu chỉ thử được trên máy thật |
| Apple ID | Apple ID thường là cài được lên iPhone cắm vào Mac. App hết hạn sau 7 ngày, phải cài lại; tối đa 3 app tự build. Muốn gửi giám khảo tự cài (TestFlight) thì cần Apple Developer Program, 99 USD/năm (câu hỏi ở mục 12) |
| Server | Chạy API mock trên Mac theo `apps/android/README.md`, mục "Chạy thử với API mock". iPhone gọi bằng IP mạng LAN của Mac (ví dụ `http://192.168.1.20:8000/`), không phải `10.0.2.2` |
| Claude Code (hoặc Codex) trên Mac | Để "vibecode" theo mục 10 |

Trên iPhone: bật **Developer Mode** (Cài đặt → Quyền riêng tư & Bảo mật). Lần đầu chạy, vào Cài đặt → Cài đặt chung → Quản lý VPN & Thiết bị để tin cậy nhà phát triển.

## 3. Công nghệ

Chỉ dùng thư viện của Apple, nên không phải lo giấy phép (luật 6).

| Việc | Android đang dùng | iOS dùng |
|---|---|---|
| Giao diện | Jetpack Compose | **SwiftUI** |
| Camera trước/sau, khung hình | CameraX | **AVFoundation**: `AVCaptureSession` + `AVCaptureVideoDataOutput` |
| Quay MP4 | CameraX `Recorder` | **`AVAssetWriter`** ghi H.264 từ chính các khung của `VideoDataOutput`. Không dùng `AVCaptureMovieFileOutput`, vì nó khó chạy song song với `VideoDataOutput` |
| Dò mặt, góc quay đầu | ML Kit Face Detection | **Vision** `VNDetectFaceRectanglesRequest` (`yaw`, `roll`; `pitch` từ iOS 15) |
| Đọc QR CCCD | ML Kit Barcode | **Vision** `VNDetectBarcodesRequest` (symbology `.qr`) |
| Ghi âm WAV 16 kHz mono | `AudioRecord` | **`AVAudioEngine`** (chuyển về 16 kHz bằng `AVAudioConverter`), tự ghi header WAV như `Wav.encode` |
| Gọi API | OkHttp + kotlinx.serialization | **`URLSession` async/await + `Codable`**, viết tay như `Api.kt` |
| Khóa phơi sáng, cân bằng trắng | Camera2 interop | `AVCaptureDevice.lockForConfiguration()`: `exposureMode = .locked`, `whiteBalanceMode = .locked` |
| Độ sáng màn hình | `FullBrightness` | `UIScreen.main.brightness = 1`, `isIdleTimerDisabled = true` |

**Client API viết tay** cho nhanh và giống Android. Dùng `swift-openapi-generator` của Apple (Apache-2.0) để sinh từ `openapi.json` thì đúng tinh thần ADR-0014 hơn, nhưng để sau.

## 4. Cấu trúc thư mục (đối chiếu với Android)

```
apps/ios/
  VeriClue.xcodeproj
  VeriClue/
    VeriClueApp.swift          ← MainActivity.kt
    Flow/FlowRules.swift       ← flow/Flow.kt        (luật thuần, có test)
    Flow/LiveFlow.swift        ← flow/LiveFlow.kt    (phiên → media → signals → finalize → voice; nhớ bước đã nhận)
    Data/Api.swift             ← data/api/Api.kt     (model Codable + gọi API)
    Capture/CameraSession.swift← capture/CameraSession.kt
    Capture/Signals.swift      ← capture/Signals.kt  (đồng hồ chung, QualityGate, TurnTracker, ColorSchedule)
    Capture/WavRecorder.swift  ← capture/WavRecorder.kt
    Capture/IdCard.swift       ← capture/IdCard.kt   (đo nét/lóa, đọc QR CCCD)
    Capture/CamProbe.swift     ← capture/CamProbe.kt
    Capture/Regions.swift      ← capture/Regions.kt  (region_means)
    UI/Theme.swift             ← ui/theme/Theme.kt   (màu Figma "VeriClue / Màu")
    UI/Components/…            ← ui/components/
    UI/Screens/…               ← ui/screens/ (Start, Identity, Face, VoiceResult)
    UI/AppNavigation.swift     ← ui/App.kt (NavigationStack + các route trong FlowRules)
  VeriClueTests/               ← app/src/test/
  docs/plan-ios.md             (file này)
  README.md                    cách build, chạy trên iPhone, trỏ server
```

**Cách port nhanh:** mở file Kotlin bên trái, nhờ AI viết file Swift bên phải, giữ nguyên tên hàm, tên route và câu chữ tiếng Việt. Câu chữ nằm sẵn trong code Android, đã qua `CitizenCopyTest` (không có chữ cấm).

## 5. Hợp đồng server (không đổi, chỉ gọi)

Nguồn: `packages/contracts/schemas/session.schema.json` và `openapi.json` (bản ở PR #47). Mọi lần gọi trong phiên gửi `Authorization: Bearer <token>`.

| Bước | Endpoint | Ghi chú |
|---|---|---|
| Tạo phiên | `POST /v1/sessions` | Header `X-Mock-Scenario` khi thử với API mock. Trả `challenge` gồm `color_sequence`, `turn_order`, `dot_path` |
| OTP | `POST …/otp` `{phone}` → `simulated_sms`; `POST …/otp/verify` `{code}` → `pass`/`retry` + `attempts_left` | 409 `otp_expired`, `otp_locked`: hiện câu nhắc và nút "Gửi lại mã" |
| CCCD | `POST …/id-card` (multipart `front`, `back`, `qr`) → `ok` + `fields` hoặc `retry` + `retry_hint` | `retry` thì quay lại chụp mặt sau |
| Xác nhận thông tin | `POST …/id-card/confirm` (các trường đã xác nhận) | Trường để nguyên thì gửi giá trị server trả về; chỉ trường người dùng sửa mới khác |
| Thử thách mới | `POST …/challenge` | Gọi **trước mỗi lượt quay mặt**: sau bước A, sau chụp lại, sau gián đoạn |
| Khuôn mặt | `POST …/media` (multipart `image` JPEG + `video` MP4) → `POST …/signals` → `POST …/finalize` | `retry` kèm `challenge` mới; `voice_challenge` kèm `voice_prompt` |
| Giọng | `POST …/voice` (multipart `audio` WAV + `video` MP4 + `audio_offset_ms`) | Chỉ gọi khi `finalize` trả `voice_challenge` (câu 5) |

**Thử lại sau lỗi mạng:** làm như `LiveFlow.kt`. Nhớ `mediaAcked`, `signalsAcked`; gửi lại thì chỉ gửi bước chưa được nhận. 409 khi gửi lại thì coi là đã nhận, trừ `session_closed`. Test cho phần này có sẵn ở `LiveFlowRetryTest.kt`: port sang Swift.

## 6. Tín hiệu gửi server (`Signals`)

- `color_events` `{index, rgb, painted_at}`: lúc mỗi màu thật sự được vẽ. Dùng `CADisplayLink.timestamp`, không dùng lúc gọi lệnh đổi màu.
- `dot_events` `{index, x, y, painted_at}`: lúc chấm sáng tới mỗi điểm của `dot_path`.
  - `x`, `y` theo tỉ lệ **vùng chấm chạy**, giống Android.
  - Chấm đi thẳng giữa hai điểm liền nhau, theo `t_ms`.
- `frame_times` `{capture_time, presented_frames, media_time}`: mỗi khung trong video. `capture_time` lấy PTS của `CMSampleBuffer`.
- **Một đồng hồ cho mọi mốc, tính bằng ms:** `CACurrentMediaTime()` × 1000, cùng gốc với `CADisplayLink.timestamp` và PTS của camera (đồng hồ host). Ngày đầu phải đo trên máy thật xem ba nguồn có cùng gốc không.
- `client_quality`: `client = "ios"`, `clock = "CACurrentMediaTime"`, `timestamp_source`, `fps`, `has_video`.
- `camprobe`: cờ `ios:simulator`, `ios:jailbreak`, `ios:debugger`; kèm `device_label`, `duplicate_frame_ratio`. Server coi mọi cờ là không đạt (câu 9), nên demo trên iPhone thật, không chạy trên Simulator.
- `region_means`: 5 vùng da + nền, tính theo tỉ lệ hộp mặt giống Android (`Regions.kt`). Chờ PRES-02 chốt định nghĩa (câu 10).

## 7. Những bẫy đã gặp ở Android (tránh lặp lại)

1. **Camera bật liên tục** từ căn mặt tới hết đọc câu (ADR-0013 nguyên tắc 4). Dùng **một** `AVCaptureSession` cho cả luồng. Đổi màn không được dựng lại session, vì sẽ hủy đoạn quay.
2. **Chụp ảnh chính diện lúc nền xám, trước khi nháy màu.** Khóa AE/AWB sau nền xám, mở khóa sau nháy màu.
3. **Video quay suốt nháy màu và chấm sáng**, dừng khi chấm chạy xong. Server cần video lúc chấm chạy để đo ánh mắt (LIVE-02).
4. **Gián đoạn** (`scenePhase` sang `.background` lúc đang quay hoặc ghi âm): bỏ lượt, hiện màn "Xác minh bị gián đoạn", làm lại phần mặt bằng `POST …/challenge`.
5. **Đọc câu:** chỉ bắt đầu ghi WAV khi video đã có khung đầu. Gửi `audio_offset_ms` = độ dài video đã quay lúc WAV bắt đầu.
6. **Xóa file MP4 tạm** khi server đã nhận, khi rời luồng, khi gián đoạn.
7. **Màn thành công** chỉ tích những gì server đã kiểm: "Khuôn mặt", và "Giọng nói" nếu đã gửi giọng.
8. **Camera trước bị lật gương**: góc `yaw` của Vision và chữ "Quay sang trái/phải" phải kiểm trên máy thật. Trái/phải là theo **người dùng**.
9. **Kết nối:** bản Release chỉ gọi HTTPS (địa chỉ cloudflared). Bản Debug cho phép HTTP trong mạng LAN bằng `NSAllowsLocalNetworking` trong `Info.plist`, chỉ ở Debug.
10. **Quyền:** `NSCameraUsageDescription`, `NSMicrophoneUsageDescription`, viết bằng tiếng Việt. Khóa màn dọc.
11. **Nút debug** "Chụp ngay", "Bỏ qua" chỉ có ở bản Debug (`#if DEBUG`), như Android.

## 8. Các bước (task) và tiêu chí xong

Ước lượng tính bằng ngày công khi làm cùng AI.

| Mã | Việc | Ước lượng | Xong khi |
|---|---|---|---|
| IOS-01 | Khung app SwiftUI, theme, toàn bộ màn theo Figma, điều hướng 3 luồng, chế độ demo (`DemoOutcome`) như Android | 2 | Chạy hết các màn trên Simulator; có màn "Xem tất cả màn" ở bản Debug |
| IOS-02 | `Api.swift`, `LiveFlow.swift`, `FlowRules.swift` + test (port `LiveFlowTest`, `LiveFlowRetryTest`, `LiveFlowStageATest`, `FlowRulesTest`) | 1,5 | Test XCTest xanh với `URLProtocol` giả; giải mã được các file trong `packages/contracts/examples/session.*.json` |
| IOS-03 | Camera trước: căn mặt (Vision), ảnh chính diện, nháy màu theo `challenge`, chấm sáng theo `dot_path`, quay đầu theo `turn_order`, quay MP4, `color_events`, `dot_events`, `frame_times`, `camprobe` | 3 | Trên iPhone thật, với API mock: `genuine` ra thành công; server nhận JPEG, MP4 và đủ tín hiệu |
| IOS-04 | Đọc câu: WAV 16 kHz + MP4 cùng lúc, `audio_offset_ms` | 1 | `voice_clone` → đọc câu → chờ duyệt; server nhận WAV và MP4 |
| IOS-05 | Bước A: OTP mô phỏng, camera sau chụp CCCD (đo nét/lóa, đọc QR), xác nhận/sửa thông tin | 1,5 | OTP sai/đúng/hết hạn hiện đúng câu; server nhận 2 ảnh CCCD và trả thông tin từ QR |
| IOS-06 | Gián đoạn, thử lại khi mất mạng, xóa file tạm, bản Release HTTPS, thử cả luồng trên máy thật, ghi số đo | 2 | Checklist mục 11 đạt; có bàn giao kèm số đo thật |

**Tổng khoảng 11 ngày công.** Từ 25/10 tới 05/11 còn 12 ngày, nên rất sát. Thứ tự làm: IOS-01 → 02 → 03 → 04 → 05 → 06. Hai việc IOS-01 và IOS-02 làm song song được (hai phiên AI, khác file).

## 9. Nếu không kịp thì cắt theo thứ tự này

1. Bỏ IOS-05 phần camera sau: CCCD dùng chế độ demo (thông tin mẫu), vẫn giữ OTP.
2. Bỏ `region_means`.
3. Bỏ chấm sáng: chỉ nháy màu + quay đầu (server sẽ coi lớp ② thiếu; ghi rõ khi demo).
4. Tối thiểu để demo: IOS-01 + 02 + phần nháy màu và quay đầu của IOS-03 + IOS-04.

Bản dự phòng cuối cùng trên iPhone: mở web `/verify` bằng Safari.

## 10. Cách "vibecode" cho nhanh mà không lệch

1. Clone repo, đọc `AGENTS.md`, mở Claude Code ở thư mục gốc repo.
2. Mỗi task một nhánh: `feat/IOS-01-swiftui-shell`, …; commit có mã task (`feat(ios): … [IOS-01]`).
3. Câu lệnh mẫu cho AI:
   > Đọc `apps/ios/docs/plan-ios.md` và `AGENTS.md`. Port `apps/android/app/src/main/java/vn/vericlue/app/flow/LiveFlow.kt` sang `apps/ios/VeriClue/Flow/LiveFlow.swift`, giữ nguyên hành vi và tên hàm; port luôn `LiveFlowRetryTest.kt` sang XCTest. Không đổi hợp đồng.
4. Không để AI "sáng tạo" luồng hay câu chữ. Android là đặc tả: lệch chỗ nào thì sửa iOS cho giống Android, hoặc ghi câu hỏi vào bàn giao.
5. Phần camera (IOS-03) phải thử trên iPhone thật **sau mỗi bước nhỏ**, vì AI không chạy được camera.
6. Hết mỗi phiên: ghi bàn giao (`uv run python scripts/new_handoff.py --task IOS-0x --who "Lý Anh Quân+<AI>"`).

## 11. Kiểm tra trước khi coi là xong

- [ ] `genuine` → thành công; màn thành công chỉ tích phần server đã kiểm.
- [ ] `low_quality` → "Chụp lại" với câu nhắc và số lần còn lại lấy từ server; lượt sau gọi `/challenge`.
- [ ] `voice_clone` → đọc câu → chờ duyệt; server nhận WAV + MP4 + `audio_offset_ms`.
- [ ] Tắt Wi-Fi lúc gửi → "Không kết nối được"; "Thử lại" khi vẫn mất mạng không bao giờ ra thành công.
- [ ] Chuyển app xuống nền lúc đang quay → "Xác minh bị gián đoạn".
- [ ] OTP sai → "Mã chưa đúng. Bạn còn N lần thử."; đúng → sang chụp CCCD.
- [ ] Không màn nào có điểm số hay chữ "giả mạo" (port `CitizenCopyTest`).
- [ ] Không commit ảnh, video, âm thanh, khóa ký, file `.env`.
- [ ] Số đo thật ghi vào bàn giao: fps, độ lệch video–WAV, dung lượng MP4, thời gian tải.

## 12. Cần trưởng nhóm chốt trước khi bắt đầu

| # | Câu hỏi | Đề xuất |
|---|---|---|
| 1 | Sửa ADR-0014 (đang ghi "iOS không làm") | Ghi: bản demo có thêm app iOS (SwiftUI, Vision), người làm Lý Anh Quân; Android vẫn là bản nộp chính |
| 2 | Thêm IOS-01..06 vào `docs/plan/backlog.md` và task card | Người làm: Lý Anh Quân; sprint S2 |
| 3 | Apple Developer Program 99 USD/năm (để giám khảo cài qua TestFlight) | Không mua cho vòng 2: demo bằng iPhone của nhóm, cài qua cáp |
| 4 | Bundle ID và tên app | `vn.vericlue.app`, tên "VeriClue", giống Android |
| 5 | iOS dùng Vision, Android dùng ML Kit | Chấp nhận: cả hai chỉ dùng để hướng dẫn người dùng, không ra phán quyết (ADR-0014 mục 3) |
