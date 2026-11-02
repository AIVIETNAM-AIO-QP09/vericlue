# Bàn giao · APP-03 · Ngọc Quang+Codex · 2026-11-03 02:23

**Nhánh:** `codex/APP-11-s24fe-integration`
**Trạng thái:** `doing` — khôi phục/giọng thật chưa nghiệm thu.

## Đã xong

- APK03b4abc đã cài giữ dữ liệu; server85c8ab4 đã dừng để đo offline khi người
  dùng đi ngủ. Bàn giao `2026-11-03-0128` ghi số đo ASR và triển khai trước đó.
- Đối chiếu PR130 đã merge lên main7cb73ba: thêm hai điểm còn thiếu ở camera.
  JPEG phải có timestamp chụp sau yêu cầu, không chỉ timestamp giao callback.
  Trace adaptive lấy hướng từ mốc hướng dẫn thực tế ở thời điểm chụp.
- Giữ các sửa giọng/PTS/preview/chờ AI/phản hồi có sẵn. Giữ local coaching
  timed là gợi ý với kiểm server bắt buộc; luồng live dùng adaptive có kiểm
  pose/hold. Đây là lựa chọn tích hợp có chủ đích, không tuyên bố hai nhánh
  tương đương hoàn toàn. Chưa merge graph tại thời điểm ghi mục này.
- Sinh lại notebook GenD bằng builder sau thay đổi tham số SCRFD; commit
  `c8e1318` theo sau frontend offline `ef4838a`.

## Test đã chạy

- Camera RED: 10 ca, 3 assertion failure đúng các trường hợp cần sửa.
- Camera GREEN và toàn Android: `recordPaparazziDebug lintDebug assembleDebug
  assembleDebugAndroidTest`, flags signedMedia/liveByDefault=true,
  presenceTrace=false: **445 ca, 0 failure/error, 1 export skip, 89 lớp**.
  Lint **0 lỗi, 44 cảnh báo, 5 thông tin**; APK và APK test build thành công.
- Python tổng lượt đầu: 5.268 đạt, 89 skip, 25 deselected, 5 lỗi. Một lỗi
  notebook GenD lệch nguồn đã sửa bằng builder; bốn CLI lỗi vì root dùng
  PYTHONPATH tương đối khiến subprocess ở thư mục tạm nạp checkout D:/vericlue.
  Đổi PYTHONPATH tuyệt đối và chạy lại nhóm liên quan: **16 đạt, 1 skip**.
  Không sửa test để che lỗi. Phải chạy lại tổng sau khi chốt thay đổi ASR.

## Đang dở và bước tiếp theo

1. Review độc lập lựa chọn Qwen1.7B manual-only, kiểm phiên bản riêng và giữ
   nguyên hash sáu ngưỡng/tài khoản; chưa bật cấu hình server.
2. Smoke frontend file trên bản ghi cũ đã chọn cố định theo khoảng cài APK.
   Lượt đầu dừng lỗi, chưa có kết quả so sánh hoàn chỉnh; đang kiểm nguyên nhân.
   Không dùng kết quả bản ghi để chọn ngưỡng/crop/dtype hoặc tuyên bố accuracy.
3. Chốt commit, hòa giải main, chạy kiểm thử tổng; chỉ triển khai bản đã qua
   review/check thực tế. Giữ DB/khóa/media và chốt lỗi/degraded.
4. Lưu bàn giao cuối, dừng tiến trình thử, tắt máy theo yêu cầu người dùng.
   Lần mở máy sau chạy `D:/vericlue/tmp/phone-demo-2026-11-02/START-DEMO.cmd`.

## Câu hỏi cho nhóm và giới hạn nghiệm thu

- Còn cần người dùng thử recovery đến kết quả trên S24 FE và xác nhận preview
  thấy đủ mặt. Đăng ký/đăng nhập lại từng có lượt đạt trước; không dùng chúng
  thay nghiệm thu APK mới hoặc toàn bộ giọng.
- OTP mô phỏng, ngưỡng tạm, thiếu hiệu chỉnh/đánh giá tách người với giọng
  thật + TTS/VC có quyền dùng vẫn là việc còn lại. VIVOS32 parity không vào fit.
- Người dùng đã cho phép làm trong đêm và tắt máy; không force đóng tài liệu
  chưa lưu, không tự đánh dấu nghiệm thu hoặc tự mở app/camera.
