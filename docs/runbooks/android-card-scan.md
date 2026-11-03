# Kiểm tra độ nhạy quét QR trên Android

APP-04/APP-10, cập nhật 03/11/2026. Luồng hiện tại chụp một mặt thẻ có cả
QR và chân dung. Các bước QR riêng/auto-zoom của bản 29/10 đã được thay thế;
không dùng hướng dẫn cũ để nghiệm thu bản một màn.

## Những điểm được sửa

- Yêu cầu ảnh phân tích lớn hơn cho camera quét thẻ, ưu tiên tỉ lệ 4:3 và
  giới hạn 1920×1440; fallback cấu hình mặc định nếu không bind được. Camera
  trước/video mặt không dùng selector này. Kích thước thực do CameraX chọn.
- Hai quan sát QR/candidate mới có thể kích hoạt ảnh tĩnh dù preview chưa
  thấy chân dung; bốn quan sát chân dung rõ cũng được thử khi chưa thấy QR.
  Frame cũ, mã đổi, khoảng cách thời gian quá lâu và retake không cộng dồn.
- Ảnh tĩnh dùng ML Kit `ACCURATE` để tìm chân dung nhỏ, preview vẫn `FAST`.
  Không tự zoom làm mất mép thẻ. Ảnh upload giữ crop đúng vùng nhìn thấy.
- Ảnh tĩnh đạt chất lượng và có dấu hiệu QR/chân dung có thể gửi server đọc
  phần còn thiếu. Không dùng QR cache; ảnh local chưa đủ cả hai không gửi QR
  text nên server mock không thể chấp nhận bằng dữ liệu local thiếu.
- Chưa tìm được chân dung thì không dùng tỷ lệ pixel trắng của toàn thẻ để
  chặn ảnh gửi đọc lại: nền thẻ trắng không đồng nghĩa lóa chân dung. Vẫn
  kiểm nét/sáng; nếu đã tìm thấy chân dung, giữ kiểm lóa trên vùng chân dung.
- Server thật quét một mặt phải giải mã QR và thấy chân dung trên ảnh gốc.
  Khi QR chưa đọc được, thử hai vùng chồng lấp và tối đa hai tứ giác thẻ nắn
  phối cảnh. Không ghép ảnh, không suy đoán chữ, không bỏ QR xung đột.
- Nắn phối cảnh chỉ giúp đọc QR; SCRFD vẫn kiểm chân dung trên ảnh gốc.
  Offline cần đủ bằng chứng local. Không tăng quota upload hoặc bỏ TTL;
  ảnh đọc chưa được vẫn hướng dẫn chỉnh và tự thử lại có khoảng nghỉ.

Không đổi định dạng API, trọng số, ngưỡng sinh trắc hoặc thêm OCR/WeChatQRCode.
Chưa có benchmark điện thoại chứng minh mức tăng độ nhạy.

## Nghiệm thu

1. Dùng cùng APK/package/khóa ký, giữ ADB Wi-Fi, reverse 8421 tới server.
2. Chọn API thật và bắt đầu phiên mới. Người dùng tự đồng ý và cung cấp ảnh;
   không điền/tick hộ hoặc ghi hình CCCD thật vào repo/log.
3. Khi mở camera thẻ, xem stream YUV trong `dumpsys media.camera` để xác nhận
   kích thước thực. Selector là yêu cầu, không đảm bảo mọi máy chọn cùng size.
4. Logcat chỉ lọc `VeriClueCardScan`: xem kích thước, `qrRead`, `portrait`,
   `sharp`, `glareClear`, `bright`, `elapsedMs`. Không log payload/ảnh.
5. Test thẻ có QR cùng mặt chân dung. Che QR, che chân dung, đưa hai thẻ:
   không được sang xác nhận thiếu bằng chứng. Đổi thẻ/retake không dùng lại
   dữ liệu cũ. QR ở mặt khác chưa thuộc luồng một ảnh này.
6. Giữ QR hơi xa/gần, lệch nhẹ, ánh sáng khác nhau; ghi kết quả trung thực.
   Không đặt tỷ lệ thành công hoặc thời gian cải thiện khi chưa đo.

Kiểm chuyển sang camera trước và video mặt sau QR, đặc biệt zoom trở về 1×.
Hardware acceptance cần ghi riêng trong bàn giao; unit/snapshot không thay
thế kiểm camera hoặc đọc QR thật trên thiết bị.

Triển khai API và Android cùng bản; máy chủ cũ chưa có đường nắn phối cảnh
và có thể còn cấu hình chân dung tùy chọn. Bắt đầu phiên mới khi nghiệm thu.

## Căn cứ API

- [CameraController: resolution selector](https://developer.android.com/reference/androidx/camera/view/CameraController#setImageAnalysisResolutionSelector(androidx.camera.core.resolutionselector.ResolutionSelector))
- [ML Kit: vùng QR tiềm năng và auto-zoom](https://developers.google.com/ml-kit/vision/barcode-scanning/android)
