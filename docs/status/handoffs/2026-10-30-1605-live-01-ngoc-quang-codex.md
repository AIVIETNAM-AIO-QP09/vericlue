# Bàn giao · LIVE-01 · Ngoc Quang+Codex · 2026-10-30 16:05

**Nhánh:** codex/APP-01-demo-integration
**Trạng thái task sau phiên này:** doing

## Đã xong
- Theo lựa chọn của người dùng: dynamic v2 quay đầu 12000 ms, mỗi hướng 4000 ms; vẫn nhận v1/6000 cho lượt cũ. Kiểm cặp version/duration và tổng lịch <=30000 ms, voice offset đúng.
- Contract/schema/Pydantic/OpenAPI/examples và type web đồng bộ; bộ sinh phát v2, không đổi màu/nhịp nháy hoặc ngưỡng xác minh.
- ML chọn calibrator theo request/protocol, cache cả trường hợp thiếu theo version; không sửa self.version chung khi request v1/v2 xen kẽ. Collector không gộp protocol. VideoFaceMatch nhiều góc v2 có version riêng, không dùng ngưỡng v1 cho v2.
- Android có đếm ngược và hướng tiếp theo theo mốc server, giữ video liên tục, không thêm delay/TTS/bước tập. Bố cục đo chiều cao và oval giới hạn theo vùng trống chỉ tại màn quay đầu để chữ lớn không chồng lấn; camera capture không thay đổi.
- Cải thiện hướng dẫn quay đầu thời gian thực trên Android (`HeadTurnGuide` trong `Signals.kt`, nối `camera.face` vào `FaceTimelineScreen` / `TurnHeadContent`):
  - Khi thiếu tín hiệu (`face == null`), chỉ hiện hướng dẫn trung tính (`"Quay chậm theo hướng mũi tên"` hoặc `"Giữ yên, nhìn thẳng vào camera"`), không xác nhận `"Giữ hướng này..."`.
  - Kiểm đúng dấu `Face.headEulerAngleY` của ML Kit trên ảnh camera trước không lật (`InputImage.fromMediaImage(media, rotation)` trong `CameraSession.kt`: người dùng quay trái `TurnDir.Left` làm mặt hướng sang phải ảnh không lật nên `yaw > 0`; quay phải `TurnDir.Right` có `yaw < 0`). Chỉ xác nhận `"Giữ hướng này đến khi đổi hướng dẫn"` khi quay đúng hướng trong khoảng `18°..40°` và mặt trong khung; quay ngược hướng hoặc chưa đủ góc (`signedYaw < 18°`) vẫn nhắc `"Quay chậm theo hướng mũi tên"`; quay quá xa (`signedYaw > 40°` hoặc lệch tâm > `0.24`) nhắc `"Quay vừa phải, giữ mặt trong khung"`. Chỉ hỗ trợ hiển thị, không quyết định `pass`.
- Sửa gốc quy chiếu tọa độ dọc mống mắt trong `eye_position` (`ml/src/vericlue_ml/presence/landmarks.py`) và nâng `GAZE_VERSION` từ `gaze-rules@0.1+face-landmarker-f16-1` lên `gaze-rules@0.2+face-landmarker-f16-1` (`ml/src/vericlue_ml/presence/gaze.py`) để truy vết rõ kết quả trước/sau:
  - Trước khi sửa (`0.1`): `horizontal` chiếu tâm mống mắt theo trục hai khóe mắt cố định (`corners = (33, 133)` và `(362, 263)`), nhưng `y` lại trừ trung điểm hai mí mắt (`lids = (159, 145)` và `(386, 374)`). Khi mắt nhìn lên/xuống, mí trên và mí dưới dịch chuyển dọc cùng chiều với mống mắt, triệt tiêu 36%–62% biên độ `iris_span_y` và làm nhiễu `correlation_y`.
  - Bản sửa tối thiểu (`0.2`): giữ nguyên kiểm độ mở mắt (`opening < MIN_EYE_OPEN_RATIO`) bằng `lids`, chỉ đổi gốc `center_y` sang trung điểm hai khóe mắt `(xy[corners[0]] + xy[corners[1]]) / 2`, không đổi bất kỳ ngưỡng nào trong `gaze.py`.
  - Giới hạn kết luận: 4 video thực tế hiện có chỉ là mẫu chẩn đoán để tìm lỗi; việc một số mẫu chẩn đoán đạt `evaluate_gaze` sau khi sửa chỉ xác nhận công thức mới hết triệt tiêu biến thiên dọc trên các mẫu đó, **chưa chứng minh độ chính xác tổng quát hoặc khả năng chống tấn công**.
