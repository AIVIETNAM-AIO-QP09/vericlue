# Bàn giao · LIVE-01 · Ngoc Quang+Codex · 2026-10-30 16:05

**Nhánh:** codex/APP-01-demo-integration
**Trạng thái task sau phiên này:** doing

## Đã xong
- Theo lựa chọn của người dùng: dynamic v2 quay đầu 12000 ms, mỗi hướng 4000 ms; vẫn nhận v1/6000 cho lượt cũ. Kiểm cặp version/duration và tổng lịch <=30000 ms, voice offset đúng.
- Contract/schema/Pydantic/OpenAPI/examples và type web đồng bộ; bộ sinh phát v2, không đổi màu/nhịp nháy hoặc ngưỡng xác minh.
- ML chọn calibrator theo request/protocol, cache cả trường hợp thiếu theo version; không sửa self.version chung khi request v1/v2 xen kẽ. Collector không gộp protocol. VideoFaceMatch nhiều góc v2 có version riêng, không dùng ngưỡng v1 cho v2.
- Android có đếm ngược và hướng tiếp theo theo mốc server, giữ video liên tục, không thêm delay/TTS/bước tập. Bố cục đo chiều cao và oval giới hạn theo vùng trống chỉ tại màn quay đầu để chữ lớn không chồng lấn; camera capture không thay đổi.
- Cải thiện hướng dẫn quay đầu thời gian thực trên Android (`HeadTurnGuide` trong `Signals.kt`, nối `camera.face` vào `FaceTimelineScreen` / `TurnHeadContent`): nhắc khi mất mặt (`faces == 0`), nhiều mặt (`faces > 1`), chưa quay đủ góc (`|yaw| < 18°` → `"Quay chậm theo hướng mũi tên"` thay vì báo giữ tư thế ngay từ đầu đoạn), quay quá xa hoặc sát mép khung (`|yaw| > 40°` hoặc lệch tâm > `0.24` → `"Quay vừa phải, giữ mặt trong khung"`), giữ tư thế khi đã vào vùng góc hợp lệ (`18°..40°`), và quay về giữa ở đoạn nhìn thẳng (`|yaw| > 12°`). Chỉ hỗ trợ hiển thị, không quyết định `pass`.
- 45 ảnh trước/sau tại tmp/head-turn-4s/{before,after}; đã xem chữ lớn 200%, compact và các trạng thái trái/giữa. Không commit ảnh vào repo.

## Đang dở
- Đã kiểm tra chẩn đoán 2 lượt thử v2 thực tế (`ses_da2a3a69f00d32e7`, `ses_c8e4f05fcf439bbc`):
  - **Đồng hồ video:** `recordingStartMs()` và dấu thời gian MP4 khớp trong khoảng `0–100 ms` (độ dài video `25214 ms` / `25480.5 ms` cho lịch `25184 ms` / `25382 ms`; tương quan mắt đạt đỉnh ở `lag = 0..50 ms`).
  - **Hướng trái/phải (`yaw_deg`):** video MP4 từ camera trước không lật gương; khi người dùng quay trái (`Seg 0`), mũi dịch sang phải ảnh (`nose_x > eyes_x`) và `yaw_deg > 0` (`+19.7°..+59.5°`); khi quay phải (`Seg 1`), `yaw_deg < 0` (`-26.5°..-61.6°`); khi nhìn thẳng (`Seg 2`), `yaw_deg` về quanh `0°`. Chiều dấu `landmarks.py` / `head_turn.py` đúng.
  - **Nguyên nhân `head_turn = incomplete_time_window`:** ở bản trước, đầu đoạn quay chip hiện ngay `"Giữ hướng này đến khi đổi hướng dẫn"` khiến người dùng giữ thẳng mặt 2,5–3,4 giây đầu rồi mới quay gấp quá đà (`46°..61°`, vượt `TURN_MAX_DEG = 50°`) làm MediaPipe mất mặt `0,80–1,26 giây` (`> MAX_GAP_MS = 300 ms`).
  - **Tọa độ mắt (`gaze_tracking = trajectory_mismatch`):** cả hai trục `gaze_x` và `gaze_y` đều tương quan dương với chấm mục tiêu (`corr_x = +0.51..+0.73`, `corr_y = +0.38..+0.54`), không bị ngược trục; tuy nhiên biên độ mống mắt dọc nhỏ (`iris_span_y ≈ 0.019..0.026`) nên chưa vượt ngưỡng thử nghiệm `MIN_AXIS_CORRELATION = 0.60`. Giữ nguyên ngưỡng và thuật toán theo ràng buộc.
  - **Tách lỗi thu nhận khỏi thiếu hiệu chỉnh AI:** `face_pad`, `face_deepfake` và `face_match` (khi bật `IDENTITY_CONSISTENCY_REQUIRED=true`) gọi `session_views`, nên khi `head_turn` chưa `PASS` thì dừng ở `degraded (E_LOW_QUALITY)`. Riêng khung nhìn thẳng `500 ms` của cả hai phiên đều đạt kiểm tư thế (`yaw = -1.60°` và `-3.48°`, cosine với CCCD `0.4907` và `0.5701`). Kể cả khi `head_turn` đạt, `PAD/GenD` và `face_match` v2 vẫn `degraded` cho tới khi có artifact hiệu chỉnh thật cho giao thức v2 (`+session-video-v2`, `+head12s-v2`).
- Chưa có artifact hiệu chỉnh thật đúng protocol v2, chưa nghiệm thu đạt toàn luồng và chưa hoàn thiện SEC-09. Lỗi/degraded vẫn không được đạt; guard ghi danh mock/mixed giữ nguyên.
- iOS hiện kiểm version 1 nên chưa dùng với lịch mới; không sửa iOS trong đợt này.
- Chưa có lượt thử người dùng sau bản bổ sung `HeadTurnGuide`; không tuyên bố đã nghiệm thu chuyển động hoặc đạt xác minh.

