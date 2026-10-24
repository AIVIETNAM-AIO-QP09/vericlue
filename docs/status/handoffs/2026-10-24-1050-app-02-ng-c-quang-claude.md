# Bàn giao · APP-02 (+ APP-01) · Ngọc Quang+Claude · 2026-10-24 10:50

**Nhánh:** `feat/APP-02-camera-mic-scaffold` (gồm cả `feat/APP-01-android-ui`; mở một PR vào `main`)
**Trạng thái task sau phiên này:** doing (đã sửa theo kết quả duyệt của trưởng nhóm, chờ duyệt PR)

## Đã xong
Sửa theo kết quả duyệt của trưởng nhóm ngày 24/10.

**Lỗi chặn.** Ở chế độ API thật, "Thử lại" và "Tiếp tục chờ" không còn đi qua `DemoOutcome`.
- `ErrorNetwork` → "Thử lại" và `Slow` → "Tiếp tục chờ" giờ về `Routes.Uploading` (`FlowRules.afterNetworkRetry`).
- `CheckingScreen(auto = !flow.live)`. Ở chế độ thật, nếu lỡ vào `Checking` thì app chuyển ngay sang `Uploading`.
- `LiveFlow` nhớ `mediaAcked` và `signalsAcked`, nên khi thử lại chỉ gửi bước server chưa nhận.
  - Gửi lại mà bị 409 thì coi là đã nhận, trừ khi mã lỗi là `session_closed`.
  - `finalize` bị 409 thì ra màn lỗi, không bao giờ ra thành công.
  - Khi `finalize` trả `retry`, cờ đã nhận được đặt lại.
- `pendingWav` chỉ bị xóa khi server đã nhận giọng, nên thử lại vẫn còn file để gửi.
- Test mới `LiveFlowRetryTest` (9 test): lỗi mạng ở từng bước, 409 khi gửi lại, `session_closed`, giọng. Có một test chạy mọi tổ hợp điểm lỗi × trạng thái khác `pass`: không tổ hợp nào ra Success.

**Nên sửa.**
- `app/build.gradle.kts`: task `checkReleaseApiUrl` gắn vào `preReleaseBuild`. Bản release dừng nếu `apiBaseUrl` không bắt đầu bằng `https://`.
- `CameraSession.deleteVideo()` xóa mọi `face_*.mp4` trong `cacheDir`. Được gọi khi:
  - server đã nhận media;
  - `leave()`;
  - bị gián đoạn (`ON_STOP`);
  - "Tiếp tục" ở hộp thoại thoát giữa giai đoạn B/C.
- `SuccessScreen(checked = …)`: chế độ thật chỉ tích "Khuôn mặt", cộng "Giọng nói" nếu server đã nhận giọng (`FlowRules.checkedByServer`). Không còn tích "Ảnh giấy tờ", vì CCCD chưa gửi server.
- "Bỏ qua nháy màu": tắt camera và chuyển sang màn riêng `FlashSkipped` ("Cần xác minh theo cách khác", mời liên hệ ngân hàng), không còn nhảy sang đọc câu. Màn này không hứa nhân viên duyệt, vì chưa gửi gì lên server. Câu hỏi 14 trong `apps/android/docs/can-chot.md`.
- `backlog.md`: APP-02/03/04 vẫn để `doing`, đã bỏ tên "Lý Anh Quân" cho tới khi trưởng nhóm chốt.

**Nhỏ.**
- Sửa comment `CameraSession.kt` và `README.md` (`region_means`, `camprobe` đã làm). README thêm cách build release có https.
- Bàn giao 2026-10-24-0010: số test 30 → 40.
- `third_party/README.md`: thêm Gradle Wrapper 8.11.1 (Apache-2.0).
- `ExitConfirm` → "Tiếp tục": chỉ bỏ lượt mặt khi màn trước thuộc giai đoạn B/C (`FlowRules.resumeRedoesFace`). Ở màn khác thì chỉ quay lại màn trước.

