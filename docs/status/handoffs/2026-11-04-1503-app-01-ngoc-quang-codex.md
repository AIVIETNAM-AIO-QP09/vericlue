# Bàn giao · APP-01 · Ngoc Quang+Codex · 2026-11-04 15:03

**Nhánh:** `codex/APP-01-consent-ui-polish`, nền `5f0c1fa`.
**Trạng thái:** doing; phần app tổng thể còn nghiệm thu điện thoại.

## Đã xong
- Theo yêu cầu tiếp theo, gộp hai ô đồng ý ở TermsScreen thành một ô tích tròn.
  Với đăng ký, nhãn nêu rõ cả xử lý xác minh và lưu mẫu khuôn mặt mã hóa trên
  máy chủ trong 24 giờ để đăng nhập lại/khôi phục. Với luồng khác chỉ xin xử lý
  phiên. Giữ nội dung quyền riêng tư đầy đủ và chốt cuộn tới cuối.
- Tích/bỏ tích cập nhật cả hai cờ UI khi onboarding; không tự chọn khi cuộn.
  Agreement, consent API, version và hai biên nhận server vẫn nguyên kiểm tra.
- Test UI mới yêu cầu đúng một checkbox, cuộn không tự đồng ý, tích một lần
  mở tiếp tục, bỏ tích khóa lại. Giữ ca 375×812, chữ 200%, ngang 812×375.
- Xuất ảnh render của điều khoản mới, CCCD, đang gửi và thiết lập tài khoản
  vào thư mục scratch ngoài repo. Ảnh chỉ dùng dữ liệu tổng hợp/minh họa;
  không lấy ảnh CCCD hoặc thông tin thật từ điện thoại.
- Task card giữ bảng metadata ngay dưới heading để plan_check nhận đúng.

## Đang dở
- Chưa cài APK hoặc thử thao tác trên điện thoại; không đổi server/runtime,
  ngưỡng, model/media, tài khoản hoặc hợp đồng API.

## Bước tiếp theo
1. Xem ảnh người dùng và thử trên thiết bị khi cần, giữ dữ liệu/Keystore cũ.
2. Nghiệm thu điện thoại/HTTPS/ba luồng vẫn theo task APP-01 gốc.

## Quyết định, lưu ý, bẫy
- Một lựa chọn UI nêu rõ hai mục đích; không bỏ riêng lời thông báo lưu mẫu.
  Backend vẫn phải cấp đủ hai biên nhận cho onboarding trước khi camera chạy.
- Các ảnh ngoài TermsScreen được xuất từ render kiểm thử của bản nền 5f0c1fa;
  code ba màn đó không thay trong lượt này. Điều khoản được render lại sau sửa.

## Câu hỏi cho nhóm
- Không có câu hỏi mới cho thay đổi đã được người dùng yêu cầu.

## Test đã chạy
- RED: trên code hai ô, ca mới thất bại đúng assertion khóa/đếm một lựa chọn.
- plan_check: 0 lỗi, 10 cảnh báo; diff --check không lỗi.
- Android `testDebugUnitTest` các nhóm ConsentReading, Terms, SessionPrivacy,
  Flow, IdAutomaticScan, UploadPresentation, AccountAccess: 50 tests, 0 failure/
  error/skip. Có màn nhỏ, font200%, ngang và snapshot sáng/tối.
- Đã xuất và xem hai ảnh ghép `01-consent-and-card.png`, `02-upload-and-setup.png`
  ở scratch `ui-review-single-consent`, cùng ảnh từng màn. Điều khoản lấy APNG
  mới sau sửa; ba màn khác là render của code nền không thay đổi.
- `testDebugUnitTest ... lintDebug`: BUILD SUCCESSFUL; lint 0 errors (14 warnings, 8 information). Không cài APK, push hoặc thao tác server.
