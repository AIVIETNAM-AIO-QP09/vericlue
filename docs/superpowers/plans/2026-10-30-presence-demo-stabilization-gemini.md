# Presence demo stabilization — Implementation Plan cho Gemini

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Người dùng chọn Gemini làm trực tiếp để tiết kiệm; không tự gọi thêm Codex/subagent. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sửa nguyên nhân có bằng chứng của lỗi mắt/quay đầu, nghiệm thu điện thoại và báo đúng khả năng demo toàn luồng.

**Architecture:** Giữ pipeline hiện có, đo đồng bộ trước rồi sửa từng nguyên nhân.
Chẩn đoán debug không tham gia quyết định API. Readiness của artifact/tài khoản
được kiểm ngay từ đầu, không chờ đến cuối mới phát hiện chốt độc lập.

**Tech Stack:** Kotlin/Compose/CameraX/ML Kit; Python/MediaPipe/FastAPI; pytest/Paparazzi.

**Spec:** `docs/superpowers/specs/2026-10-30-presence-demo-stabilization-design.md`.
Người dùng xem hai tài liệu và gửi prompt sang Gemini để bắt đầu thực hiện;
không coi việc Codex viết kế hoạch là đã triển khai.

## Global Constraints

Đọc toàn bộ mục Giới hạn bắt buộc và Nghiệm thu của spec. OTP mô phỏng, iOS
ngoài phạm vi; không nới điều kiện để ép đạt; không push/PR. Giữ nguyên nhánh
`codex/APP-01-demo-integration`, không reset các thay đổi do người khác tạo.
Không dùng video chẩn đoán làm tập chọn ngưỡng.

## Review Focus

1. Hướng ảnh gương/rotation và crop khác nhau giữa preview, analyzer, MP4.
2. Callback hoặc frame cũ làm xanh/đếm giữ trong segment mới.
3. T0 suy từ Status callback bị trễ, và nhịp frame bỏ qua lúc chuyển phase.
4. Chỉ một trục mắt kém nhưng bị che bởi correlation gộp/abs hoặc chọn đoạn.
5. Head pass rồi session_views/calibration/account vẫn chặn độc lập.

## Task 1 — Readiness và công cụ chẩn đoán tái lập

**Files:**
- Create: `scripts/diagnose_presence_session.py`, `scripts/tests/test_diagnose_presence_session.py`.
- Read: `services/api/src/vericlue_api/services/session_privacy.py`, `db/models.py`,
  `ml/src/vericlue_ml/common/calibration.py`, `face/match.py`.
- Update: file bàn giao APP-01 mới bằng `scripts/new_handoff.py`.

**Interfaces:** CLI `main(argv: list[str] | None = None) -> int`; report schema_version=1,
source commit, module versions, timestamp/protocol, module status/gate/reason,
gaze metrics, head missing/gap/pose aggregates, artifact readiness.
Không có token, CCCD, danh tính, media paths hoặc dữ liệu ảnh trong output.

- [ ] Viết test `test_diagnostic_report_redacts_private_payload_and_keeps_failures`:
  fixture payload có token/id_fields/ảnh giả; report không chứa các trường đó,
  giữ degraded/unclear và missing-calibrator, không tự sửa kết quả.
- [ ] Viết `test_diagnostic_media_lease_released_on_reader_failure`: reader lỗi
  vẫn close/release; phiên/media hết hạn báo unavailable, không khôi phục dữ liệu.
- [ ] Chạy test thấy đỏ; triển khai CLI dùng Settings/Database/SessionPrivacy,
  chọn latest hoặc session chỉ trong local, không log toàn payload/.env.
- [ ] Kiểm APK metadata và hash file local so với file giao; signer phải đúng.
  Nhận dạng lượt thử sau cài; không suy current APK từ DB timestamp đơn thuần.
- [ ] Kiểm đúng full version calibrator bằng loader trong runtime server;
  kiểm cấu hình match/consistency/enrollment. Ghi ngay blocker toàn luồng.
- [ ] Chạy CLI ở bốn lượt trong spec nếu dữ liệu còn hạn; báo riêng gaze và head.
  Dùng report có sẵn nếu media không còn, không ép chạy model thay bằng mock.
- [ ] Test xanh, commit tooling/handoff [LIVE-02]; không commit output runtime.

## Task 2 — Đối chiếu app và server theo cùng thời điểm

**Files:**
- Create: `apps/android/app/src/main/java/vn/vericlue/app/capture/PresenceDebugTrace.kt`.
- Test: `apps/android/app/src/test/java/vn/vericlue/app/PresenceDebugTraceTest.kt`.
- Modify: `capture/CameraSession.kt`, `ui/screens/FaceScreens.kt` (chỉ hook debug).
- Read: `capture/FaceTimeline.kt`, `ml/src/vericlue_ml/presence/landmarks.py`.

