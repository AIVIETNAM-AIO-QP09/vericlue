# Kiểm tra độ nhạy quét QR trên Android

APP-04/APP-10, cập nhật 03/11/2026. Luồng hiện tại chụp một mặt thẻ có cả
QR và chân dung. Các bước QR riêng/auto-zoom của bản 29/10 đã được thay thế;
không dùng hướng dẫn cũ để nghiệm thu bản một màn.

## Mặc định mới: bộ quét tài liệu

Người dùng chọn ML Kit Document Scanner sau khi camera cũ trên S24 FE có
nhiều frame đủ nét/sáng, thấy chân dung nhưng `qrRead=false`. Đây là quan sát
log kỹ thuật, không phải số đo tỷ lệ thành công.

- Bước CCCD trong luồng API mở giao diện SDK: nhận mép thẻ, tự chụp, xem lại
  ảnh; một trang JPEG, tắt gallery import, chế độ BASE (không filter/clean).
- Giữ nguyên bytes JPEG/EXIF của kết quả, tối đa 10 MiB/16 triệu pixel; server
  đọc cả QR/chân dung cùng ảnh. Không chờ ML Kit QR/face ở preview cũ nữa.
- SDK lần đầu tải mô-đun qua Play services; tối đa 45 giây chờ chuẩn bị rồi
  hiện retry/camera cũ dự phòng. Hủy scanner quay về màn chờ, không tự mở lại.
- Rời màn vô hiệu hóa callback cũ. Một kết quả chỉ gửi một lần; app không
  lưu bản sao JPEG, dọn URI ảnh chụp tạm khi xử lý xong theo quyền provider.
- Google quản lý màn camera/xem lại của SDK; màu/bố cục màn đó ít tùy biến
  hơn UI Compose. Chưa có benchmark chứng minh độ nhạy thẻ thật tăng.

Kiểm SDK sẵn sàng bằng instrumentation đã cài, không mở camera:

```powershell
adb shell am instrument -w -e mode document-scanner-readiness vn.vericlue.app.test/vn.vericlue.app.HeadSpeechProbe
```

Probe kiểm SDK và đọc/dọn JPEG tổng hợp có EXIF trong cache; không bấm đồng ý,
không gửi ảnh hoặc nhận dạng danh tính. Việc quét thẻ thật vẫn do người dùng.

## Camera cũ dự phòng và xử lý server

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
3. Mặc định phải mở bộ quét tài liệu, tìm mép thẻ và cho kiểm tra ảnh trước
   khi gửi. Thử hủy rồi quét lại; hủy không được mở lại camera ngay. Khi SDK
   chưa sẵn sàng, thử nút camera dự phòng. Kiểm tra cả lần đầu tải mô-đun.
4. Riêng camera dự phòng: xem stream YUV trong `dumpsys media.camera` để
   xác nhận kích thước thực. Logcat chỉ lọc `VeriClueCardScan`: kích thước,
   `qrRead`, `portrait`, `sharp`, `glareClear`, `bright`, `elapsedMs`.
   SDK không phát các log preview này; không log payload/ảnh CCCD.
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

## Khi app chưa ghi nhận được đồng ý

`/healthz=ok` chỉ chứng minh server đang chạy. Android hiện đóng gói thông báo
`demo-v1` và `account-template-v1` trong `SessionPrivacyFlow.kt`; GET privacy
của phiên phải trả phiên bản khớp nội dung thực sự hiển thị. Profile local cũ
`PRIVACY_POLICY_VERSION=remote-test-v1` sẽ bị app từ chối dù kết nối tốt.
Với nguyên nội dung demo đang đóng gói, dùng `PRIVACY_POLICY_VERSION=demo-v1`
rồi restart server; người dùng tự bấm đồng ý lại. Không bỏ kiểm phiên bản,
không sao chép tự động phiên bản server vào lựa chọn đồng ý của client.

## Kiểm cả đồng ý và OTP trước khi giao máy thử

Profile local `synthetic` cần bật tường minh `SIMULATED_OTP=true`. Nếu thiếu,
server trả `503 otp_unavailable` khi gửi mã dù health và đồng ý đều thành
công; Android hiện đưa lỗi này vào màn dịch vụ tạm thời chưa sẵn sàng.
OTP này chỉ hiển thị SMS mô phỏng trong app, không gửi SMS thật.

Sau khi restart đúng server, chạy bằng môi trường Python có dependency API:

```powershell
tmp/session-api-runtime/Scripts/python.exe -X utf8 scripts/smoke_android_stage_a.py --run-synthetic
```

Lệnh chỉ gọi loopback 8421, yêu cầu profile synthetic, tạo phiên chẩn đoán
riêng và kiểm đồng ý xử lý + lưu mẫu, OTP sai/đúng, bộ đọc QR thật với ảnh
tổng hợp không có chân dung (phải retry). Phiên chẩn đoán được rút lại sau
kiểm tra, không dùng phiên/dữ liệu hoặc biên nhận của người dùng. Không thay
nghiệm thu camera, chân dung thật hoặc các mô hình xác minh khuôn mặt.

## Căn cứ API

- [CameraController: resolution selector](https://developer.android.com/reference/androidx/camera/view/CameraController#setImageAnalysisResolutionSelector(androidx.camera.core.resolutionselector.ResolutionSelector))
- [ML Kit: vùng QR tiềm năng và auto-zoom](https://developers.google.com/ml-kit/vision/barcode-scanning/android)
