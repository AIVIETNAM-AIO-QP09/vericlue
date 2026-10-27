# Kế hoạch chi tiết app iOS — VeriClue

> **Người làm:** anh Lý (Lý Anh Quân), trên Mac, làm cùng AI (Claude Code hoặc Codex).
> **Người soạn:** Ngọc Quang + Claude, 24/10/2026. **Trạng thái:** Quang đã duyệt; trưởng nhóm đã chốt mục 16 theo đề xuất (24/10). ADR-0014 và backlog (IOS-01..07) đã cập nhật.
> **Hạn:** nộp vòng 2 trước **06/11/2026**. App Android là bản nộp chính; iOS là bản thêm. Không kịp phần nào thì cắt theo mục 14, không kéo trễ Android.

Đọc hết file này một lượt trước khi bắt đầu. Mỗi task ở mục 9 ghi rõ: làm file nào, hàm nào, gọi API nào với dữ liệu gì, thử thế nào, khi nào coi là xong. Gặp chỗ file này không nói tới thì **làm giống app Android** (`apps/android/`). Nếu Android cũng không có thì ghi câu hỏi vào file bàn giao, **không tự nghĩ ra**.

---

## Mục lục

1. Mục tiêu và phạm vi
2. Luật bắt buộc (đọc kỹ)
3. Chuẩn bị máy và tài khoản
4. Chạy server trên Mac để thử
5. Tạo project Xcode
6. Cấu trúc thư mục và đối chiếu với Android
7. Hợp đồng API: từng lệnh gọi, gửi gì, nhận gì
8. Dòng thời gian phần khuôn mặt (quan trọng nhất)
9. Các task IOS-01 → IOS-07, từng bước
10. Câu chữ hiển thị
11. Xử lý lỗi và trạng thái
12. Những bẫy đã gặp ở Android
13. Kiểm tra cuối và bàn giao
14. Nếu không kịp thì cắt gì
15. Câu lệnh mẫu cho AI
16. Đã chốt (24/10)

---

## 1. Mục tiêu và phạm vi

App iPhone cho người dân, chạy **cùng server, cùng hợp đồng** với app Android. Luồng đăng ký (`purpose = onboarding`):

```
Màn ngân hàng mẫu → Chào → Đăng nhập/Đăng ký → Điều khoản → Đồng ý → Giới thiệu → Quyền camera/micro
→ Số điện thoại → OTP → Chụp CCCD mặt trước → Xem lại → Mặt sau → Xem lại → Kiểm tra thông tin (sửa nếu cần)
→ Chuẩn bị → Căn mặt → [một bản ghi video liên tục: nền xám → nháy màu → chấm sáng → quay đầu]
→ Đọc câu → Gửi → Kết quả (thành công / chờ duyệt / chụp lại / lỗi)
```

Thêm hai luồng ngắn hơn (ADR-0013):
- **Đăng nhập lại (`reauth`):** số điện thoại → OTP → quay mặt **thụ động** (không nháy màu, không chấm sáng, không quay đầu). Hiện server luôn trả `recovery_required`, vì chưa có khóa thiết bị (SEC-02).
- **Khôi phục (`recovery`):** giống đăng ký, nhưng bỏ bước CCCD.

**Không làm:** đọc chip NFC, khóa thiết bị (Secure Enclave), ký media, tải lên chia đoạn, bàn duyệt (web lo).

---

## 2. Luật bắt buộc (đọc kỹ)

Trích từ `AGENTS.md` §6. Vi phạm là PR bị trả về.

1. **Người dân không bao giờ thấy điểm số hay chữ "giả mạo".** App chỉ đổi màn theo `status` server trả. Câu nhắc chụp lại chỉ nói về **chất lượng** (ánh sáng, khoảng cách…).
2. **`error`, `degraded`, trạng thái lạ, lỗi mạng, JSON hỏng → màn lỗi.** Không bao giờ thành "thành công". Chỉ `status == "pass"` mới ra màn thành công.
3. **Không commit** ảnh, video, âm thanh, file `.env`, khóa ký, file `.p12` / `.mobileprovision`.
4. **Không chép code GPL/AGPL/LGPL** hoặc code không có giấy phép. Thư viện của Apple thì dùng thoải mái. Thêm thư viện ngoài nào cũng phải ghi vào `third_party/README.md`.
5. **Không sửa** `packages/contracts/`, `docs/adr/`, `docs/status/STATUS.md`. Thấy hợp đồng thiếu hay sai thì ghi câu hỏi, không tự sửa.
6. **Không bịa số liệu.** Số đo (fps, thời gian tải…) phải đo thật, ghi vào bàn giao.
7. Chữ hiển thị bằng **tiếng Việt có dấu**; tên biến, hàm bằng tiếng Anh.

---

## 3. Chuẩn bị máy và tài khoản

| Việc | Cách làm | Kiểm tra |
|---|---|---|
| Xcode 16+ | App Store → Xcode | `xcodebuild -version` in ra 16.x |
| iPhone thật, iOS 16+ | Bắt buộc. **Simulator không có camera** | Cài đặt → Cài đặt chung → Giới thiệu |
| Bật Developer Mode | iPhone: Cài đặt → Quyền riêng tư & Bảo mật → Chế độ nhà phát triển → Bật, máy khởi động lại | Mục đó hiện "Bật" |
| Apple ID trong Xcode | Xcode → Settings → Accounts → + → Apple ID | Thấy "Personal Team" |
| Clone repo | `git clone https://github.com/AIVIETNAM-AIO-QP09/vericlue.git` | — |
| Python + uv (để chạy server) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `uv --version` |
| Claude Code | theo hướng dẫn của nhóm | mở được ở thư mục repo |

**Giới hạn của Apple ID miễn phí:** app hết hạn sau **7 ngày** (cắm máy, bấm Run lại là xong); tối đa 3 app tự build trên một máy. Không gửi cho người khác cài được: muốn vậy thì cần tài khoản trả phí, xem mục 16.

---

## 4. Chạy server trên Mac để thử

Ở thư mục gốc repo:

```bash
uv sync --frozen --all-packages
mkdir -p tmp/media
export DATABASE_URL="sqlite:///$PWD/tmp/dev.db" MEDIA_DIR="$PWD/tmp/media" USE_MOCK_MODELS=true
uv run --frozen alembic -c services/api/alembic.ini upgrade head
uv run --frozen uvicorn vericlue_api.main:app --app-dir services/api/src --host 0.0.0.0 --port 8000
```

- `USE_MOCK_MODELS=true` là **bắt buộc**: luồng có `purpose` chỉ chạy ở chế độ mock. Chế độ thật trả `503 flow_unavailable`.
- Lấy IP của Mac trong mạng LAN: `ipconfig getifaddr en0`, ví dụ `192.168.1.20`. iPhone và Mac phải chung Wi-Fi.
- Kiểm từ iPhone: mở Safari, vào `http://192.168.1.20:8000/docs`, phải thấy trang tài liệu API.
- **Chọn kịch bản mock** bằng header `X-Mock-Scenario`: `genuine` (thật), `low_quality` (chụp lại), `voice_clone` (giọng giả, ra chờ duyệt), `print`, `replay`, `virtual_cam`, `faceswap`, `error`.

