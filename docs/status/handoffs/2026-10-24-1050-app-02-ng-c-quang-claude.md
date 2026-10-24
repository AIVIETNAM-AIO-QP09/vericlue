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
