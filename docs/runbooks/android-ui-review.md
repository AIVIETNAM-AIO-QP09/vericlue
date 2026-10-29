# Xem giao diện đăng ký Android sau cập nhật APP-09

Ảnh lấy trực tiếp từ Jetpack Compose bằng Paparazzi, không cần máy ảo,
điện thoại, camera, server hoặc model. Dữ liệu, ảnh camera và mã xác nhận
trong ảnh đều là minh họa. Đây là kiểm tra giao diện, không phải nghiệm thu
QR/AI/kết nối hoặc tương tác trên thiết bị thật.

## Render và xuất bộ ảnh

Chuẩn bị JDK 17, Android SDK theo README Android rồi chạy:

```powershell
cd apps/android
.\gradlew.bat recordPaparazziDebug --tests '*OnboardingJourneySnapshotTest'
cd ../..
uv run python scripts/export_android_ui.py --output tmp/vericlue-ui-review
```

Mở `tmp/vericlue-ui-review/index.html`. Các PNG đã đánh số nằm trong thư mục
con; bấm ảnh để xem kích thước gốc. ZIP nằm cạnh thư mục xuất. `manifest.json`
ghi commit, trạng thái thay đổi source UI và hash nguồn/ảnh. Không commit ảnh
camera/căn cước thật, dữ liệu, khóa hoặc file build.

Bộ ảnh tách luồng chính, nhánh bổ sung và lỗi; mỗi nhóm có sáng/tối. Có các
màn trọng yếu ở 375dp, cỡ chữ hệ thống 200% và bố cục ngang để tìm lỗi.
Activity vẫn khóa dọc. Màn dài được cuộn trong app; PNG là một khung nhìn,
không phải ảnh ghép toàn bộ nội dung ngoài màn hình.

## Luồng dùng để review

1. Mở VeriClue → chọn đăng ký → đồng ý xác minh.
2. Số điện thoại → mã xác nhận (OTP demo được ghi rõ).
3. Quét mặt có chân dung → đọc thông tin. Nếu chưa đọc được QR, mới yêu cầu
   mặt có QR; thiếu chân dung/QR sai hoặc lỗi mạng không được coi là đã xong.
4. Kiểm tra/chỉnh sửa → xác nhận thông tin trước khuôn mặt.
5. Chuẩn bị → căn mặt → giữ yên/ánh sáng → ánh mắt → quay đầu theo lịch phiên.
6. Chờ kết quả. Chỉ đọc câu nếu API yêu cầu; chỉ `pass` mới mở thành công.

Thứ tự quay đầu trong ảnh là ví dụ; lịch thật lấy từ server. Gallery debug
vẫn phục vụ xem UI; các màn minh họa không chứng minh kết quả AI.

## Những thay đổi cần chú ý

- Đồng ý không tick sẵn, không buộc cuộn hết, chi tiết mở trong cùng vùng
  cuộn. Loại dữ liệu có cả mẫu khuôn mặt mã hóa và giọng nói khi cần.
- Bỏ tùy chọn lưu trữ chưa có hiệu lực, lời hứa thời hạn/SMS/nhân viên và
  thông báo đã mở tài khoản hoặc đã kiểm giọng nói khi chưa được API xác nhận.
- Giữ cảnh báo nháy sáng, cấp quyền, gợi ý chất lượng, lỗi và lối dừng.
- Nút tăng chiều cao theo chữ. Kết quả/lỗi vẫn cuộn được khi thiếu chiều cao;
  nút ghi âm nằm trong vùng thao tác cố định.
- Một package `vn.vericlue.app`, cùng API 8421. Không tạo app/server mới.

Giới hạn: đồng ý hiện là trạng thái UI, chưa tích hợp receipt đồng ý với
backend. Không thay cờ/chốt backend để né việc này. Không nghiệm thu pháp lý,
TalkBack, camera, xử lý ảnh hoặc quay/ghi âm liên tục chỉ bằng PNG.