---

## 5. Tạo project Xcode

1. Xcode → File → New → Project → iOS → **App**.
2. Product Name `VeriClue`; Organization Identifier `vn.vericlue` (ra Bundle ID `vn.vericlue.app`, chờ chốt ở mục 16); Interface **SwiftUI**; Language **Swift**; tick **Include Tests**.
3. Lưu vào `apps/ios/` của repo, **không** tick "Create Git repository" (repo đã có Git).
4. Target → General → Minimum Deployments **iOS 16.0**; Device Orientation: chỉ **Portrait**.
5. Target → Signing & Capabilities → Team: Personal Team của anh.
6. Target → Info, thêm các khóa:

| Khóa | Giá trị |
|---|---|
| `NSCameraUsageDescription` | `VeriClue dùng camera để chụp giấy tờ và quay khuôn mặt khi xác minh danh tính.` |
| `NSMicrophoneUsageDescription` | `VeriClue dùng micro để ghi giọng đọc một câu ngắn khi xác minh.` |
| `UIRequiresFullScreen` | YES |
| `NSAppTransportSecurity` → `NSAllowsLocalNetworking` | YES (**chỉ** để Debug gọi `http://192.168.x.x`; bản Release dùng HTTPS) |

7. Tạo file cấu hình `Config/Debug.xcconfig` và `Config/Release.xcconfig`, mỗi file một dòng `API_BASE_URL = …`:
   - Debug: `http:/$()/192.168.1.20:8000/` (`$()` là để xcconfig không hiểu `//` thành comment).
   - Release: `https:/$()/<địa chỉ cloudflared>/`.

   Đọc trong code bằng `Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL")`, sau khi thêm khóa `API_BASE_URL = $(API_BASE_URL)` vào Info.
8. Thêm vào `.gitignore` của repo: `apps/ios/**/xcuserdata/`, `apps/ios/**/*.xcuserstate`, `apps/ios/build/`.
9. Copy font **Be Vietnam Pro** (4 file `.ttf` ở `apps/android/app/src/main/res/font/`) vào `VeriClue/Resources/Fonts/`, khai báo trong Info → `UIAppFonts`. Font này dùng giấy phép OFL, đã ghi ở `third_party/README.md`.

---

## 6. Cấu trúc thư mục và đối chiếu với Android

```
apps/ios/
  VeriClue.xcodeproj
  Config/Debug.xcconfig, Release.xcconfig
  VeriClue/
    VeriClueApp.swift              ← MainActivity.kt
    Flow/Routes.swift              ← Routes trong flow/Flow.kt (tên route giữ nguyên)
    Flow/FlowRules.swift           ← FlowRules trong flow/Flow.kt
    Flow/LiveFlow.swift            ← flow/LiveFlow.kt
    Flow/DemoFlow.swift            ← DemoOutcome, FlowState trong ui/App.kt
    Data/Models.swift              ← các data class trong data/api/Api.kt
    Data/SessionApi.swift          ← SessionApi trong data/api/Api.kt
    Capture/Clock.swift            ← CaptureClock trong capture/Signals.kt
    Capture/CameraSession.swift    ← capture/CameraSession.kt
    Capture/VideoWriter.swift      (mới: AVAssetWriter)
    Capture/FaceTracker.swift      ← phần ML Kit trong CameraSession.kt (dùng Vision)
    Capture/QualityGate.swift      ← QualityGate, TurnTracker trong capture/Signals.kt
    Capture/ColorSchedule.swift    ← ColorSchedule trong capture/Signals.kt
    Capture/WavRecorder.swift      ← capture/WavRecorder.kt
    Capture/IdCard.swift           ← capture/IdCard.kt (đo nét, lóa, đọc QR)
    Capture/CamProbe.swift         ← capture/CamProbe.kt
    Capture/Regions.swift          ← capture/Regions.kt
    UI/Theme.swift                 ← ui/theme/Theme.kt
    UI/Components/*.swift          ← ui/components/*.kt
    UI/Screens/StartScreens.swift, IdentityScreens.swift, FaceScreens.swift, VoiceResultScreens.swift
    UI/AppNavigation.swift         ← ui/App.kt (NavigationStack + điều phối)
    Resources/Fonts/*.ttf
  VeriClueTests/
    FlowRulesTests.swift           ← FlowRulesTest.kt
    LiveFlowTests.swift            ← LiveFlowTest.kt + LiveFlowRetryTest.kt + LiveFlowStageATest.kt
    ContractTests.swift            ← ContractTest.kt (giải mã packages/contracts/examples/session.*.json)
    CitizenCopyTests.swift         ← CitizenCopyTest.kt (không có chữ cấm)
    MockURLProtocol.swift          (giả server cho test)
  docs/plan-ios.md                 (file này)
  README.md                        (cách build, chạy, trỏ server — viết ở IOS-07)
```

**Lưu ý:** app Android đã chạy theo API dynamic của #49 (PR #46). File tương ứng cho phần mặt là `capture/FaceTimeline.kt` (lịch, có test `FaceTimelineTest.kt`) và `FaceTimelineScreen` ở cuối `ui/screens/FaceScreens.kt`: **port gần như nguyên văn**. Màn `HoldStillScreen` / `TurnHeadScreen` cũ chỉ còn cho chế độ demo.

---

## 7. Hợp đồng API: từng lệnh gọi, gửi gì, nhận gì

Nguồn sự thật: `packages/contracts/schemas/session.schema.json` và `packages/contracts/openapi.json`. Tài liệu: `docs/architecture/dynamic-session-api.md`. Mở `http://<mac>:8000/docs` để thử tay từng lệnh.

**Quy tắc chung:**
- Mọi lệnh sau khi tạo phiên đều gửi header `Authorization: Bearer <token>`.
- **Token đổi** sau `POST …/challenge`: lưu token mới, bỏ token cũ (token cũ trả 401).
- Thời gian dạng ISO 8601 (`2026-10-24T06:05:00Z`).
- Lỗi luôn có dạng `{"error_code": "...", "message": "..."}`. App đọc `error_code`, **không hiện `message` cho người dân**.
- Bản Debug gửi thêm header `X-Mock-Scenario: <kịch bản>` khi tạo phiên.

### 7.1 Tạo phiên — `POST /v1/sessions`

Gửi (JSON):
```json
{"purpose": "onboarding", "nonce": "ios_<22 ký tự ngẫu nhiên A-Za-z0-9_->"}
```
- `nonce`: 16–128 ký tự `[A-Za-z0-9_-]`. Sinh bằng `SecRandomCopyBytes` rồi mã hóa base64url, bỏ dấu `=`.
- `purpose`: `onboarding` | `reauth` | `recovery`, theo nút người dùng bấm ở màn Đăng nhập/Đăng ký.