**Sau khi subagent `reviewer` rà.**
- Video được xóa ngay khi server nhận media, nhờ `submitFace(onMediaAcked = …)`. Trước đây file còn sót lại khi `finalize` trả `retry`.
- "Dừng xác minh" tắt quay, xóa video và dừng ghi âm ngay lúc bấm.
- Hộp thoại thoát ghi "Tiếp tục" khi không làm lại phần mặt.
- "Thử lại" và "Tiếp tục chờ" bỏ màn lỗi khỏi back stack.

**Cập nhật 11:20: video lúc đọc câu (VOICE-05), kiểm trên máy ảo.**
- Ở chế độ API thật, app quay MP4 lúc đọc câu (`CameraSession.startRecording(voice = true)`, file `voice_*.mp4`) và gửi kèm WAV ở `/voice` (`LiveFlow.submitVoice(wav, video, onAccepted)`). Phần quay này không đụng tới `frame_times`/`region_means` của phần mặt.
- WAV chỉ bắt đầu khi video đã có khung hình đầu (`awaitRecordingStarted`). Trước khi gửi, app chờ CameraX ghi xong file (`finishedVideo`). Server nhận xong thì app xóa video.
- Bấm dừng trước khi mic kịp bắt đầu thì việc khởi động bị hủy, không có bản ghi thừa.
- Test mới `voiceSendsTheReadingVideoNextToTheWav`.

**Cập nhật 12:10: trưởng nhóm duyệt miệng mọi đề xuất trong `can-chot.md`** (Quang chuyển lời).
- Cột "Trả lời" đã điền đủ 17 câu.
- Câu 11: Quang quyết không chia việc cho anh Lý; backlog APP-02/03/04 ghi "Ngọc Quang+Claude".
- Câu 6, 7: đã sửa ADR-0017 §3 (WebM trên web, MP4 trên app) và ADR-0014 mục 2, 3 (ML Kit).
- Câu 8, 16: mở PR `[contract]` #47 (nhánh `feat/APP-contract-clock-voice-offset`, tách từ `main`):
  - `/voice` nhận `audio_offset_ms`;
  - sửa mô tả đồng hồ trong `session.schema.json`;
  - sinh lại `openapi.json`, thêm 3 test API.
- App gửi `audio_offset_ms`: lấy độ dài video CameraX đã báo ở sự kiện `Status` gần nhất, cộng thời gian từ sự kiện đó tới lúc WAV bắt đầu (`CameraSession.videoElapsedMs`). Chưa kiểm giá trị này trên máy ảo, vì server mock đang chạy là bản cũ, chưa có trường này.
- Câu 3 (M5, LIVE-01), 4 (FLOW-02 của M2, FLOW-03 của M1), 10 (PRES-02), 17 (REV-02) là việc của task khác; câu 5 duyệt nhưng chưa chọn cách. Xem "Câu hỏi cho nhóm".

**Cập nhật 13:20: câu 3, 4, 18–26 đã duyệt; làm cả server lẫn app.**
- Server và hợp đồng nằm ở PR #47 (nhánh `feat/APP-contract-clock-voice-offset`), đã merge vào nhánh này cho khớp hợp đồng:
  - gói thử thách LIVE-01 (`turn_order`, `dot_path`, `dot_events`);
  - OTP mô phỏng;
  - CCCD (`id-card`, `id-card/confirm`);
  - `POST /challenge` (thử thách mới, gia hạn phiên tối đa 15 phút).
- App, chế độ API thật:
  - **Phiên bắt đầu ở màn số điện thoại.** OTP hiện tin nhắn mô phỏng từ server. Mã sai hiện "Mã chưa đúng. Bạn còn N lần thử."; hết hạn hoặc bị khóa thì nhắc bấm "Gửi lại mã".
  - **CCCD:** gửi 2 ảnh và chuỗi QR ở màn xem lại mặt sau. Server trả `retry` thì quay lại chụp mặt sau. Thông tin xác nhận lấy theo server; sửa thì chỉ gửi trường đã sửa (`FlowRules.confirmedFields`).
  - **Trước mỗi lượt quay mặt** gọi `LiveFlow.prepareFace`: tạo phiên mới nếu chưa có, còn lại thì gọi `POST /challenge`. Gián đoạn hay thoát giữa chừng giờ giữ phiên, không tạo phiên mới.
  - **Chấm sáng** chạy theo `dot_path`, ghi `dot_events`. Video quay tiếp tới hết đoạn chấm sáng (cho LIVE-02).
  - **Thứ tự quay đầu** lấy từ `turn_order`.