**Interfaces:** debug opt-in, bounded RAM trace cho một attempt; sample chứa
relative video time, segment, frame timestamp/age, yaw/pitch/roll, hướng dẫn;
gaze sample chứa thời điểm render và x/y thực tế. Không gửi vào Signals/API,
không dùng làm input để server chấp nhận. Chỉ tổng hợp local được lưu.

- [ ] Test đỏ `disabledTraceKeepsNoSamples`, `traceIsBoundedAndClearedBetweenAttempts`,
  `staleSampleCannotBeAttributedToNewSegment`: trace tắt rỗng, ring cap 1024, mỗi kênh tối đa 10 mẫu/giây (giữ thêm mốc đổi phase),
  clear xóa sample cũ; phân loại sample theo timestamp thay vì segment lúc callback.
- [ ] Thêm opt-in debug tắt mặc định; clock dùng CaptureClock hiện có. Không
  đổi ghi hình, t0, target chấm hay camera binding để “sửa” khi chưa có chứng cứ.
- [ ] Một lượt chẩn đoán có hướng dẫn: giữ đầu thẳng, quay nhẹ và dừng khi báo.
  Stream/đối chiếu số đo trong local, không xuất video hay raw sinh trắc ra chat.
- [ ] Report riêng (a) yaw app vs server tại các mốc tương ứng; (b) độ trễ
  analyzer/hướng dẫn; (c) rotation/mirror/crop; (d) thời điểm chấm thực vẽ so
  với lịch server và PTS. Chỉ t0 từ callback chưa đủ để kết luận đồng bộ.
- [ ] Nếu thiếu trace cũ, ghi thiếu và lấy một lượt mới; không dựng số ML Kit
  từ số MediaPipe để thay bằng chứng. Chốt nguyên nhân có thể tái hiện trước Task 3.
- [ ] Unit test xanh, commit debug opt-in [APP-01].

## Task 3 — Sửa nguyên nhân đã được chứng minh, từng lỗi một

**Files:** chỉ sửa nơi Task 2 chứng minh lỗi: `capture/Signals.kt`,
`capture/CameraSession.kt`, `capture/FaceTimeline.kt`, `ui/screens/FaceScreens.kt`,
`ml/src/vericlue_ml/presence/landmarks.py` hoặc `gaze.py`.
Tests: `CaptureTest.kt`, `FaceTimelineTest.kt`, `CameraGeometryTest.kt`,
`ml/tests/test_landmark_reader.py`, `test_gaze.py`, `test_head_turn.py`.

**Interfaces:** giữ FaceSignal/ModuleResult và contract hiện có; biến đổi local
phải có test hình học/đồng hồ với oracle độc lập. Không thay dấu/scale vì muốn
khớp riêng bốn clip. HEAD_VERSION/GAZE_VERSION tăng nếu thay semantics server.

- [ ] Chọn một nguyên nhân từ Task 2, ghi bằng chứng và test đỏ trước sửa.
  Nếu không chứng minh được, ghi remaining investigation; không đoán patch.
- [ ] Test `rotatedAndMirroredInputsPreserveSubjectDirections` (nếu lỗi orientation):
  frame/transform tổng hợp có hướng biết trước, đúng subject-left/right;
  không dùng cùng công thức production để tự tạo expected.
- [ ] Test `staleFrameCannotCompleteNewSegmentHold` (nếu analyzer trễ): timestamp
  thuộc đoạn trước không giữ góc đoạn mới; gap/reversed-time/NaN/pitch/roll vẫn warn.
- [ ] Test `test_gaze_preserves_both_axes_and_known_response_lag`: chuỗi tổng hợp
  theo oracle có lag trong cửa sổ hiện tại pass; đứng yên, sai một trục, đường
  của phiên khác, lag ngoài cửa sổ vẫn fail/unclear. Không bỏ trục x.
- [ ] Test `renderedDotUsesServerLinearInterpolation`/t0 mapping nếu lỗi timeline:
  timestamp chấm đúng plan ở đầu/giữa/cuối; callback trễ không tự được coi là
  timestamp first-frame. Không thêm thời gian vào protocol v2 hiện có.
- [ ] Sửa tối thiểu; chạy lại test đúng lỗi rồi toàn các suite liên quan.
  Nếu hai provider góc không thể đồng nhất bằng sửa lỗi tọa độ có chứng cứ,
  đề xuất dùng chung estimator/model và thiết kế bổ sung; không chọn hệ số tùy ý.
