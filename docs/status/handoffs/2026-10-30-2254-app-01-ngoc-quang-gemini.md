# Bàn giao · APP-01 · Ngoc Quang+Gemini · 2026-10-30 22:54

**Nhánh:** codex/APP-01-demo-integration
**Trạng thái task sau phiên này:** doing

## Đã xong
- **Task 1 — Công cụ chẩn đoán tái lập & kiểm tra readiness (`[LIVE-02]`, commit `c01e014`):**
  - Thêm CLI `scripts/diagnose_presence_session.py` (`schema_version = 1`) và bộ test `scripts/tests/test_diagnose_presence_session.py` (kiểm khử PII, giữ nguyên lý do lỗi và đảm bảo `lease.release()` trong `finally:` kể cả khi reader ném lỗi).
  - Xuất báo cáo chẩn đoán không chứa PII cho 4 phiên gần nhất tại `D:\vericlue\tmp\full-demo-setup\presence-stabilization\task1-diagnostic-report.json`:
    - Xác nhận độc lập `artifact_readiness`: `face_pad` v2 = `unavailable`, `face_deepfake` v2 = `unavailable`, `identity_face_calibration` = `unavailable`, `identity_consistency_calibration` = `unavailable`, `account_enrollment = false`, `full_flow_ready = false`.
- **Task 2 — Trace đối chiếu thời gian thực có giới hạn (`[APP-01]`, commit `04db668`):**
  - Tạo `PresenceDebugTrace.kt` và `PresenceDebugTraceTest.kt` (tắt mặc định `enabled = false`, giới hạn `maxSamples = 1024`, `minSampleGapMs = 100L`, xóa sạch giữa các lượt bằng `clear()`, từ chối gán mẫu có `recordingRelMs` ngoài cửa sổ `[windowStartRelMs, windowEndRelMs)` cho đoạn mới).
  - Đối chiếu định lượng 4 phiên thực tế (`task2-alignment-analysis.json`):
    - **Quay đầu (`head_turn`):** Phiên `14:17:02` (trước khi có cảnh báo nghiêng đầu) đạt đủ `125/125` mẫu hợp lệ (`no_face = 0`, `yaw = -39.75°..+45.55°`), chỉ trượt `pose_out_of_range` do `max_abs_roll = 16.79° > 15°`. Ba phiên sau (`14:21:00`, `14:38:09`, `14:39:35`) bị `incomplete_time_window` (`max_gap_ms = 899..2098 ms`) do người dùng quay mặt rời màn hình không nhìn thấy chữ và `TurnPoseState.Hold` không phát âm báo khi vừa vào vùng `[20°, 38°]`, khiến người dùng tiếp tục xoay quá đà lên `51.8°..60.9°` và mất mặt. Ngoài ra `SegmentHoldTracker` trước đây chưa chặn khung hình trễ (`timestampNs < segmentStartMs`) từ đoạn trước.
    - **Chấm mắt (`gaze_tracking`):** Phiên `14:17:02` đã `pass` (`r_x = 0.730, r_y = 0.731, lag = 200 ms`). Ở 2 phiên `14:21:00` và `14:38:09`, tương quan theo 8 mốc điểm dừng (`waypoints`) đạt `r_x = 0.861` và `0.744`, nhưng tương quan chuỗi 100 ms giảm còn `0.528` và `0.443` do hai nguyên nhân kỹ thuật: (1) hai điểm khóe mắt đơn lẻ `(33, 133)` và `(362, 263)` trên lưới mí mắt mềm bị kéo dịch theo mống mắt làm suy giảm biên độ ngang; (2) `FaceObservationReader` chạy `RunningMode.IMAGE` không trạng thái ở `10 Hz` gây nhiễu lượng tử hóa từng khung hình trên quỹ đạo mục tiêu `1 Hz`. Riêng phiên `14:39:35`, tại `t = 1226..1625 ms` mắt thực tế nhìn lệch sang phải (`0.527`) khi chấm ở bên trái (`0.31`), nên vẫn phải `fail` trung thực.