- Test: 61 test JVM (thêm `LiveFlowStageATest`, 8 test).
- **Kế hoạch app iOS** cho anh Lý: đã soạn, chờ Quang duyệt, chưa đưa vào repo.

**Cập nhật 14:00: sửa theo reviewer trước khi merge #46, #47** (trưởng nhóm cho tự merge).
- **Bịt đường né bước đọc câu:** `voice_owed` giữ yêu cầu đọc câu qua mọi lần `POST /challenge`. Lượt mặt nào bỏ dở sau khi đã chấm (không phải retry) tính là một lần chụp lại, và kết quả của lượt cũ bị xóa.
- **Số CCCD** chỉ lưu dạng HMAC. Họ tên, ngày sinh, địa chỉ vẫn lưu rõ để nhân viên duyệt so; ghi thành giới hạn, SEC-01 xử lý.
- **OTP** gửi tối đa 3 lần mỗi phiên (409 `otp_too_many`).
- **App:** thử thách thiếu `turn_order` thì ra màn lỗi dịch vụ, không tự chọn thứ tự.
- **Backlog:** nhận LIVE-06 (phần gia hạn và làm lại phần mặt).
- **Còn lại (ghi cho SEC-01/PLAT-06):** bớt số lần thử OTP chưa khóa hàng nên gửi song song có thể thử quá 5 lần; `ID_HMAC_KEY` mặc định chưa bị chặn khi chạy mô hình thật; `simulated_sms` chưa có công tắc tắt.

## Đang dở
- Chưa thử trên điện thoại thật.
- Thứ tự quay đầu vẫn chọn trên máy; đường chấm sáng chưa ghi. Cả hai chờ hợp đồng LIVE-01.
- Chưa gửi ảnh góc 2/3. Chưa tải lên dần. Chưa có HTTPS qua cloudflared.
- CCCD và OTP chưa gửi server (FLOW-02, FLOW-03).
- "Bỏ qua nháy màu" chưa tạo ca duyệt trên server (câu 14).

## Bước tiếp theo
1. Trưởng nhóm duyệt PR gộp APP-01 + APP-02 vào `main`.
2. Trưởng nhóm trả lời `apps/android/docs/can-chot.md`, cột "Trả lời", câu 3–15.
3. Thử trên máy thật theo giai đoạn 9 của `docs/plan-camera-mic.md`. Build release bằng `-Pvericlue.apiBaseUrl=https://<cloudflared>/`.

## Quyết định, lưu ý, bẫy
- **API chưa có `GET` trạng thái phiên.** Nếu `finalize` mất phản hồi, lần thử lại sẽ bị 409 và ra màn lỗi dịch vụ. Cách này an toàn (không bao giờ ra đạt) nhưng người dùng phải làm lại.
- **Chống phát lại 409 theo bước (PLAT-06) chưa cài trên server.** App đã sẵn sàng: gửi lại mà bị 409 thì coi là đã nhận.
- Gợi ý của reviewer, chưa làm:
  - `voiceChecked` giữ cho cả phiên. Nếu bước giọng trả `retry` rồi lượt mặt sau `pass`, màn thành công vẫn tích "Giọng nói".
  - Thoát từ màn chụp lại sẽ tạo phiên mới, nên `attempts_left` bị làm mới. Server cần giới hạn số lần (LIVE-06/SEC).
  - Gallery (chỉ có ở bản debug) đi thẳng tới Success.
  - Quay lại `Uploading` từ hộp thoại thoát sẽ gửi lại. Nếu `finalize` đang dở thì nhận 409 và ra lỗi: an toàn, nhưng mất một lượt.
- OkHttp mặc định tự gửi lại khi lỗi kết nối. Riêng test tắt tính năng này để thấy đúng lỗi mạng.
- Tiêu chí "Build được APK trên máy Windows" (E9, APP-01) vẫn giữ dấu tích, vì đã build thật trên máy này (xem phần Test đã chạy). Câu 15 trong `can-chot.md` để trưởng nhóm xác nhận.

