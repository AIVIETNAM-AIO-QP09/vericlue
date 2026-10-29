# Kiểm tra độ nhạy quét QR trên Android

APP-10 xử lý phản hồi của người dùng trên nubia Neo 2 ngày 29/10/2026. Trước
bản sửa, stream phân tích đo qua `dumpsys media.camera` là ImageReader 640×480
(format YUV). Đây là quan sát cấu hình, không phải số đo độ chính xác QR.

## Những điểm được sửa

- Yêu cầu ảnh phân tích lớn hơn cho camera quét thẻ, ưu tiên tỉ lệ 4:3 và
  giới hạn 1920×1440; fallback cấu hình mặc định nếu không bind được. Camera
  trước/video mặt không dùng selector này. Kích thước thực do CameraX chọn.
- Bước chỉ lấy QR không chờ thêm face detector. ML Kit hỗ trợ vùng QR tiềm
  năng và gợi ý zoom; chỉ cho phép zoom ở bước QR, tối đa 3× và không vượt
  giới hạn thiết bị. Bước chân dung cần giữ toàn thẻ nên không tự zoom.
- Hai lần đọc QR khớp trong cửa sổ ngắn có thể xen khung chưa đọc được. Đổi
  mã, quá hạn, frame cũ hoặc retake không được hoàn thành lượt trước.
- Phản hồi đã đọc giữ 1,5 giây, độc lập với điều kiện chụp. Không lấy QR cache
  cho ảnh mới. Ảnh tự chụp ở bước QR phải được giải mã lại trên đúng bitmap.
- QR đã giải mã từ pixel được coi là đọc được, dù toàn ảnh có nhiều điểm trắng
  hoặc nền mờ. Không dùng heuristic toàn khung để chặn mã đã đọc thành công.
  Bước chân dung vẫn giữ kiểm chất lượng cũ; server giữ kiểm QR/ảnh độc lập.

Không đổi định dạng API, model, ngưỡng ML, OCR hoặc tạo app/server mới.

## Nghiệm thu

1. Dùng cùng APK/package/khóa ký, giữ ADB Wi-Fi, reverse 8421 tới server.
2. Chọn API thật và bắt đầu phiên mới. Người dùng tự đồng ý và cung cấp ảnh;
   không điền/tick hộ hoặc ghi hình CCCD thật vào repo/log.
3. Khi mở camera thẻ, xem stream YUV trong `dumpsys media.camera` để xác nhận
   kích thước thực. Selector là yêu cầu, không đảm bảo mọi máy chọn cùng size.
4. Logcat chỉ lọc `VeriClueCardScan`. `candidate` là có vùng nghi QR, `decoded`
   là có dữ liệu giải mã, `qrRead` là qua bộ lọc QR/khung; các cờ quality giúp
   tách chưa đọc được với đang bị chặn điều kiện chụp. Không log payload/ảnh.
5. Test thẻ có QR cùng mặt chân dung và QR ở mặt khác. Xem lại thông tin; đổi
   thẻ/retake không được lấy lại dấu đọc hoặc dữ liệu cũ.
6. Giữ QR hơi xa/gần, lệch nhẹ, ánh sáng khác nhau; ghi kết quả trung thực.
   Không đặt tỷ lệ thành công hoặc thời gian cải thiện khi chưa đo.

Kiểm chuyển sang camera trước và video mặt sau QR, đặc biệt zoom trở về 1×.
Hardware acceptance cần ghi riêng trong bàn giao; unit/snapshot không thay
thế kiểm camera hoặc đọc QR thật trên thiết bị.

## Căn cứ API

- [CameraController: resolution selector](https://developer.android.com/reference/androidx/camera/view/CameraController#setImageAnalysisResolutionSelector(androidx.camera.core.resolutionselector.ResolutionSelector))
- [ML Kit: vùng QR tiềm năng và auto-zoom](https://developers.google.com/ml-kit/vision/barcode-scanning/android)
