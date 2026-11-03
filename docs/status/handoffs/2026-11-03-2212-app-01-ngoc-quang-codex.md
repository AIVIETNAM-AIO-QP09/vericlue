# Bàn giao · APP-01 · Ngoc Quang+Codex · 2026-11-03 22:12

**Nhánh:** `feat/APP-01-face-login-wait`, nền PR #138.
**Trạng thái task sau phiên này:** doing.

## Đã xong
- Preview inline đã qua StableFaceGate bỏ delay chuyển cảnh 600 ms, mặc định
  các luồng khác giữ nguyên. Không đổi ngưỡng/contract/model/clip hoặc hold.
- Thêm pha Finishing: giữ preview đến khi writer finalize, lấy frame times,
  client quality, regions và probe trước unbind. Sau đó hiển thị vòng chờ trên
  Login, không compose camera trong pha Checking, nút Hủy vẫn có.
- Job gửi dùng khóa submitting chung cho Finishing/Checking để chuyển giao diện
  không hủy HTTP hoặc làm gửi lại. Giữ các guard generation/account/API hiện có.
- Snapshot sáng/tối, chữ 100%/200% kiểm tra camera biến mất lúc Checking, spinner
  xuất hiện, không hiện thành công; các pha thu giữ cùng vị trí preview.
- PR #139 Ready, base #138. APK nguồn `1b35dc0` kèm bảy file UI local có sẵn
  đã cài đè nubia Neo 2 thành công, giữ dữ liệu; đã mở app, không thấy lỗi
  AndroidRuntime trong kiểm tra khởi động. SHA-256 APK trên máy khớp bản ký
  `11de787c4622104ba86b09fd0989d16859c9a7b8ea9332149cb948946745d624`.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- recordPaparazziDebug, lintDebug, assembleDebug đã PASS; chưa nghiệm thu máy.
- Server 8421 hiện tắt; ADB reverse đã nối lại. Chưa kiểm tra lượt đăng nhập
  đầu-cuối hoặc đo thời gian trên thiết bị; cần server và người dùng tự quét.
- Các thay đổi UI/Three.js có sẵn của người dùng không đưa vào commit task.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Cài APK ký cùng chứng thư lên nubia Neo 2, giữ dữ liệu. Người dùng tự quét;
   xác nhận camera đóng trước thời gian gửi/chờ, chỉ kết quả hợp lệ mở hồ sơ.
2. Thử hủy khi chờ và đưa app xuống nền; kết quả muộn không được mở tài khoản.

## Quyết định, lưu ý, bẫy
- Tối thiểu luồng hiện tại còn hold khoảng 1 giây và clip 3 giây cộng thời gian
  khởi tạo/phân tích/finalize. Bỏ 600 ms là bỏ delay được lập trình, không phải
  số đo latency thực tế hay cam kết quét dưới 1 giây.
- Face ID iOS xử lý sinh trắc trên thiết bị. Android BiometricPrompt là phương
  thức khác, chưa được thay cho camera VeriClue người dùng đã chọn.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Nếu mục tiêu dưới 1 giây là bắt buộc: cần thống nhất đổi phương thức xác thực
  thiết bị hoặc có đánh giá riêng cho clip/model ngắn; không tự nới cổng hiện tại.

## Test đã chạy
<!-- lệnh + kết quả thật -->
```
recordPaparazziDebug + lintDebug + assembleDebug: BUILD SUCCESSFUL.
537 tests, 0 failures/errors, 1 skipped; lint 0 errors, 44 warnings.
Đã xem snapshot Checking font 200%: không có preview, có trạng thái chờ và Hủy.
git diff --check: PASS. plan_check.py: 0 lỗi, 10 cảnh báo.
```