- **Task 3 — Sửa từng nguyên nhân đã chứng minh theo TDD (`[APP-01]` commit `752c93c`, `[LIVE-02]` commit `2b275c0`):**
  - Android (`Signals.kt`, `FaceScreens.kt`, `CaptureTest.kt`):
    - Thêm `segmentStartMs` vào `SegmentHoldTracker` để chặn mọi khung hình cũ (`frameMs < segmentStartMs`) không làm hoàn tất đoạn mới (`staleFrameCannotCompleteNewSegmentHold`).
    - Phát âm báo ngắn `65 ms` (âm lượng dịu `35/100`, tối đa 1 lần/trạng thái/đoạn) ngay khi vào `TurnPoseState.Hold` để người dùng biết dừng xoay khi mặt đã quay khỏi màn hình; đổi câu chữ khi giữ đủ trong đoạn sang câu trung tính `"Tạm giữ đủ góc, nhìn thẳng"`.
  - ML (`landmarks.py`, `gaze.py`, `test_gaze.py`):
    - Cố định trục ngang mắt bằng cụm mốc hốc mắt – khóe mắt (`(33, 130, 226)` / `(133, 243, 244)` và `(362, 463, 464)` / `(263, 359, 446)`) cùng 5 điểm mống mắt (`468..472`, `473..477`), chống kéo trôi khóe mắt mềm (`test_orbital_canthus_cluster_resists_palpebral_commissure_drag`).
    - Thêm bộ lọc trung bình trượt đối xứng 3 mẫu (`100 ms` lân cận) trong `evaluate_gaze` trước khi tính tương quan 2 trục (`test_gaze_preserves_both_axes_and_known_response_lag`), giữ nguyên mọi ngưỡng (`MIN_CORRELATION = 0.60`, `MIN_IRIS_SPAN`, cả hai trục `X`/`Y`, `MAX_LAG_MS = 350`). Nâng `GAZE_VERSION` lên `gaze-rules@0.3+face-landmarker-f16-1`.
- **Task 4 & 5 — Kiểm tra chốt hạ lưu, đóng gói APK và cập nhật server:**
  - Ghi rõ danh mục artifact còn thiếu tại `D:\vericlue\tmp\full-demo-setup\presence-stabilization\missing-artifacts.md`; giữ nguyên `ACCOUNT_ENROLLMENT=false`, không tạo calibrator giả.
  - Chạy xanh `recordPaparazziDebug --tests "*FaceChallengeSnapshotTest*"`, `testDebugUnitTest` (172/172 test Android), `assembleDebug`, và 119 test Python liên quan; `ruff check` sạch; `scripts/plan_check.py` báo `0 lỗi`.
  - Xác nhận chữ ký APK (`822e5e44be42ce365f186a6c73af5bf36eb262c3cc65011b4269363adc695c75`), SHA-256 (`E933A123FBBFE7CE9A5EC7C424F412D6920E86D565197FBA8FA9C47E1ADFA06F`), copy sang `D:\vericlue\tmp\full-demo-setup\apk\VeriClue-demo-debug.apk`, cài đè qua `adb install -r` và khởi động lại server cổng `8421`.

## Đang dở
- **Kết luận 1 — Mắt / quay đầu (prefix):** Đã sửa các lỗi kỹ thuật đã chứng minh và cài bản APK mới lên máy `SM_A526B`; sẵn sàng để người dùng chạy nghiệm thu hữu hạn (tối đa 3 lượt thử thật trên điện thoại theo kịch bản chuẩn).
- **Kết luận 2 — Toàn luồng eKYC / ghi danh:** **Chưa sẵn sàng đạt `pass` toàn luồng** (`full_flow_ready = false`) vì 4 artifact hiệu chỉnh độc lập (`face_pad` v2, `face_deepfake` v2, `IDENTITY_FACE_CALIBRATION`, `IDENTITY_CONSISTENCY_CALIBRATION`) vẫn là `unavailable` và `account_enrollment = false`. Dù `gaze_tracking` và `head_turn` đạt `pass`, phiên xác minh vẫn sẽ trả `review` ở các mô-đun hạ lưu.

## Bước tiếp theo
1. Thực hiện tối đa 3 lượt thử nghiệm thu hữu hạn trên điện thoại `SM_A526B` (giữ điện thoại cách mặt 30–40 cm; ở bước quay đầu dừng lại ngay khi nghe tiếng bíp ngắn đầu tiên báo vào vùng giữ góc, chờ tiếng bíp thứ hai rồi quay về nhìn thẳng).
2. Chạy `scripts/diagnose_presence_session.py --server-dir D:\vericlue\tmp\full-demo-setup\server --latest 3` sau lượt thử để kiểm tra kết quả `gaze_tracking` (`gaze-rules@0.3+face-landmarker-f16-1`) và `head_turn`.
3. Thu thập dữ liệu có quyền sử dụng hợp lệ theo `SEC-09` (tách biệt `calib_fit` / `calib_ltt` theo người) để fit calibrator thật cho `face_pad` v2, `face_deepfake` v2 và `face_match` trước khi mở `ACCOUNT_ENROLLMENT=true`.

## Quyết định, lưu ý, bẫy
- Bắt buộc tắt `PresenceDebugTrace` mặc định (`enabled = false`) trong bản giao.
- Khi khởi động lại `scripts/server.py` từ PowerShell, không dùng `Start-Process -Wait` trên tiến trình cha vì tiến trình con `uvicorn` kế thừa descriptor log sẽ giữ pipe mở vô hạn; dùng daemon hoặc kiểm `/healthz` trực tiếp.

## Câu hỏi cho nhóm
- Không có.