Nhận về (rút gọn; bản đầy đủ ở `packages/contracts/examples/session.CreateSessionResponse.dynamic.json`):
```json
{
  "session_id": "ses_…", "token": "…", "expires_at": "…", "purpose": "onboarding", "nonce": "…",
  "challenge": {
    "challenge_id": "ch_…", "baseline_ms": 1000,
    "color_sequence": [{"rgb": "#80e09e", "hold_ms": 440, "transition_ms": 150}, … 8 bước],
    "capture_at_ms": [4023, 4799], "expires_at": "…",
    "dynamic": {
      "version": 1, "session_id": "ses_…", "nonce": "…",
      "frontal_capture_at_ms": 500,
      "gaze_points": [{"x": 0.5, "y": 0.5, "at_ms": 6534}, … 8 điểm, cách nhau 1000 ms],
      "head_turns": ["left", "right", "center"], "head_start_at_ms": 13534, "head_duration_ms": 6000,
      "voice_start_at_ms": 19534, "voice_prompt": "Tôi xác nhận …, mã …", "voice_challenge_id": "vc_…"
    }
  }
}
```
- `dynamic` **chỉ có** khi `purpose` là `onboarding` hoặc `recovery`. Với `reauth` thì không có `dynamic`: quay mặt thụ động.
- **Khi nào tạo phiên:** lúc người dùng bấm "Gửi mã" ở màn số điện thoại (phiên chứa cả OTP và CCCD).

### 7.2 OTP — `POST …/otp` rồi `POST …/otp/verify`

- Gửi mã: `{"phone": "0912345678"}`; số phải đúng `^0[0-9]{9}$`.
  - Nhận về: `{"expires_at": "…", "attempts_left": 5, "simulated_sms": "VeriClue: Mã xác minh của bạn là 356934. Mã hết hạn sau 2 phút."}`.
  - Hiện `simulated_sms` trong khung "SMS mô phỏng" ở đầu màn OTP.
- Xác nhận: `{"code": "356934"}`.
  - Nhận về `{"status": "pass", "attempts_left": 5}` → sang chụp CCCD (`reauth` thì sang quay mặt).
  - `{"status": "retry", "attempts_left": 4}` → hiện "Mã chưa đúng. Bạn còn 4 lần thử."
- Lỗi 409:

| `error_code` | Hiện gì |
|---|---|
| `otp_expired` | "Mã đã hết hạn. Hãy bấm "Gửi lại mã"." |
| `otp_locked` | "Bạn đã nhập sai quá số lần. Hãy bấm "Gửi lại mã"." |
| `otp_too_many` | màn "Tạm thời chưa thể xác minh" (gửi mã quá 3 lần) |
| `otp_already_verified` | coi như đã qua, đi tiếp |

### 7.3 CCCD — `POST …/id-card` rồi `POST …/id-card/confirm`

- Gửi (multipart):
  - `front`: ảnh JPEG mặt trước;
  - `back`: ảnh JPEG mặt sau;
  - `qr`: chuỗi QR app đọc được ở mặt sau. Thiếu thì bỏ trường này.
- Nhận về:
  - `{"status": "ok", "fields": {"full_name": "Nguyễn Văn An", "id_number": "001099012345", "date_of_birth": "1995-01-01", "sex": "Nam", "address": "…", "issued_on": "2021-06-15"}}` → màn Kiểm tra thông tin;
  - `{"status": "retry", "retry_hint": "QR_UNREADABLE" | "QR_INVALID"}` → quay lại chụp mặt sau, hiện "Chưa đọc được mã QR, hãy đưa mặt sau thẻ lại gần hơn rồi chụp lại."
- Xác nhận: gửi JSON `IdCardFields`.
  - Trường nào người dùng **không sửa** thì gửi đúng giá trị server trả; chỉ trường đã sửa mới khác.
  - Ngày gửi dạng `YYYY-MM-DD`; giới tính chỉ `Nam` hoặc `Nữ`.
  - Nhận về `{"received": true}`.
- **Hiển thị:** họ tên viết HOA; số CCCD nhóm 3 số (`001 099 012 345`) và khóa không cho sửa; ngày dạng `dd/MM/yyyy`.

### 7.4 Thử thách mới — `POST …/challenge`

- Không gửi body.
- Nhận về `{"token": "…", "expires_at": "…", "challenge": {… như 7.1, có dynamic mới, voice_prompt và voice_challenge_id mới …}}`.
- **Gọi trước mỗi lượt quay mặt**, trừ lượt đầu tiên khi phiên vừa được tạo ngay trước đó:
  - sau khi xong bước A (OTP + CCCD), vì thử thách chỉ sống 120 giây;
  - sau khi bị gián đoạn hoặc làm lại phần mặt.
- Sau `finalize` trả `retry` thì **không cần** gọi: phản hồi `retry` đã kèm `challenge` mới.
- **Phải** lưu `token` mới và thay toàn bộ `challenge` đang giữ.
- 409 `session_too_long`: phiên quá 15 phút → màn "Phiên đã hết hạn".

### 7.5 Gửi phần khuôn mặt — 3 lệnh, đúng thứ tự

1. `POST …/media` (multipart):
   - `image`: JPEG chính diện, chụp tại `frontal_capture_at_ms`;
   - `video`: MP4 của **cả** phần mặt;
   - `challenge_id`: `challenge.challenge_id` hiện tại.

   Nhận về `{"step": "media", "received": true}`.
2. `POST …/signals` (JSON), gồm:
   - `challenge_id`;
   - `color_events`: `[{"index": 0, "rgb": "#80e09e", "painted_at": 1234.5}, …]`;
   - `frame_times`: `[{"capture_time": 1234.5, "presented_frames": 1, "media_time": 0.0}, …]`;
   - `client_quality`: `{"client": "ios", "clock": "CACurrentMediaTime", "timestamp_source": "sample_buffer_pts", "fps": "30", "has_video": "true", "ae_awb_locked": "true"}`;
   - `camprobe`: xem mục 9, IOS-04;
   - `region_means`: nếu có.

   Nhận về `{"step": "signals", "received": true}`.
3. `POST …/finalize` (JSON): `{"challenge_id": "ch_…"}`. Nhận về `FinalizeResponse`:

| `status` | Làm gì |
|---|---|
| `pass` | (luồng có `purpose` hầu như không ra `pass` ở đây vì luôn phải đọc câu) → Thành công |
| `voice_challenge` | Lưu `voice_prompt`, `voice_challenge_id` → màn Đọc câu |
| `retry` | Có `retry_hint` → màn "Chụp lại" (câu nhắc theo mục 10); không có → màn "Làm lại thử thách". Thay `challenge` bằng `challenge` trong phản hồi. `attempts_left` hiện "Còn N lần chụp lại" |
| `review` | Màn "Hồ sơ đang được xác minh thêm" |
| `deny` | Màn "Xác thực không thành công, vui lòng thử lại sau" |
| `recovery_required` | Màn hướng dẫn khôi phục tài khoản (luồng `reauth`) |
| khác / thiếu | Màn lỗi dịch vụ |