## Câu hỏi cho nhóm
- Câu 5: duyệt "chốt một cách" nhưng chưa nói cách nào. App tạm giữ như API hiện tại: chỉ đọc câu khi `finalize` trả `voice_challenge`.
- Câu 3 (LIVE-01) và câu 4 (OTP, CCCD) đang chặn app. Nếu M5/M2 bận thì Quang+Claude làm được: FLOW-03 vốn thuộc M1.
- Câu 16 (`can-chot.md`, M4): thêm `audio_offset_ms` vào `/voice`, vì video vẫn bắt đầu trước WAV khoảng 0,6 s.
- Câu 17: bàn duyệt chưa xem được media. `MediaRef.kind` thiếu `voice_video`, chưa có route `/media`, web `/review` còn trống.
- Câu 14 (`can-chot.md`): cần cách để server mở ca duyệt thủ công khi người dùng không xem được màn nháy màu.
- Câu 15: xác nhận giữ dấu tích "build trên Windows".

## Test đã chạy
```
Windows 11, JDK 17 (D:\tools\jdk17), Android SDK 35, apps/android:
./gradlew --no-daemon testDebugUnitTest assembleDebug
  → BUILD SUCCESSFUL, 52/52 test qua (sau khi sửa theo reviewer)
    (CaptureTest 7, CitizenCopyTest 1, ContractTest 2, FlowRulesTest 9, IdCardTest 5,
     LiveFlowRetryTest 9, LiveFlowTest 6, ProbeRegionsTest 8, ScreensSnapshotTest 5)
./gradlew --no-daemon assembleRelease
  → BUILD FAILED đúng ý: :app:checkReleaseApiUrl "Release cần -Pvericlue.apiBaseUrl=https://…"
./gradlew --no-daemon assembleRelease -Pvericlue.apiBaseUrl=https://example.invalid/
  → BUILD SUCCESSFUL, app-arm64-v8a-release.apk 23 488 823 byte

Cập nhật 13:20:
./gradlew testDebugUnitTest assembleDebug → BUILD SUCCESSFUL, 61/61 test qua
uv run pytest services/api (nhánh contract) → qua; gen_openapi --check khớp; ruff sạch
Máy ảo + API mới ở cổng 8001 (app build với -Pvericlue.apiBaseUrl=http://10.0.2.2:8001/):
  OTP: tin nhắn mô phỏng hiện mã; nhập sai → "Mã chưa đúng. Bạn còn 4 lần thử."; nhập đúng → sang chụp CCCD
  CCCD: server lưu id_front.jpg + id_back.jpg; máy ảo không có QR → server trả retry → app quay lại chụp mặt sau
  low_quality: server nhận 7 dot_events khớp 7 điểm dot_path → "Ảnh chưa đủ rõ", còn 1 lần
    → "Chụp lại" → app gọi POST /challenge → turn_order mới ["right","left"], app hiện "Quay sang phải" trước
  Chưa thử: sửa thông tin CCCD (máy ảo không có QR thật), gián đoạn sau bước A

Cập nhật 11:20:
./gradlew testDebugUnitTest assembleDebug → BUILD SUCCESSFUL, 53/53 test qua
Máy ảo Pixel 6 (Android 14, webcam) + API mock (SQLite), điều khiển bằng adb:
  genuine, tắt mạng máy ảo (svc wifi/data disable) rồi gửi → "Không kết nối được"
    → "Thử lại" khi vẫn mất mạng → lại "Không kết nối được" (không ra thành công)
    → bật mạng, "Thử lại" → "Xác minh thành công", chỉ tích "Khuôn mặt"
    → server nhận face_image.jpg + face_video.mp4 (1,5 MB); cache app không còn face_*.mp4
  voice_clone → đọc câu → chờ duyệt; server nhận voice_audio.wav + voice_video.mp4
    độ dài (2 lượt bấm cách nhau 5 s và 6 s): WAV 4,50 s / MP4 5,22 s; WAV 5,66 s / MP4 6,23 s
  GET /v1/review/cases/{id}: ca có trong danh sách, nhưng media thiếu voice_video và /media/… trả 404 (câu 17)
```