- 45 ảnh trước/sau tại tmp/head-turn-4s/{before,after}; đã xem chữ lớn 200%, compact và các trạng thái trái/giữa. Không commit ảnh vào repo.

## Đang dở
- Chẩn đoán 4 lượt thử v2 thực tế (`ses_da2a3a69f00d32e7` lúc 16:29, `ses_c8e4f05fcf439bbc` lúc 16:32, `ses_22c86c665303a52c` lúc 17:24, `ses_67a35fbfe77cf3f3` lúc 17:27) — tách rõ lỗi ghi hình/đồng bộ, giới hạn detector và thiếu calibration:
  - **1. Khoảng mất dữ liệu chính xác trên 2 lượt mới nhất (17:24 và 17:27):**
    - **`ses_22c86c665303a52c` (17:24:56, lịch `('right', 'left', 'center')`, cửa sổ đầu `[13169.0 .. 25669.0 ms]`):**
      - Video MP4: `773` khung, `0.0 .. 25780.3 ms`, khoảng cách khung thô lớn nhất `66.6 ms` (`0` khoảng trống `> 100 ms`).
      - Mẫu trích xuất trong `[13169.0 .. 25669.0 ms]`: `125` mẫu (`first = 13189.9 ms`, `last = 25580.4 ms`, lệch biên đầu `+20.9 ms <= 200 ms`, thiếu biên cuối `88.6 ms <= 200 ms`).
      - Hợp lệ: `117 / 125` mẫu (`coverage = 0.929` so với `126` mẫu kỳ vọng). Không hợp lệ: `8` mẫu — **100% do `face_count == 0` (`no_face`), 0 mẫu mất pose (`pose_angles != None`, `scale_ratio = 1.0` trên mọi khung có mặt)**.
      - Khoảng trống (`gap`) giữa các mẫu hợp lệ `> 150 ms`:
        1. `19984.7 -> 20484.3 ms` (**`gap = 499.6 ms > MAX_GAP_MS = 300 ms`**, `rel = +6315.7 .. +6815.3 ms` ở đoạn 1 `left`): mất 4 mẫu (`20084.6, 20184.6, 20284.5, 20384.4 ms`) khi đầu quay quá xa (`yaw = +56.8°` trước gap -> `+65.5°` sau gap).
        2. `20584.3 -> 21083.9 ms` (**`gap = 499.6 ms > MAX_GAP_MS = 300 ms`**, `rel = +6915.3 .. +7414.9 ms` ở đoạn 1 `left`): mất 4 mẫu (`20684.2, 20784.1, 20884.0, 20983.9 ms`) khi đầu giữ ở `+65.5° .. +66.3°`.
    - **`ses_67a35fbfe77cf3f3` (17:27:38, lịch `('left', 'right', 'center')`, cửa sổ đầu `[12667.0 .. 25167.0 ms]`):**
      - Video MP4: `759` khung, `0.0 .. 25280.7 ms`, khoảng cách khung thô lớn nhất `66.6 ms` (`0` khoảng trống `> 100 ms`).
      - Mẫu trích xuất trong `[12667.0 .. 25167.0 ms]`: `125` mẫu (`first = 12690.3 ms`, `last = 25114.1 ms`, lệch biên đầu `+23.3 ms <= 200 ms`, thiếu biên cuối `52.9 ms <= 200 ms`).
      - Hợp lệ: `106 / 125` mẫu (`coverage = 0.841` so với `126` mẫu kỳ vọng). Không hợp lệ: `19` mẫu — **100% do `face_count == 0` (`no_face`), 0 mẫu mất pose**.
      - Khoảng trống (`gap`) giữa các mẫu hợp lệ `> 150 ms`:
        1. `16987.0 -> 17186.8 ms` (`gap = 199.8 ms`, `rel = +3820.0 .. +4019.8 ms` cuối đoạn 0 `left`): mất 1 mẫu (`17086.9 ms`) giữa `yaw = +58.5°` và `+58.9°`.
        2. `17186.8 -> 17686.5 ms` (**`gap = 499.6 ms > 300 ms`**, `rel = +4019.8 .. +4519.5 ms`): mất 4 mẫu (`17286.8 .. 17586.5 ms`) giữa `yaw = +58.9°` và `+61.4°`.
        3. `19984.7 -> 21483.6 ms` (**`gap lớn nhất = 1498.9 ms > 300 ms`**, `rel = +6817.7 .. +8316.6 ms` ở đoạn 1 `right`): mất 14 mẫu liên tiếp (`20084.6 .. 21383.6 ms`) giữa `yaw = -61.6°` và `-58.3°`.
  - **2. Đối chiếu lịch server với mốc chuyển pha thực tế (và giới hạn của phép đo):**
    - `Signals.frame_times` ghi nhận đầy đủ `567` khung (`0.0 .. 25747.0 ms`) ở phiên 17:24 và `576` khung (`0.0 .. 25280.7 ms`) ở phiên 17:27; file MP4 kết thúc ở `25780.3 ms` và `25280.7 ms` (không bị cắt ngắn cuối video).
    - Khi màn hình Android chuyển từ nền trắng sáng của bước chấm mắt (`TimelineGaze`) sang nền tối của màn quay đầu (`TurnHeadContent`) tại `head_start_at_ms` (`13669.0 ms` ở 17:24; `13167.0 ms` ở 17:27), độ sáng trung bình khung hình MP4 (`mean luma`) sụt bậc thang tại `raw_ts = 13889.4 ms` (`145.2 -> 131.7`, `+220.4 ms`) ở 17:24 và tại `raw_ts = 13389.8 ms` (`135.9 -> 127.1`, `+222.8 ms`) ở 17:27. Mốc thay đổi độ sáng này **hỗ trợ kiểm tra đồng bộ tại điểm chuyển pha `TimelineGaze -> TurnHeadContent`**, nhưng bị ảnh hưởng bởi độ trễ phơi sáng tự động của camera trước và **chưa chứng minh mọi thời điểm trong toàn bộ lịch đều khớp tuyệt đối**.
  - **3. Phân biệt 3 nhóm nguyên nhân:**
    - **Ghi hình / đồng bộ:** Không phát hiện rớt khung hoặc cắt ngắn file (`max_raw_frame_gap = 66.6 ms`, biên đầu/cuối cửa sổ khớp trong `20–89 ms`), mốc luma tại điểm chuyển sang màn quay đầu cách `head_start_at_ms` khoảng `~220 ms` (bằng chứng hỗ trợ tại điểm chuyển pha, không suy rộng thành đồng bộ tuyệt đối mọi mốc).
    - **Giới hạn detector & thao tác góc quay:** Cả MediaPipe `FaceLandmarker` phía server (kể cả khi hạ thử `min_face_detection_confidence = 0.3`) lẫn ML Kit `PERFORMANCE_MODE_FAST` phía Android (`Signals.region_means` thiếu đúng các khung `19984.7..20684.2 ms` ở 17:24 và `17020.3..17952.9 ms` ở 17:27) đều mất mặt (`face_count = 0`) khi đầu người dùng quay vượt `|yaw| ≈ 58°–66°` (góc nghiêng hoàn toàn). Ngoài ra, `evaluate_head_turn` hiện áp dụng cả kiểm `np.diff(times).max() <= 300 ms` và `abs(yaw_deg) <= 50°` trên toàn cửa sổ `valid`, nên chỉ cần người dùng xoay quá đà qua ngưỡng `50°–60°` ở đỉnh lượt quay là phiên bị `incomplete_time_window` hoặc `pose_out_of_range`, dù đã giữ trong vùng `20°..50°` đủ lâu (`1898.5 ms` ở `right` và `1199.1 ms` ở `left` trong phiên 17:24).
    - **Thiếu hiệu chỉnh AI (calibration):** Kiểm độc lập 3 khung (`front`, `left`, `right`) đã qua kiểm tư thế `[20°..50°]` của hai phiên 17:24 và 17:27 trên các mô-đun downstream cho thấy: `face_deepfake` (`status = ok`, `score = 0.2112` / `0.2530`), `face_pad` (`status = ok`, `score = 0.9990` / `0.9997`) và `face_match` (`score = 0.5418` / `0.4563`) đều tính được `score` thực, nhưng `SessionAttackDetector` và `VideoFaceMatchDetector` chuyển về `status = degraded, prob_attack = None` vì chưa có artifact hiệu chỉnh cho giao thức v2 (`+session-video-v2`, `+head12s-v2`).