### 7.6 Đọc câu — `POST …/voice`

- Gửi (multipart):
  - `audio`: WAV 16 kHz mono 16-bit;
  - `video`: MP4 quay cùng lúc với WAV;
  - `audio_offset_ms`: số nguyên, xem mục 8.4;
  - `voice_challenge_id`.
- Nhận về `VoiceResponse`: `pass` → Thành công · `review` → Chờ duyệt · `deny` → không thành công · `voice_challenge` → màn "Hãy đọc lại" với `voice_prompt` và `voice_challenge_id` **mới** (đọc lại tối đa 1 lần).

### 7.7 Mã lỗi HTTP chung

| HTTP | Nghĩa | Màn |
|---|---|---|
| 401 | Token sai/hết hạn | "Phiên đã hết hạn" |
| 409 `session_closed` | Phiên đã kết thúc | "Phiên đã hết hạn" |
| 409 `step_already_received` | Bước này server đã nhận (gửi lại sau lỗi mạng) | **Coi như đã nhận, đi tiếp** |
| 409 `challenge_mismatch`, `challenge_expired` | Lượt đã cũ | Gọi `/challenge` rồi làm lại phần mặt |
| 409 khác | Sai thứ tự | Lỗi dịch vụ |
| 422 | Dữ liệu sai (lỗi của app) | Lỗi dịch vụ, ghi log |
| 429, 503 | Bận / chưa sẵn sàng | Lỗi dịch vụ |
| Lỗi mạng, timeout | — | "Không kết nối được" + nút "Thử lại" |

---

## 8. Dòng thời gian phần khuôn mặt (quan trọng nhất)

