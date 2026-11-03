# Bàn giao · APP-04 · Ngoc Quang+Codex · 2026-11-03 14:09

**Nhánh:** `codex/APP-11-s24fe-integration`
**Trạng thái task sau phiên này:** doing

## Đã xong
- Theo yêu cầu mới: CCCD luôn tự chụp trong phiên còn hiệu lực, không bắt
  người dùng bấm shutter sau 20s/ba lần. Bỏ callback/nút chụp thủ công khỏi UI.
- Scheduler chỉ một capture đang chạy, cần quan sát mới và nghỉ 1/2/4s sau
  lỗi local, 5/10/20s sau retry/upload lỗi; không giới hạn số thử local. Đây là
  giãn nhịp gửi, không bảo đảm tránh hết quota năm lượt server. Lỗi quota/TTL/
  phiên vẫn thoát đúng route, không hồi sinh phiên. Back/Stop/dispose/lỗi
  terminal đóng scanActive ngay; token loại callback trễ. Hint cũ hết sau 3s.
- Preview có chân dung+QR/candidate được thử ảnh tĩnh rõ hơn dù quality hoặc
  tilt ở preview chưa đạt; bốn frame chân dung rõ có thể thử khi chưa thấy QR.
  Chốt ảnh cuối giữ nguyên: QR hợp lệ và đúng một chân dung cùng ảnh mới,
  quality/brightness phải đạt, server đọc lại. Không ghép bằng chứng qua ảnh.
- Khi full-card không thấy QR, thử tối đa hai vùng 65% chiều rộng chồng lấp
  30%, giữ toàn chiều cao cùng bitmap; candidate thật được ưu tiên. Giữ union
  mọi QR để từ chối mã xung đột. Không đổi zoom/focus/resolution/rotation hoặc
  mở crop ngoài vùng đang nhìn thấy. Cleanup đợi cả QR và face kể cả lỗi
  submission đồng bộ, tránh bỏ proxy/bitmap đang được nhánh khác dùng.
- Parser local kiểm tên/ngày sinh/giới tính như server để không tự gửi lặp
  QR chắc chắn bị từ chối. Ngày cấp không hợp lệ tiếp tục là trường tùy chọn.
- Hai agent triển khai tách file, một agent review độc lập; root review thêm
  và bổ sung snapshot test không có shutter ở chữ thường/200%. Review cuối
  không còn blocker. Source tham khảo cho crop retry:
  https://developers.google.com/ml-kit/vision/barcode-scanning/android

## Đang dở
- Full Android test/lint/build đã đạt, APK đã cài lúc 14:14:28 trên S24 FE.
  Nghiệm thu quét CCCD/độ nhạy trên S24 FE còn chờ; không công bố tăng accuracy
  hoặc bảo đảm một lần đưa thẻ là thành công khi chưa đo thật.

## Bước tiếp theo
1. Người dùng thử lại CCCD, xác nhận không xuất hiện nút chụp thủ công và
   quét tự tiếp tục sau lần ảnh chưa đủ; theo dõi thời gian/flags không PII.

## Quyết định, lưu ý, bẫy
- Giữ server `11dfc7e`, GenD **0.95** đang chạy từ bàn giao 13:47. Không đổi
  các ngưỡng khác, không reset thêm tài khoản, không xóa media hay app data.
- Log kỹ thuật thấy rotation90 crop ra ~1079×680; khi đổi rotation có crop
  680×429. Chưa đủ chứng minh lỗi mapping; không sửa hình học theo suy đoán.
- Hành vi stop sau 20s và chụp thủ công trong bàn giao 13:00 đã được yêu cầu
  mới thay thế. Giữ nguyên các điều kiện fail-closed và xác nhận thông tin.

## Câu hỏi cho nhóm
- Chưa có số liệu độ nhạy QR trên nhiều thiết bị/thẻ; cần nghiệm thu thật.

## Test đã chạy
- RED đầu: thiếu scheduler mới (compile-RED). Baseline stub/extraction rồi
  chạy behavior RED: **40 test, 16 fail đúng phần đang sửa**, gồm ba ROI,
  hai UI shutter, scheduler/hints/parser/preview-trigger. Không coi compile
  failure là bằng chứng lỗi hành vi; log behavior riêng giữ ở scratch.
- Full `testDebugUnitTest lintDebug assembleDebug`: **490 test, 489 đạt,
  1 bỏ qua, 0 failure/error**, BUILD SUCCESSFUL (3m58s). Root xem render mới
  cỡ chữ thường/200%; không có shutter, hướng dẫn tự chụp hiện đúng. Ở chữ
  lớn nội dung tiếp tục trong vùng cuộn, không coi render là thử camera thật.
- `plan_check`: 0 lỗi, 10 cảnh báo có sẵn; `git diff --check` sạch.

## Triển khai 14:14 UTC+7
- APK nguồn `cb316ba799a4ef5ad2accdfcafc61a3e1ead033e`, Android tree
  `d906dedc46cca052e8c1592213478a3362a6b52b`, SHA-256
  `8f3128b5f703c7ae65ca25c12a8defe77d6fbb22fed2581ae2dda9d108fb95fc`.
- Signer/v2, trace=false/live=true/signed=true được kiểm; backup APK/build-info
  trước thay. `adb install -r` Success; base.apk trên máy khớp hash. Cài lần
  đầu vẫn 02/11 09:01:50, update 03/11 14:14:28; không clear data/uninstall.
- Lint 0 lỗi, 44 warnings/5 information. Server ready=true,
  failed_modules=[], signed policy attestation đạt; reverse tcp8421 hoạt động.
  Profile vẫn `588ba6c6d8011adbef67df129bd9ab963e24a8b30bba31aa0c53ffd6b553dea6`.
- Chưa có lượt máy thật xác nhận độ nhạy mới; PR giữ draft/chưa merge.