- Chưa có artifact hiệu chỉnh thật đúng protocol v2, chưa nghiệm thu đạt toàn luồng và chưa hoàn thiện SEC-09. Lỗi/degraded vẫn không được đạt; guard ghi danh mock/mixed giữ nguyên.
- iOS hiện kiểm version 1 nên chưa dùng với lịch mới; không sửa iOS trong đợt này.
- Đã commit bản sửa `landmarks.py`, `GAZE_VERSION` (`gaze-rules@0.2+face-landmarker-f16-1`), test và handoff; đã khởi động lại server local `localhost:8421` với đúng mã nguồn đã commit.
- Chưa có lượt thử mới sau khi nâng `gaze-rules@0.2+face-landmarker-f16-1`. Bước quay đầu vẫn còn vướng mất mặt (`face_count = 0`) khi người dùng quay quá xa (`> 50°–60°`), và vẫn thiếu calibration cho PAD/GenD/danh tính v2 nên **chưa thể hứa toàn luồng sẽ xác minh đạt**.
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

- APK tại D:/vericlue/tmp/full-demo-setup/apk/VeriClue-demo-debug.apk; SHA256 mới `152ab790af468612706148c650e1ce78158ea39f73c6ba0b18ed7e8563beee48` (bản trước lưu tại `apk/archive-1c4f69a` và `apk/archive-94be648`).
- Đã `adb install -r` Success trên Samsung SM_A526B qua ADB Wi-Fi; hash `base.apk` trên máy khớp chính xác (`152ab790af468612706148c650e1ce78158ea39f73c6ba0b18ed7e8563beee48`). Không gỡ app hoặc xóa Keystore.
- Launcher hiện có giữ nguyên server, DB/.env/khóa. Health ok, failed_modules rỗng, mock_models true đúng do OTP demo.
- Smoke HTTP bằng metadata/khóa công khai tổng hợp: nhận version=2, head_duration_ms=12000, mỗi đoạn 4000; voice offset đúng, tổng trong giới hạn 30000; rút phiên synthetic sau thử. Không thu hoặc xuất media người thật.
- ADB reverse tcp:8421 đã nối lại, app đã mở. Bằng chứng local tại D:/vericlue/tmp/full-demo-setup/head-turn-4s/delivery-smoke.json. Người dùng tự bắt đầu lượt mới để nghiệm thu.
