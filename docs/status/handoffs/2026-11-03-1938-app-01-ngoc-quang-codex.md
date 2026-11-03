# Bàn giao · APP-01 · Ngoc Quang+Codex · 2026-11-03 19:38

**Nhánh:** `feat/APP-01-inline-face-login`, nền PR #137 (`1c61e09`).
**Trạng thái task sau phiên này:** doing, cần nghiệm thu máy thật.

## Đã xong
- Quét khuôn mặt trong một Dialog ngay trên màn Login, không đi qua FaceLoginIntro,
  Framing, HoldStill rồi Uploading riêng. Consent rõ ràng bằng nút Đồng ý và quét.
- Preview CameraX cố định giữa chuẩn bị/căn/quay/chờ; không có oval.
  Dùng StableFaceGate + QualityGate đầy đủ; bỏ điều kiện lấp oval thuần bố cục.
- Dùng lại FaceTimelineScreen và FaceAttemptGuard: vẫn quay 3 giây, frontal ở
  500ms; không suy thành công từ animation. Hủy/ra nền dừng camera, bỏ phản hồi
  muộn; Hủy yêu cầu rút consent của session cũ. API giữ quyền quyết định cuối.
- Tách hàm nhận kết quả account để quét inline và luồng voice dùng cùng guard.
  Bổ sung snapshots sáng/tối, font 200%, preview không đổi vị trí giữa các pha.

## Đang dở
- Chưa đo độ trễ đầu-cuối trên thiết bị; không quảng cáo quét tức thời.
- Giữ nguyên các thay đổi chưa commit có sẵn của người dùng trong
  AccountAccessScreens.kt, Theme.kt, AccountAccessSnapshotTest.kt, three-scene.md;
  không đưa các file này hoặc research JSON có sẵn vào commit của task.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Trên thiết bị đã ghi danh: đăng nhập khuôn mặt → đồng ý → nhìn camera → chờ
   API; xác nhận không nhảy màn hoặc phải khớp oval. Thử mặt bị cắt/thiếu sáng,
   rời camera, hủy khi đang gửi và đưa app xuống nền.
2. Đăng ký/khôi phục vẫn dùng luồng đầy đủ; voice escalation khi server yêu cầu.

## Quyết định, lưu ý, bẫy
- Không đổi model, ngưỡng, contract hay thời lượng thu. Việc này giảm thao tác
  và lặp ảnh frontal trước quay; không biến camera VeriClue thành sinh trắc OS.
- Hộp quét vẫn cần đồng ý trước xử lý; không tự lưu đồng ý cho những phiên sau.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Chờ nghiệm thu UX/tốc độ thực; không có quyết định mới cần chặn triển khai.

## Test đã chạy
<!-- lệnh + kết quả thật -->
```
compileDebugKotlin: PASS.
recordPaparazziDebug + lintDebug + assembleDebug (offline, max-workers=1): PASS.
537 tests, 0 failures/errors, 1 skipped; lint 0 errors, 44 warnings.
24 snapshot mới: sáng/tối, font thường/200%, 6 pha; đã xem ảnh quét và consent chữ lớn.
plan_check.py: 0 lỗi, 10 cảnh báo; git diff --check: PASS.
```