Toàn bộ phần mặt (nền xám → màu → chấm → quay đầu) nằm trong **một video liên tục**. Mọi `at_ms` của server tính từ **khung hình đầu tiên của video đó**: `t = 0` là lúc `AVAssetWriter` ghi khung đầu. Server đo ánh mắt (#50) và quay đầu (#51) bằng cách cắt video theo đúng các mốc này, nên **lệch mốc là hỏng**.

### 8.1 Các pha (ví dụ với gói ở 7.1)

| Pha | Từ (ms) | Đến (ms) | App làm gì |
|---|---|---|---|
| Nền xám | 0 | `baseline_ms` (1000) | Màn xám nhạt, chữ "Giữ yên, nhìn thẳng". **Chụp JPEG tại `frontal_capture_at_ms`** (500). Sau pha này **khóa AE/AWB** |
| Nháy màu | `baseline_ms` | `baseline_ms + Σ(hold_ms + transition_ms)` | Mỗi bước: chuyển màu trong `transition_ms`, giữ `hold_ms`. Ghi `color_events` lúc màu **thật sự lên màn**. Hết pha thì **mở khóa AE/AWB** |
| Chấm sáng | `gaze_points[0].at_ms` | `gaze_points[7].at_ms` | Chấm ở `gaze_points[0]`; đi **thẳng, đều** tới điểm sau, tới đúng `at_ms` của điểm đó. Chữ "Giữ đầu yên, chỉ đưa mắt theo chấm sáng" |
| Quay đầu | `head_start_at_ms` | `+ head_duration_ms` (6000) | 3 đoạn, mỗi đoạn 2000 ms: `head_turns[0]`, `head_turns[1]`, `center`. Hiện mũi tên và chữ "Quay sang trái/phải", "Nhìn thẳng" |
| Dừng quay | `head_start_at_ms + 6000` | — | Dừng ghi video, **chờ ghi file xong**, sang màn "Đang gửi" → gửi phần mặt → `finalize` trả `voice_challenge` → màn Đọc câu (giống Android) |

### 8.2 Đồng hồ

- Dùng **một** đồng hồ cho mọi mốc: `CACurrentMediaTime()` (giây) × 1000 → ms.
- Thời điểm khung camera: PTS của `CMSampleBuffer` (`CMSampleBufferGetPresentationTimeStamp`), đổi sang giây bằng `CMTimeGetSeconds`. Khi `AVCaptureSession` dùng đồng hồ host (mặc định), giá trị này **cùng gốc** với `CACurrentMediaTime()`. **Ngày đầu IOS-04 phải in thử hai giá trị cạnh nhau để chắc** (chênh vài chục ms là đúng).
- Thời điểm màn hình vẽ: dùng `CADisplayLink`. `timestamp` là lúc khung **trước** đã lên màn; `targetTimestamp` là lúc khung **sắp** lên. Ghi `painted_at = targetTimestamp × 1000` cho khung có màu mới.
- `t0` = PTS của khung đầu **được ghi vào file** (khung đầu đưa vào `AVAssetWriterInput` sau `startSession`), **không phải** khung camera đầu tiên nhìn thấy. Android đã lệch 0,1–0,9 s vì nhầm hai mốc này. Mọi lịch trình chạy theo `CACurrentMediaTime() − t0`.

### 8.3 Chấm sáng — cách vẽ

- **Vùng chấm chạy là toàn màn hình**, trừ safe area. `x`, `y` (0–1) nhân với rộng/cao vùng này.
- **Không lật gương** tọa độ: `x = 0` là mép trái màn hình như người dùng nhìn thấy.
- Chấm: hình tròn đường kính 28 pt, màu chính của theme, có quầng nhạt 48 pt.
- Ở góc trên phải để một ô preview camera nhỏ (60 × 78 pt), như Android.
- Vị trí tại thời điểm `t`: tìm `i` sao cho `at_ms[i] ≤ t < at_ms[i+1]`, rồi nội suy tuyến tính `p = p[i] + (p[i+1] − p[i]) × (t − at_ms[i]) / (at_ms[i+1] − at_ms[i])`. Cập nhật mỗi khung bằng `CADisplayLink`, không dùng animation của SwiftUI, vì cần đúng mốc.

### 8.4 Đọc câu và `audio_offset_ms`

1. Vào màn Đọc câu, hiện `voice_prompt`. Người dùng bấm nút micro.
2. Bắt đầu **video mới** (file khác, cùng `AVCaptureSession`, không dựng lại session).
3. **Chờ khung đầu** của video này được ghi, rồi mới bắt đầu ghi WAV. Ghi lại `audio_offset_ms = (lúc WAV bắt đầu − PTS khung đầu) × 1000`, thường dương vài chục đến vài trăm ms.
4. Bấm dừng: dừng WAV, dừng video, **chờ `AVAssetWriter.finishWriting` xong** rồi mới gửi.
5. Gửi theo 7.6. Server nhận xong thì xóa hai file tạm.

### 8.5 Video

- `AVAssetWriter`: H.264, khoảng 720 × 1280, 30 fps, bitrate khoảng 3 Mbps, **không có tiếng** (tiếng đi riêng trong WAV).
- Ghi từ chính các `CMSampleBuffer` của `AVCaptureVideoDataOutput` (không dùng `AVCaptureMovieFileOutput`).
- `expectsMediaDataInRealTime = true`; bắt đầu bằng `startSession(atSourceTime:)` với PTS khung đầu.
- **Hướng video:** dọc, **không lật gương** (`connection.isVideoMirrored = false` cho output ghi). Preview trên màn có thể lật cho tự nhiên, nhưng file gửi server thì không.
- Mỗi khung ghi vào `frame_times`: `capture_time` = PTS (ms), `presented_frames` = số thứ tự khung, `media_time` = (PTS − t0) giây.

---

## 9. Các task, từng bước

Ước lượng tính bằng ngày công khi làm cùng AI. Mỗi task một nhánh `feat/IOS-0x-…`, commit có mã task, ví dụ `feat(ios): Vision face tracker [IOS-04]`.

### IOS-01 · Khung app và toàn bộ màn (2 ngày)

**Làm:**
1. Tạo project theo mục 5.
2. `UI/Theme.swift`: màu lấy đúng mã hex trong `apps/android/app/src/main/java/vn/vericlue/app/ui/theme/Theme.kt` (sáng và tối); font Be Vietnam Pro; cỡ chữ theo `VcType`.
3. `UI/Components/`: port từng component ở `ui/components/` (thanh trên, thanh tiến độ 3 bước, nút chính, nút phụ, banner, bàn phím số, ô OTP, thẻ danh sách, khung camera).
4. `Flow/Routes.swift`: enum `Route` với đủ các route sau, tên giữ nguyên như Android:
   `bank_start, bank_opened, gallery, splash, auth, terms, consent, intro, permission, phone, otp, otp_error, id_front, id_front_glare, id_front_review, id_back, id_back_review, confirm, edit_info, face_ready, framing, hold_still, turn_head, voice, voice_again, uploading, upload_failed, checking, slow, success, review, retry_quality, retry_challenge, error_camera, error_mic, error_network, error_session, error_service, error_device, interrupted, no_voice, exit_confirm, stopped, flash_skipped`.
   Thêm 2 route mới cho API của #49: `deny`, `recovery_required`.
5. `UI/Screens/*`: vẽ từng màn theo Figma (https://www.figma.com/design/kKEiRjXMCNDPVeupHsUn1H) và theo màn Android cùng tên. Câu chữ **chép nguyên** từ code Android.
6. `UI/AppNavigation.swift`: `NavigationStack` với `path: [Route]`; hàm `go(_:)` (không thêm trùng route đang ở đỉnh), `back()`, `toBank()`.
7. **Chế độ demo** (`DemoFlow.swift`): giống `FlowState` + `DemoOutcome` của Android. Chưa gọi server; màn "Đang kiểm tra" tự chạy rồi ra kết quả theo lựa chọn.
8. Màn **"Xem tất cả màn"** (chỉ `#if DEBUG`): danh sách mọi màn và các công tắc "Giả lập / API thật", kịch bản mock, `purpose`. Mở từ màn ngân hàng mẫu.

**Xong khi:** chạy trên Simulator, đi được hết luồng demo của cả 3 `purpose`; mở được từng màn từ "Xem tất cả màn"; so với Figma không lệch rõ.

### IOS-02 · Client API và luật luồng (1,5 ngày)

**Làm:**
1. `Data/Models.swift`: struct `Codable` cho mọi def ở mục 7. Dùng `CodingKeys` snake_case, hoặc `JSONDecoder.keyDecodingStrategy = .convertFromSnakeCase`. Trường nào có thể thiếu thì để optional.
2. `Data/SessionApi.swift` dùng `URLSession` + `async/await`:
   - mỗi lệnh ở mục 7 là một hàm `async`, trả `Result<T, ApiError>`;
   - `enum ApiError { network, unauthorized, conflict(code: String?), expired, busy, badResponse, server }`;
   - map mã HTTP giống `SessionApi.errorFor` của Android;
   - multipart: tự viết hàm `MultipartBody` (boundary ngẫu nhiên, mỗi phần có `Content-Disposition` và `Content-Type`);
   - timeout: kết nối 15 s, đọc/ghi 60 s.
3. `Flow/LiveFlow.swift`: class `@MainActor` giữ `session`, `token`, `challenge`, `frontalJpeg`, `colorEvents`, `mediaAcked`, `signalsAcked`, `voicePrompt`, `voiceChallengeId`, `pendingWav`, `voiceChecked`, `otpSms`, `idFields`. Port **đúng hành vi** từng hàm Android:
   - `createSession(purpose:scenario:)` (thay `ensureSession`);
   - `sendOtp`, `verifyOtp`, `sendIdCard`, `confirmIdCard`;
   - `prepareFace()`: nếu phiên vừa tạo thì giữ challenge; còn lại gọi `/challenge`, thay token và challenge, xóa dữ liệu lượt cũ;
   - `submitFace(…)`: gửi media (nếu `!mediaAcked`) → signals (nếu `!signalsAcked`) → finalize; 409 `step_already_received` khi gửi lại thì coi là đã nhận; `retry` thì thay challenge và đặt lại hai cờ;
   - `submitVoice(wav:video:audioOffsetMs:)`: giữ `pendingWav` tới khi server nhận.
4. `Flow/FlowRules.swift`: `routeForStatus`, `retryHintText`, `otpWrongText`, `otpErrorText`, `confirmedFields`, `isoToDisplay` / `displayToIso`, `checkedByServer`, `afterNetworkRetry`, `resumeRedoesFace`.
5. **Test** (`VeriClueTests/`):
   - `MockURLProtocol` trả JSON có sẵn theo từng path;
   - port mọi test trong `LiveFlowTest.kt`, `LiveFlowRetryTest.kt`, `LiveFlowStageATest.kt`, `FlowRulesTest.kt`;
   - thêm test: với mọi trạng thái khác `pass` sau lỗi mạng + thử lại, không bao giờ ra `success`;
   - `ContractTests`: đọc từng file `packages/contracts/examples/session.*.json`, giải mã được vào model tương ứng (copy các file ví dụ vào target test, **đừng sửa**).

**Xong khi:** `⌘U` xanh hết; không có test nào gọi mạng thật.

### IOS-03 · Bước A thật: OTP, CCCD (1,5 ngày)

**Làm:**
1. Màn số điện thoại: bấm "Gửi mã" → `createSession(purpose:)` → `sendOtp`. Chỉ cho bấm khi số hợp lệ (`PhoneRules` của Android). Chặn bấm hai lần trong lúc chờ.
2. Màn OTP: hiện `otpSms`; 6 ô; bấm "Xác nhận" → `verifyOtp`; xử lý theo bảng 7.2; nút "Gửi lại mã" bật sau 45 giây.
3. `Capture/CameraSession.swift` (phần camera sau): mở camera sau, preview trong khung tỉ lệ thẻ 1,586:1, nút chụp.
4. `Capture/IdCard.swift`:
   - **Độ nét:** chuyển ảnh xám, chạy Laplacian (vImage), tính phương sai. Ngưỡng ban đầu lấy từ `IdCard.kt`, chỉnh lại theo số đo trên iPhone.
   - **Lóa:** tỉ lệ điểm ảnh gần trắng (luma ≥250) trong vùng thẻ; chặn khi tỉ lệ >0.02, theo `IdCard.kt` Android. Đây là ngưỡng khởi đầu, chưa hiệu chỉnh bằng tập đo iPhone.
   - **QR:** `VNDetectBarcodesRequest`, `symbologies = [.qr]`, lấy `payloadStringValue`.
5. Màn xem lại: hiện ảnh vừa chụp và 3 dòng kiểm (nét / không lóa / đọc được QR, riêng mặt sau), câu nhắc đúng lỗi.
6. Mặt sau "Ảnh rõ, tiếp tục" → `sendIdCard(front:back:qr:)`; `retry` → về chụp mặt sau; `ok` → màn Kiểm tra thông tin với dữ liệu server.
7. Màn Kiểm tra thông tin → "Thông tin đúng" → `confirmIdCard(fields của server)`; "Sửa thông tin" → màn sửa → "Lưu và tiếp tục" → `confirmIdCard(confirmedFields(…))`.

**Xong khi:** trên iPhone với server mock: OTP sai rồi đúng chạy đúng; chụp một thẻ **in thử từ dữ liệu bịa** (đừng dùng thẻ thật trong ảnh commit) → server nhận 2 ảnh, trả thông tin từ QR.

### IOS-04 · Camera trước và phần khuôn mặt (3 ngày, khó nhất)

**Làm, theo thứ tự (thử trên iPhone sau mỗi bước):**
1. `CameraSession.swift` (camera trước):
   - **một** `AVCaptureSession` cho cả luồng;
   - `sessionPreset = .hd1280x720`;
   - `AVCaptureVideoDataOutput` (BGRA, `alwaysDiscardsLateVideoFrames = true`) chạy trên một hàng đợi riêng;
   - preview bằng `AVCaptureVideoPreviewLayer` bọc trong `UIViewRepresentable`, **dùng chung một layer** cho mọi màn;
   - trong màn chạy lịch phần mặt, **chỉ một ô preview cố định** (góc trên phải, khoảng 96 × 128 pt) suốt cả 4 pha. Không đổi chỗ, không tạo preview mới giữa các pha: Android đã bị hủy đoạn quay vì chuyện này.
2. `FaceTracker.swift`:
   - mỗi khung (hoặc cách 1 khung) chạy `VNDetectFaceRectanglesRequest` (revision 3);
   - lấy `boundingBox`, `yaw`, `roll`, `pitch` (iOS 15+);
   - phát ra `FaceSignal { box, yaw (độ), brightness }`.
3. `QualityGate.swift`: port `QualityGate.evaluate` (thiếu sáng / xa / lệch / đạt). Giữ "đạt" 1 giây thì tự chuyển sang phần ghi. Màn căn mặt hiện **một** câu nhắc tương ứng.
4. `VideoWriter.swift` theo mục 8.5; hàm `start(url:)`, `append(sampleBuffer)`, `finish() async -> URL?`; ghi lại PTS khung đầu (`t0`).
5. Màn "Giữ yên" chạy lịch mục 8.1 bằng `CADisplayLink`:
   - đổi màu nền **toàn màn hình**;
   - `UIScreen.main.brightness = 1.0` trong lúc chạy, trả lại độ sáng cũ khi xong;
   - `UIApplication.shared.isIdleTimerDisabled = true`;
   - ghi `color_events`;
   - chụp JPEG tại `frontal_capture_at_ms` (lấy khung camera gần nhất, xoay đúng chiều, nén chất lượng 0,9).
6. Khóa và mở AE/AWB:
   - `device.lockForConfiguration()`; `exposureMode = .locked`; `whiteBalanceMode = .locked`; `unlockForConfiguration()`;
   - mở lại bằng `.continuousAutoExposure` và `.continuousAutoWhiteBalance`;
   - ghi vào `client_quality.ae_awb_locked` là có khóa được hay không.
7. Chấm sáng theo mục 8.3.
8. Quay đầu theo mục 8.1:
   - mũi tên và chữ theo `head_turns`;
   - **trái/phải là theo người dùng**: "Quay sang trái" nghĩa là người dùng quay về phía tay trái của họ;
   - dùng `yaw` của Vision để hiện vòng tiến độ khi đã quay đủ (khoảng 25°), nhưng **không** tự chuyển bước sớm: lịch do server định;
   - kiểm dấu `yaw` trên máy thật và ghi vào bàn giao.
9. `CamProbe.swift`:
   - `ios:simulator`: `#if targetEnvironment(simulator)`;
   - `ios:jailbreak`: tồn tại một trong `/Applications/Cydia.app`, `/bin/bash`, `/usr/sbin/sshd`, `/etc/apt`, hoặc ghi được ra `/private/jb_test`;
   - `ios:debugger`: `sysctl` với `KERN_PROC_PID`, kiểm cờ `P_TRACED`. Chỉ bật ở Release; Debug luôn có debugger nên **bỏ cờ này ở Debug**, ghi chú vào `client_quality`;
   - `device_label`: `UIDevice.current.model` + mã máy (`utsname.machine`);
   - `duplicate_frame_ratio`: tỉ lệ khung trùng hệt khung trước (so hash nhỏ của ảnh thu nhỏ), như `DuplicateFrameMeter` của Android.
10. `Regions.swift`: đủ 5 vùng da + nền theo tỉ lệ hộp mặt, như `Regions.kt` (bắt buộc theo yêu cầu Cổng 5; không cắt).
11. Hết pha quay đầu: `finish()` video (chờ xong) → màn "Đang gửi" → `submitFace`. Kết quả `voice_challenge` → màn Đọc câu với `voice_prompt`; `retry`, `review`, `deny` hay lỗi → màn tương ứng (bảng 7.5).

**Xong khi:** trên iPhone, kịch bản `genuine`: server nhận JPEG, MP4 (mở được bằng QuickTime, không lật, dài khoảng 19 giây), `color_events` 8 phần tử, `frame_times` khoảng 30 khung/giây; `low_quality` ra "Chụp lại" với câu nhắc, lượt sau dùng challenge mới.

### IOS-05 · Đọc câu (1 ngày)

**Làm:**
1. `WavRecorder.swift`:
   - `AVAudioSession` category `.playAndRecord`, mode `.measurement`;
   - `AVAudioEngine.inputNode` → `AVAudioConverter` sang 16 kHz, mono, Int16;
   - gom PCM rồi tự ghi header WAV 44 byte như `Wav.encode` của Android;
   - phát mức âm (RMS) cho sóng âm trên màn;
   - tối đa 8 giây.
2. Màn Đọc câu theo mục 8.4. Hiện câu trong khung, nút micro tròn, sóng âm khi đang ghi.
3. WAV rỗng (người dùng không nói) → màn "Chưa thu được giọng nói".
4. `voice_challenge` lần hai → màn "Hãy đọc lại" với câu mới.

**Xong khi:** `voice_clone` → đọc câu → "Hồ sơ đang được xác minh thêm"; server lưu `voice_audio.wav` và `voice_video.mp4`; ghi vào bàn giao độ dài WAV, độ dài MP4 và `audio_offset_ms` của 3 lần thử.

### IOS-06 · Gián đoạn, mất mạng, dọn file (1 ngày)

**Làm:**
1. Theo dõi `scenePhase`: sang `.background` khi đang ở `framing`, `hold_still`, `turn_head`, `voice`, `voice_again` thì dừng video và ghi âm, xóa file tạm, sang màn "Xác minh bị gián đoạn". "Quay lại chuẩn bị" → `face_ready`, lượt sau gọi `/challenge`.
2. Lỗi mạng ở bất kỳ bước gửi nào → "Không kết nối được" → "Thử lại" gửi lại **chỉ phần chưa được nhận**, không bao giờ đi tắt ra kết quả.
3. Nút thoát giữa chừng → hộp thoại "Bạn muốn dừng xác minh?": ở phần mặt hoặc giọng thì "Quay lại chuẩn bị"; ở chỗ khác thì "Tiếp tục".
4. Xóa file thu do app sở hữu khi server đã nhận, khi rời luồng hoặc bị gián đoạn.
   IOS-06 đặt MP4 trong `tmp/vericlue-capture/` với tên face/voice + UUID; WAV ở RAM.
   Lúc mở app dọn orphan trong namespace và file legacy `vericlue-face/voice-<UUID>`;
   không xóa rộng mọi WAV/MP4 hoặc file do người dùng xuất sang Files/Photos.
5. Màn thành công: chỉ tích những gì server đã kiểm ("Khuôn mặt", và "Giọng nói" nếu đã gửi giọng).

**Xong khi:** đủ các mục ở checklist 13.1 liên quan.

### IOS-07 · Release, đo đạc, bàn giao (1 ngày)

**Làm:**
1. Scheme Release với `API_BASE_URL` HTTPS (cloudflared, chờ địa chỉ). Bỏ `NSAllowsLocalNetworking` ở Release.
2. Ẩn hết nút debug và màn "Xem tất cả màn" bằng `#if DEBUG`.
3. Đo trên iPhone và ghi vào bàn giao:
   - fps thật;
   - dung lượng MP4 phần mặt và phần giọng;
   - thời gian gửi trên Wi-Fi và trên 4G;
   - `audio_offset_ms`;
   - dấu `yaw` khi quay trái/phải;
   - độ chênh giữa PTS camera và `CACurrentMediaTime`.
4. Viết `apps/ios/README.md`: cách cài, chạy server, đổi IP, chạy test, cài lên iPhone.
5. Ghi bàn giao: `uv run python scripts/new_handoff.py --task IOS-07 --who "Lý Anh Quân+<AI>"`.

**Tổng ước lượng: khoảng 11 ngày công.** Thứ tự: IOS-01 → 02 → 03 → 04 → 05 → 06 → 07. IOS-01 và IOS-02 làm song song được (hai phiên AI, khác file). IOS-04 bắt đầu được ngay khi xong IOS-02, không cần chờ IOS-03.

---

## 10. Câu chữ hiển thị

**Lấy nguyên từ code Android**, không tự viết lại:
- câu nhắc chất lượng: `FlowRules.retryHintText` (`MORE_LIGHT` → "Ra chỗ sáng hơn", `MOVE_CLOSER` → "Lại gần hơn", …);
- màn lỗi và gián đoạn: `object Messages` trong `ui/screens/VoiceResultScreens.kt`;
- màn bước A: `ui/screens/IdentityScreens.kt`;
- màn khuôn mặt: `ui/screens/FaceScreens.kt`.

Chữ cho 2 route mới:
- `deny`: tiêu đề "Xác thực không thành công", nội dung "Vui lòng thử lại sau.", nút "Quay lại ứng dụng ngân hàng".
- `recovery_required`: tiêu đề "Cần xác minh lại đầy đủ", nội dung "Thiết bị này chưa được liên kết. Hãy làm theo hướng dẫn khôi phục tài khoản trong ứng dụng ngân hàng.", nút "Quay lại ứng dụng ngân hàng".

**Chữ cấm** (test `CitizenCopyTests` kiểm trong toàn bộ chuỗi hiển thị): "giả mạo", "deepfake", "điểm", "score", "AI phát hiện", "gian lận".

---

## 11. Xử lý lỗi và trạng thái

- Mỗi lệnh gọi API trả `Result`. Không dùng `try!` hay `fatalError` trên dữ liệu từ server.
- Bảng điều hướng theo mã: mục 7.5, 7.6, 7.7.
- **Thử lại** chỉ ở lỗi mạng; lỗi 4xx/5xx khác thì ra màn lỗi, không tự thử lại.
- Thiếu camera hoặc micro, người dùng từ chối quyền → màn "Chưa cho camera" / "Chưa cho micro", có nút mở Cài đặt (`UIApplication.openSettingsURLString`).
- Camera không mở được → màn "Thiết bị chưa đáp ứng". **Không để app văng.**

---

## 12. Những bẫy đã gặp ở Android

1. **Camera bật liên tục** từ căn mặt tới hết đọc câu (ADR-0013 nguyên tắc 4): một `AVCaptureSession`, đổi màn không dựng lại session.
2. **Dựng lại hoặc đổi chỗ preview giữa lúc quay sẽ hỏng đoạn quay** (Android: camera bị cấu hình lại, mất video ở giây thứ 7, lúc chuyển từ màu sang chấm): một ô preview cố định cho cả lịch phần mặt; sau khi chuyển màn đợi khoảng 600 ms rồi mới bắt đầu ghi.
3. **Video phải chạy liên tục** qua cả màu, chấm, quay đầu: chỉ dừng khi hết quay đầu.
4. **Chờ ghi file xong** (`finishWriting`) rồi mới gửi; gửi file đang ghi dở thì server không đọc được.
5. **Gửi lại sau lỗi mạng** dễ bị 409: nhớ bước nào đã nhận (mục 9, IOS-02, bước 3).
6. **Không tự chọn** thứ tự quay đầu hay đường chấm: luôn theo gói của server. Thiếu `dynamic` ở luồng cần có → màn lỗi dịch vụ.
7. **Lật gương:** preview thì lật, file gửi đi thì không, tọa độ chấm cũng không lật.
8. **Máy ảo/Simulator** luôn bị cờ `camprobe` nên không đạt; demo trên iPhone thật.
9. **HTTP thường** chỉ cho Debug trong LAN; Release chỉ HTTPS.
10. **Độ sáng màn hình** phải trả lại như cũ khi xong hoặc bị gián đoạn.
11. **Không tin** kết quả do app tự tính (QR, góc quay…) là phán quyết: chỉ dùng để hướng dẫn người dùng. Server quyết.

---

## 13. Kiểm tra cuối và bàn giao

### 13.1 Checklist trên iPhone thật với server mock

- [ ] `genuine`, onboarding: đi hết luồng → đọc câu → "Xác minh thành công", chỉ tích phần server đã kiểm.
- [ ] `low_quality`: "Chụp lại" với câu nhắc và "Còn N lần chụp lại" lấy từ server; lượt sau dùng challenge mới.
- [ ] `voice_clone`: đọc câu → "Hồ sơ đang được xác minh thêm".
- [ ] Tắt Wi-Fi lúc gửi → "Không kết nối được"; "Thử lại" khi vẫn mất mạng → vẫn báo lỗi; bật lại → đi tiếp đúng.
- [ ] Vuốt về màn hình chính lúc đang quay → "Xác minh bị gián đoạn"; làm lại thì app gọi `/challenge`.
- [ ] OTP sai → "Mã chưa đúng. Bạn còn N lần thử."; đúng → sang CCCD.
- [ ] CCCD: QR không đọc được → quay lại chụp mặt sau; sửa họ tên → server ghi chú cho ca duyệt.
- [ ] `reauth`: quay thụ động → màn `recovery_required`.
- [ ] Video gửi lên mở được, đúng chiều, không lật, dài đúng lịch.
- [ ] Không màn nào có chữ cấm; test `⌘U` xanh.
- [ ] Không commit ảnh, video, âm thanh, khóa ký.

### 13.2 Bàn giao

Sau mỗi phiên làm việc, ghi bàn giao (`scripts/new_handoff.py`), gồm: đã xong gì, đang dở gì (file:dòng), số đo thật, câu hỏi cho nhóm. Mở PR theo `.github/PULL_REQUEST_TEMPLATE.md`, mỗi task một PR.

---

## 14. Nếu không kịp thì cắt gì (theo thứ tự)

**Cập nhật yêu cầu Cổng 5:** sếp yêu cầu làm đủ IOS-04; `region_means` và full
`camprobe` là bắt buộc, không áp dụng hai phương án cắt trước đây cho task này.

3. CCCD thật: dùng thông tin mẫu ở chế độ demo, giữ OTP.
4. Luồng `recovery`.
5. **Tối thiểu để demo:** IOS-01, IOS-02, IOS-04 (đủ bước 9, 10 theo yêu cầu mới), IOS-05.

Bản dự phòng cuối cùng trên iPhone: mở web `/verify` bằng Safari.

---

## 15. Câu lệnh mẫu cho AI

Mở Claude Code ở thư mục gốc repo. Mỗi phiên làm **một task**. Câu mở đầu:

> Đọc `AGENTS.md`, rồi `apps/ios/docs/plan-ios.md` (mục 2, 7, 8 và task IOS-0x). Làm task IOS-0x đúng các bước ghi trong file. App Android ở `apps/android/` là đặc tả hành vi và câu chữ: port sang Swift, giữ nguyên tên hàm, tên route, câu tiếng Việt. Không sửa `packages/contracts/`. Chỗ nào file kế hoạch và Android đều không nói tới thì dừng lại hỏi tôi, đừng tự nghĩ.

Ví dụ cụ thể cho IOS-02:

> Port `apps/android/app/src/main/java/vn/vericlue/app/flow/LiveFlow.kt` sang `apps/ios/VeriClue/Flow/LiveFlow.swift` theo mục 7 của plan (API có `purpose`, `challenge_id`, `voice_challenge_id`, token mới sau `/challenge`). Port luôn `LiveFlowRetryTest.kt` sang XCTest dùng `MockURLProtocol`. Chạy `xcodebuild test -scheme VeriClue -destination 'platform=iOS Simulator,name=iPhone 15'` và sửa tới khi xanh.

**Nếu dùng Codex** (CLI hoặc app Codex trên Mac):
- Mở Codex ở **thư mục gốc repo**, không mở ở `apps/ios/`. Codex tự đọc `AGENTS.md` ở gốc, nên luật dự án có hiệu lực ngay; câu mở đầu ở trên vẫn dùng nguyên được.
- Cho Codex quyền chạy lệnh trong repo để nó tự build và test bằng `xcodebuild`, ví dụ `xcodebuild test -scheme VeriClue -destination 'platform=iOS Simulator,name=iPhone 15'`. Codex không bấm được giao diện Xcode, cũng không chạy được trên iPhone: phần đó anh tự bấm Run.
- Tạo project Xcode (mục 5) thì anh tự làm bằng giao diện Xcode trước, rồi mới giao Codex viết code. Đừng để Codex tự sinh file `.xcodeproj` bằng tay.
- Mỗi task một phiên Codex mới, mở đầu bằng câu ở trên và mã task. Phiên dài quá thì ghi bàn giao (`scripts/new_handoff.py`) rồi mở phiên mới.
- Codex hay "sửa cho chạy được" bằng cách nới điều kiện hoặc bỏ qua lỗi. Dặn rõ: **không** sửa test cho xanh bằng cách bỏ kiểm tra; không đổi `packages/contracts/`.
- Trước khi mở PR, nhờ Claude (hoặc một phiên Codex khác) rà lại theo `AGENTS.md` §6 và §8, như nhóm đang làm với Android.

**Mẹo:**
- Phần camera (IOS-04): sau mỗi bước, cắm iPhone chạy thử ngay, vì AI không chạy camera được.
- Gặp lỗi hợp đồng (422, 409 lạ): mở `http://<mac>:8000/docs`, gửi tay đúng dữ liệu để xem server mong gì, rồi mới sửa app.
- Đừng để AI "làm cho nhanh" bằng cách bỏ qua lỗi hay ép ra thành công: vi phạm luật 2.

---

## 16. Đã chốt (24/10)

Trưởng nhóm đồng ý chốt theo đề xuất, có lỗi thì sửa sau. Ghi ở ADR-0014 (mục "Cập nhật 24/10") và `docs/plan/backlog.md`.

| # | Câu hỏi | Đã chốt |
|---|---|---|
| 1 | Sửa ADR-0014 (đang ghi "iOS không làm") | Ghi: có thêm app iOS (SwiftUI, Vision), người làm Lý Anh Quân; Android vẫn là bản nộp chính |
| 2 | Thêm IOS-01..07 vào `docs/plan/backlog.md` và task card | Đã thêm: người làm Lý Anh Quân, sprint S2, ưu tiên P1 (bản phụ); task card ở `docs/plan/epics/E9-app-flows.md` |
| 3 | Mua Apple Developer Program (99 USD/năm) để cài qua TestFlight | Không mua cho vòng 2: demo bằng iPhone của nhóm, cài qua cáp |
| 4 | Bundle ID, tên app | `vn.vericlue.app`, "VeriClue", giống Android |
| 5 | iOS dùng Vision, Android dùng ML Kit | Chấp nhận: cả hai chỉ để hướng dẫn, không ra phán quyết |
| 6 | Địa chỉ cloudflared cho bản Release | Dùng chung với Android |
