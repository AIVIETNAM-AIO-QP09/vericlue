# Bàn giao · APP-01 · Ngoc Quang+Codex · 2026-11-04 14:40

**Nhánh:** `codex/APP-01-consent-ui-polish`, nền hợp nhất `b4fafb7` (PR136–140).
**Trạng thái task sau phiên này:** doing, còn nghiệm thu điện thoại.

## Đã xong
- Theo thiết kế người dùng đã chốt: nội dung quyền riêng tư luôn hiện trong
  một màn cuộn; tới cuối mới mở lựa chọn. Không tự tích hoặc gửi consent.
- Hai lựa chọn xử lý/lưu mẫu độc lập, điều khiển vẫn có semantics Checkbox
  nhưng hình tròn có dấu tích. Chữ 13sp theo cỡ chữ hệ thống, hit area >=48dp.
- Giữ rõ hạn lưu mẫu 24 giờ, mã hóa và việc dừng phiên không tự xóa tài khoản.
  Không đổi phiên bản consent gửi API, loại dữ liệu hay backend.
- QR đang tìm đổi thành Đang trích xuất thông tin; chân dung cũng dùng nhãn
  Đang trích xuất chân dung. Không sửa bộ đọc/chụp/chốt bằng chứng.
- Gửi dữ liệu dùng biểu tượng tải lên và thanh chờ xanh, bỏ vòng cầu vồng và
  thẻ chữ lặp. Không tạo phần trăm hay hoàn thành giả. Khi giảm chuyển động,
  giữ thanh tĩnh với semantics tiến độ indeterminate. Nút dừng vẫn hoạt động.
- Bỏ nhãn demo/ngưỡng trên các màn người dùng và mã version kỹ thuật khỏi
  chữ quyền riêng tư. Thời hạn thực tế và cảnh báo preview không chạy AI còn giữ.
- Subagent review read-only không thấy finding có thể hành động; không chạy
  Gradle song song hoặc tác động server/điện thoại.

## Đang dở
- Chưa cài APK hoặc nghiệm thu trên điện thoại. Kiểm tra UI không chứng minh
  accuracy/hiệu chỉnh của AI. Ngưỡng, mode/hash, API và chốt lỗi không đổi.

## Bước tiếp theo
1. Thử cuộn thông tin tới cuối rồi tự chọn hai ô; kiểm tra nút tiếp tục và trạng
   thái đang gửi trên thiết bị, kể cả chữ lớn, đổi hướng và mất mạng.
2. APP-01 vẫn còn các tiêu chí điện thoại/HTTPS/ba luồng của task gốc.

## Quyết định, lưu ý, bẫy
- Chốt đọc hết kiểm trạng thái đã đo layout trước khi mở lựa chọn, tránh
  maxValue ban đầu. Nhớ việc đã đọc riêng từng purpose; busy khóa thao tác.
- Bỏ chữ demo là thay trình bày theo yêu cầu, không chuyển cấu hình thành
  production hoặc xác nhận ngưỡng đã được hiệu chỉnh bằng dữ liệu.
- Không sửa STATUS, contract, model/media, tài khoản, server hoặc thiết bị.

## Câu hỏi cho nhóm
- Không có quyết định mới cần chốt cho phần trình bày đã duyệt.

## Test đã chạy
- RED: test cuộn/chọn mới thất bại trên code cũ với assertion
  Choices and continue are locked before reading (đúng hành vi còn thiếu).
- plan_check.py: 0 lỗi, 10 cảnh báo sẵn có.
- Android full suite `testDebugUnitTest lintDebug`: BUILD SUCCESSFUL, 552 tests,
  0 failures/errors, 1 skipped (551 pass). Lint: 0 errors, 14 warnings, 8 information.
- Chạy bổ sung `testDebugUnitTest --tests '*ConsentReadingSnapshotTest'
  --tests '*UploadPresentationSnapshotTest'`: BUILD SUCCESSFUL, 6/6 pass,
  gồm màn nhỏ 375×812, chữ 200% và ngang 812×375. Không chạy Gradle song song.
- Đã xem ảnh đầu/cuối điều khoản, hai ô chọn và CTA ở chữ thường/200%,
  cùng ảnh gửi dữ liệu cả hai cỡ chữ. Chế độ hệ thống sáng/tối được render;
  repo hiện chủ động dùng cùng theme navy cho cả hai.
- Tất cả Gradle dùng JDK17, SDK D:/tools/android-sdk, offline, max-workers=2,
  API localhost8421, signedMedia/liveByDefault=true, presenceTrace=false.
- `git diff --check`: PASS. Subagent review không có finding cần xử lý.
- Không build/cài APK hoặc push trong phiên này.
