# Bàn giao · APP-01 · Ngoc-Quang+Codex · 2026-10-31 07:38

**Nhánh:** `codex/APP-01-demo-integration` (nền `5afd9da`)
**Trạng thái task sau phiên này:** doing — hoàn thiện hướng dẫn, chưa nghiệm thu toàn luồng AI thật

## Đã xong
- Bước tập local trái/giữa/phải, chưa chuẩn bị challenge, ghi hình hoặc gửi API;
  bỏ qua chỉ bỏ phần tập. Luồng reauth thụ động giữ nguyên.
- Oval mảnh, scrim nhẹ, mũi tên chỉ hiện khi cần quay. Chữ lớn/375dp vẫn có nút tiếp tục.
- TTS đọc câu Việt cố định; ưu tiên offline qua các engine có sẵn, chỉ thử mạng
  sau khi tìm offline không thành. Không tự tải hay đổi engine hệ thống.
- Bíp nhỏ khác nhau cho quay/giữ/nhìn thẳng; cue quan trọng có bíp ngay cả khi TTS
  khởi động chậm. Dừng âm khi đổi trạng thái, ra nền hoặc thoát màn.
- Sửa mất lời Hold khi góc dao động warning → Hold → warning bị throttle → Hold;
  lời cảnh báo cũ dừng và lần trở về Hold vẫn có nhắc. Có test hồi quy.
- Review lại policy/TTS: không còn phát hiện critical/important cần xử lý.
- GitHub đã fetch: main `7fc2ce9` đã nằm trong nhánh local. PR #116 (ONNX FP32),
  #117 (GenD FP16) là công cụ export/đo; không sửa head/gaze runtime hay cấp artifact
  video-v2. Không merge/cherry-pick, không push/PR.

## Đang dở
- Nghiệm thu người thật với bản APK cuối; callback TTS im lặng không chứng minh
  âm nghe rõ, app–server chấm đạt hoặc toàn luồng đã hoàn tất.
- Artifact hiệu chỉnh/đánh giá PAD/GenD/danh tính video-v2 và lưu mẫu SEC-09 còn thiếu.

## Bước tiếp theo
1. Theo `docs/runbooks/head-turn-coaching.md`, mở một lượt mới, tập rồi xác minh.
2. Nếu còn retry/review, đối chiếu đúng attempt bằng runbook diagnostics; không
   nới ngưỡng/ép pass hay coi đoạn tập là bằng chứng xác minh.

## Quyết định, lưu ý, bẫy
- Không đổi lịch quay/video, API, ML, contracts, ngưỡng hay camera CCCD/iOS.
- Lượt chẩn đoán 23:36 ngày 30/10: mắt đạt; đầu có126 mẫu hợp lệ, yaw57,1°;
  app đã Warn. Không dùng mẫu chẩn đoán để chứng minh độ chính xác tổng quát.
- Người dùng hủy yêu cầu tắt máy sáng31/10: đã gỡ task Windows; không hẹn lại.
- Bằng chứng local: `D:\vericlue\tmp\full-demo-setup\head-coaching\`;
  APK giao: `D:\vericlue\tmp\full-demo-setup\apk\VeriClue-demo-debug.apk`.

## Câu hỏi cho nhóm
- Tiếp tục cung cấp artifact đúng version và nghiệm thu điện thoại; chưa có bằng
  chứng để đóng toàn bộ APP-01/tài khoản thật. Không phát sinh quyết định ngưỡng.

## Test đã chạy
```
TDD: 7 HeadGuidanceTest, 3 failed trước fix (Hold reentry và offline engine search).
testDebugUnitTest assembleDebug assembleDebugAndroidTest -Pvericlue.presenceTrace=true:
BUILD SUCCESSFUL; 192 tests, 0 failures/errors/skipped (gồm CitizenCopy/ThemeAccessibility).
Native: install -r app + test APK Success, đúng signer822e5e44…;
offline_vietnamese=true/network_required=false ở hai lần probe.
Callback im lặng lần đầu false, lần chạy lại true. Có giới hạn cold start,
không coi lần thứ hai là chứng minh mọi lần đều đọc kịp. Xem hai log completed-native*.
Paparazzi lượt đầu: 18 tests, 1 failed (SmallFaceChallengeSnapshotTest.allFacePhases,
FileAlreadyExistsException khi ghi đè PNG). Chạy lại riêng sau khi dừng đọc/copy ảnh;
không sửa test hay giao diện để che lỗi file.
Paparazzi chạy lại: BUILD SUCCESSFUL, 18 tests/0 failures/errors; 63 ảnh phần mặt
(9 ảnh tập mới) cùng ScreensSnapshotTest. Đã xem màn giữ/tập chữ200%, nút không
bị cắt. So ảnh local tại head-coaching/comparison.html (trái trước/phải sau).
Launcher API lần đầu quá hạn120s lúc nạp model sau mở máy; lần khởi động lại
thành công cổng8421. Đã nối adb reverse. OTP vẫn mô phỏng; không đổi cấu hình model.
plan_check.py: 0 lỗi, 10 cảnh báo kế hoạch có sẵn; git diff --check sạch.
```