- [ ] Giữ tiếng 35/100, ngắn, không NACK chói; cảnh báo không lặp liên tục.
  Gợi ý dùng chữ “Tạm giữ đủ góc, nhìn thẳng” nếu cần tránh hiểu dấu tích là API pass.
- [ ] Commit từng nguyên nhân [APP-01]/[LIVE-02], ghi rõ chưa chứng minh accuracy.

## Task 4 — Các chốt sau chuyển động, không tạo calibrator giả

**Files:** read `presence/session_views.py`, `face/session_attack.py`,
`face/video_match.py`, `face/match.py`, `services/api/.../services/accounts.py`;
tests `ml/tests/test_session_views.py`, `test_video_identity.py`,
`test_session_calibration.py`, `services/api/tests/test_session_calibration_guards.py`.
Update `docs/runbooks/session-face-calibration.md` nếu phát hiện tài liệu sai.

- [ ] Sau prefix pass, kiểm frontal baseline, thứ tự, thời điểm ba view và
  decode chính frame server chọn; lỗi ảnh/selector phải có test hồi quy trước sửa.
- [ ] Tìm artifact/dataset có provenance trong repo và D:/vericlue/data,
  D:/vericlue/tmp/full-demo-setup; trọng số không phải dữ liệu hiệu chỉnh.
  Không quét cả máy, không tải lại hàng chục GB khi chưa biết phần thiếu.
- [ ] Nếu đủ dữ liệu có quyền, đúng protocol/chia theo người/hai lớp: dùng
  `eval.session_calibration collect|fit` theo runbook; kiểm full version/hash/split.
  Không fit trên clip diagnostic, không đổi tên artifact legacy hoặc tự gán nhãn.
- [ ] Nếu thiếu, lập `missing-artifacts.md` local: module/full-version, loại mẫu,
  quyền dữ liệu, split/nhãn/provenance thiếu gì; giữ degraded. Ghi rõ chưa có
  enrollment thật; không tắt guard, bật ACCOUNT_ENROLLMENT hay tự grant SEC-09.
- [ ] Các test missing/wrong/provisional artifact vẫn từ chối. Chỉ ghi DONE
  toàn luồng nếu API thật pass và mọi module bắt buộc có bằng chứng hợp lệ.

## Task 5 — Kiểm tra, giao APK và nghiệm thu hữu hạn

- [ ] Chạy từ apps/android với JAVA_HOME=D:/tools/jdk17:
  `./gradlew testDebugUnitTest assembleDebug`, rồi
  `./gradlew recordPaparazziDebug --tests '*FaceChallengeSnapshotTest*'`.
  CitizenCopyTest/ThemeAccessibilityTest phải xanh; xem ảnh thường/chữ 200%.
- [ ] Từ repo: `uv run pytest ml/tests services/api/tests scripts/tests`;
  nếu runtime uv thiếu model dependency, dùng Python runtime đã có cho cùng
  test, không thay bộ test để che lỗi. Test model thật phải được đánh dấu riêng.
- [ ] `uv run ruff check <các file Python thay đổi>`; `git diff --check`;
  `uv run python scripts/plan_check.py`: 0 lỗi (10 cảnh báo cũ không phải lỗi mới).
- [ ] Snapshot trước/sau, JUnit, reports vào
  `D:/vericlue/tmp/full-demo-setup/presence-stabilization/`; không commit media.
- [ ] Signer APK phải là 822e5e44be42ce365f186a6c73af5bf36eb262c3cc65011b4269363adc695c75.
  Cài -r, không uninstall/clear. Lưu commit/hash/source-dirty đúng thực tế vào
  build-info.json; không ghi commit cũ cho binary mới.
- [ ] Restart server bằng launcher hiện có nếu backend đổi, chờ health ok;
  kiểm ADB devices và reverse 8421. Lỗi auto-review thì ghi rõ, không lách.
- [ ] Tối đa ba lượt nghiệm thu, giữ tất cả kết quả theo attempt. Cần có thứ
  tự trái–phải và phải–trái trong kiểm thử; nếu server chưa sinh đủ order thì
  ghi chưa nghiệm thu order đó, không sửa gói server để hợp thức hóa clip.
- [ ] Kết luận hai dòng độc lập: “mắt/quay đầu: đạt/chưa đạt theo các lượt…”;
  “toàn eKYC/ghi danh: đạt hoặc bị chặn bởi…”. Không nói đạt toàn bộ từ dấu xanh.
- [ ] Bàn giao APP-01 bằng new_handoff.py, cập nhật task card/backlog đúng mức;
  commit local, không push/PR. Tắt trace debug và giải phóng trace RAM khi kết thúc.