## Bước tiếp theo
1. Sau cập nhật, tạo phiên mới để nhận v2; phiên v1 cũ vẫn 2 giây/hướng.
2. Giữ điện thoại cố định; đến mỗi hướng quay đầu chậm theo mũi tên và giữ đến hướng dẫn kế tiếp, cuối cùng nhìn thẳng. Chỉ theo chấm bằng mắt trong phần trước đó.
3. Nếu vẫn review, đọc chẩn đoán theo module trước sửa; không mặc định do người dùng và không hạ ngưỡng để ép đạt. Chưa dùng video thử để fit.

## Quyết định, lưu ý, bẫy
- Các regression v2 gom tại ml/tests/test_head_protocol_v2.py và tái dùng fixture tổng hợp; rủi ro coupling fixture được bù bằng chạy suite cũ và mới.
- Unit adapter trước đây mock session_views và bỏ metadata; nay fixture cấp metadata v1 rõ ràng để kiểm chọn protocol trước decode. API test dùng gói v2 đầy đủ do generator phát.
- Paparazzi phát hiện chữ lớn bị chồng; sửa theo layout đo kích thước, mặc định oval các màn khác giữ nguyên. Cần thử thật để đánh giá hướng dẫn, không suy từ ảnh snapshot rằng xác minh sẽ đạt.
- OTP demo, guard, giới hạn video/decoder và các ngưỡng chuyển động không đổi. Không push/PR; không sửa STATUS, ADR hoặc thresholds.yaml.
- Review độc lập phát hiện race trong collector: lịch có thể bị thay sau preflight nhưng trước đo, trộn protocol dù row lỗi. Đã có 4 test đỏ cho thay khi nạp model/đo mẫu trước, cả mẫu thành công/lỗi; sửa bind hash lịch từ preflight, kiểm lại trước/sau từng lượt và trước ghi report. Các test xanh, toàn suite 775/775.

### Các mục review để lại cho phạm vi khác

- Chốt API/template/continuity vẫn từ chối version nhiều góc mới khi chưa đủ bằng chứng: giữ theo thiết kế, chi phí là chưa ghi danh/đăng nhập thật toàn luồng.
- Độ chính xác chuyển động, hướng ảnh gương và UX máy thật: cần người dùng thử bản mới; chi phí là vẫn có thể phải sửa sau lượt thực tế.
- Kiểm tư thế riêng từng đoạn và xác minh chiều sâu: luật cũ được giữ; chi phí là chưa được coi đã chống tấn công chiều sâu.
- Cài APK/restart/handoff: đã kiểm vận hành bên dưới, còn người dùng nghiệm thu; Wi-Fi/cổng reverse có thể cần nối lại khi đổi mạng.
- iOS v2: ngoài phạm vi theo yêu cầu; chi phí là chưa demo iOS bằng server lịch mới.

## Câu hỏi cho nhóm
- Cần bộ dữ liệu đúng protocol và hiệu chỉnh/đánh giá độc lập; kéo dài thời gian không tự giải quyết độ chính xác hoặc bằng chứng chiều sâu.

## Test đã chạy
- Suite Python ML/API/router/contract sau sửa review: 775 test, 0 lỗi/thất bại/bỏ qua (final.xml trong evidence local); có cảnh báo dependency/fixture cũ.
- Android testDebugUnitTest + assembleDebug: 163 test (thêm `headTurnGuideHelpsHoldOrCorrectWithoutDecidingPass` trong `CaptureTest`), 0 lỗi/thất bại/bỏ qua; JUnit đã giữ riêng. CitizenCopyTest và ThemeAccessibilityTest nằm trong suite.
- recordPaparazziDebug --tests '*FaceChallengeSnapshotTest*': qua, 45 ảnh before/after; view kiểm đại diện chữ 200%/compact.
- Ruff phần Python thay đổi: sạch; OpenAPI --check khớp; web npm run typecheck qua.
- plan_check.py: 0 lỗi, 10 cảnh báo tải công việc/đường găng hiện có; git diff --check qua.
- SDK apksigner xác nhận APK arm64 debug có v2 signature, signer SHA256 822e5e44be42ce365f186a6c73af5bf36eb262c3cc65011b4269363adc695c75 khớp bản đang cài.

## Bàn giao vận hành đã kiểm

- APK tại D:/vericlue/tmp/full-demo-setup/apk/VeriClue-demo-debug.apk; SHA256 mới `b7bdc24ae23574357c87d0a6979f53e04bdcc96ff4da3dc48b7447251f985b93` (bản trước lưu tại `apk/archive-1c4f69a` và `apk/archive-94be648`).
- Đã `adb install -r` Success trên Samsung SM_A526B qua ADB Wi-Fi; hash `base.apk` trên máy khớp chính xác (`b7bdc24ae23574357c87d0a6979f53e04bdcc96ff4da3dc48b7447251f985b93`). Không gỡ app hoặc xóa Keystore.
- Launcher hiện có giữ nguyên server, DB/.env/khóa. Health ok, failed_modules rỗng, mock_models true đúng do OTP demo.
- Smoke HTTP bằng metadata/khóa công khai tổng hợp: nhận version=2, head_duration_ms=12000, mỗi đoạn 4000; voice offset đúng, tổng trong giới hạn 30000; rút phiên synthetic sau thử. Không thu hoặc xuất media người thật.
- ADB reverse tcp:8421 đã nối lại, app đã mở. Bằng chứng local tại D:/vericlue/tmp/full-demo-setup/head-turn-4s/delivery-smoke.json. Người dùng tự bắt đầu lượt mới để nghiệm thu.
