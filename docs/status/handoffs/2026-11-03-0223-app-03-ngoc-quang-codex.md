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

## Lựa chọn ASR đã review, chưa kích hoạt

- Cờ server `MANUAL_DEMO_CONTENT_BACKEND=qwen17` chỉ cho manual full demo;
  mặc định 0.6 giữ nguyên. Phiên bản được kiểm tại worker preload/IPC, snapshot
  phiên mã hóa, quyết định và quyền ghi danh có giọng. Không backfill pin 1.7.
  Hash sáu ngưỡng và account/template/key/device/consent không đổi.
- Adapter cố định đã chuyển từ eval sang voice; eval giữ re-export. Không đổi
  thuật toán suy luận, VAD, prefix, matcher hay YAML model/threshold.
- RED 19 ca ban đầu có 15 lỗi đúng phần thiếu; 229 hồi quy hẹp đạt, 70 ca
  account/auth đạt; sau kiểm containment thư mục có 56 worker/API đạt.
  Các nhóm chồng lặp, không cộng thành một số test độc lập.
- Review độc lập không tìm thấy blocker. Chưa chạy preload thật toàn stack;
  chưa coi lựa chọn mô hình là đã triển khai hoặc recovery đã sửa.
- Root chạy lại selection/session/manual-demo: **92 ca đạt**.
- Đã chép 11 file artifact/giấy phép/provenance được kiểm hash vào thư mục
  1.7B mới ngoài repo; không ghi đè trọng số 0.6B hoặc bật cấu hình.

## Hòa giải main7cb73ba

- Hai nhánh đã chứa cả parent658139f và332dad3; khác biệt còn lại là cách xử
  lý merge. Merge thường có 25 xung đột, đã đối chiếu từng nhóm; giữ trọn các
  sửa PTS/native voice, preview, timeout/ack, schema mode-budget và protocol3
  adaptive hiện có. Không thay bằng toàn bộ bản merge của bên kia.
- Đã lấy hai sửa camera nêu trên. Giữ dải hướng dẫn adaptive hiện có 25…45°
  thay vì đổi sang 16…29° khi server đang yêu cầu tối thiểu20°; không khẳng
  định góc ML Kit tương đương góc server. Giữ timed coaching là gợi ý như trước.
- Giữ bàn giao lịch sử của bạn `2026-11-02-2337-app-11-codex.md`. Bổ sung,
  chuyển 23 trường hợp test có ích sang API protocol3: không mượn artifact
  timed, không trộn calibrator, kiểm account recovery/enrollment và giữ mẫu cũ.
  **Root chạy nhóm 7 file: 198 ca đạt.** Mã Android không đổi so với lượt445 ca
  vừa build. Không thêm workaround mỗi class một tiến trình khi fixture animation
  hiện có đã được kiểm toàn bộ.

## Câu hỏi cho nhóm và giới hạn nghiệm thu

Native frontend lượt đầu dừng ở guard miền pixel. Đã tái hiện bằng ảnh tổng
hợp trắng/đen với phép warp cố định, sửa riêng sai số FP32 dưới0,001 byte
trước cast (byte đầu ra không đổi); không sửa crop/clock/dtype/ngưỡng.
RED4 lỗi đúng guard, root GREEN115 ca. Lượt native lại vẫn cần ghi riêng.

- Còn cần người dùng thử recovery đến kết quả trên S24 FE và xác nhận preview
  thấy đủ mặt. Đăng ký/đăng nhập lại từng có lượt đạt trước; không dùng chúng
  thay nghiệm thu APK mới hoặc toàn bộ giọng.
- OTP mô phỏng, ngưỡng tạm, thiếu hiệu chỉnh/đánh giá tách người với giọng
  thật + TTS/VC có quyền dùng vẫn là việc còn lại. VIVOS32 parity không vào fit.
- Người dùng đã cho phép làm trong đêm và tắt máy; không force đóng tài liệu
  chưa lưu, không tự đánh dấu nghiệm thu hoặc tự mở app/camera.
