# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-03 00:01

**Nhánh:** `codex/APP-11-s24fe-integration`, nền tích hợp `85c8ab4`.
**Trạng thái task sau phiên này:** doing; khôi phục/giọng thật chưa nghiệm thu.

## Đã xong
- Sửa lỗi thao tác có thể tự gửi bản ghi khi người dùng chưa đọc xong: cap
  CameraX từ 8 lên 10 giây, vẫn trong giới hạn decoder 12 giây. UI dùng thời
  lượng native gồm cả chuẩn bị, không chạy lại đồng hồ khi micro sẵn sàng.
- Chỉ gửi sau thao tác “Đọc xong”. Cap native luôn bị từ chối, kể cả khi bấm
  kết thúc trùng lúc; EOF không có xác nhận cũng không decode/gửi. Nút kết thúc
  và đếm ngược cố định phía dưới, có kiểm tra ở cỡ chữ 200%.
- Hết giờ mở thông báo riêng, không báo nhầm thiếu quyền hoặc nói nhỏ. Ghi lại
  local bỏ media cũ và tạo lại màn thu; giữ đúng Voice/VoiceAgain, câu và
  challenge ID, không gọi refresh/reset lượt thử. Server vẫn kiểm expiry/replay.
- Ba subagent chia capture, UI và review độc lập. Giữ generation/cancellation,
  ký MP4/WAV/offset, chuẩn hóa PTS v3, consent và tài khoản hiện có.
- Review giao diện phát hiện câu đọc bị đẩy khỏi vùng nhìn khi chữ 200%; lúc
  chuẩn bị/ghi ưu tiên câu đọc, giữ nguyên cỡ chữ và nút kết thúc cố định.
  Regression dùng câu tổng hợp theo cấu trúc 14 âm tiết, không dùng câu thật.
- Giữ native preview bằng `StableCameraScene` ngoài mọi nhánh trạng thái;
  ẩn thumbnail khi đọc chỉ thay lớp hiển thị. Reset vị trí cuộn lúc bắt đầu
  chuẩn bị để không giữ offset từ màn hướng dẫn. Có test đếm mount/dispose
  xuyên Idle/Preparing/Recording/Finished; review chéo không còn blocker.

## Đang dở
- Lượt thật trước vẫn không đạt nội dung câu và lipsync. Người dùng xác nhận
  đã đọc đủ/đúng; chưa có bản ghi mới trên bản sửa 10 giây để kiểm chứng.
- APK đã build sau kiểm tra toàn Android; triển khai và lượt người dùng ghi
  tiếp sau commit. Chưa coi kết quả kiểm thử là nghiệm thu máy thật.

## Bước tiếp theo
1. Cài APK bằng `install -r`, kiểm signer/hash/flags/reverse8421. Giữ API
   source85c8ab4; cập nhật `apk_source_commit` riêng trong metadata bundle.
2. Người dùng tự mở app thử khôi phục: chờ “Đang ghi âm”, đọc đủ câu, bấm
   “Đọc xong” trước khi hết giờ. Đối chiếu lượt mới với server; chỉ đánh dấu
   nghiệm thu khi toàn luồng và ghi liên kết tài khoản thực sự thành công.

## Quyết định, lưu ý, bẫy
- OTP mô phỏng, AI/ngưỡng demo tạm giữ nguyên. Không bỏ chốt để đạt tối nay;
  error/degraded không thành pass. Không dùng bản ghi nghiệm thu hoặc 32 mẫu
  VIVOS parity để fit/chọn ngưỡng, không đưa câu kỳ vọng vào hotword ASR.
- Đối chứng Qwen trước đó khớp runtime chính thức trên cùng PCM/trọng số nhưng
  vẫn mismatch. Không coi tăng thời lượng là đã giải quyết nguyên nhân ASR.
- Probe riêng SyncNet khớp tính toán các khối với mã gốc trên tensor tổng hợp;
  mẫu frame kiểm tra chưa thấy hai khóe miệng nằm ngoài crop. Đây là chẩn đoán
  kỹ thuật, không phải số độ chính xác báo cáo. Căn mặt/warp upstream vẫn khác;
  chưa có recipe/checkpoint đầy đủ có thể đưa hợp lệ vào sản phẩm.
- Không đổi API/ML/contract/ngưỡng ở bản sửa này. Không restart API chỉ để cài
  APK, không reset/gỡ app/xóa tài khoản hoặc tự mở camera bằng ADB.

## Câu hỏi cho nhóm
- Vẫn cần dữ liệu có quyền sử dụng, chia theo người/nguồn và artifact đúng
  phiên bản cho hiệu chỉnh/đánh giá. Nghiệm thu demo không thay thế việc đó.

## Test đã chạy
- RED có chủ đích: 25 ca, 10 lỗi đúng mục tiêu trước khi sửa production.
- Lượt toàn Android đầu sau sửa: 420 ca, 2 lỗi hoạt ảnh màn thành công,
  1 export skip; các ca mới của voice đạt.
- Chẩn đoán fixture: lớp hoạt ảnh riêng đạt 4 ca nhưng hai lần ghi GIF trong
  cùng test tái hiện RED. Sửa test sở hữu recomposer/main frame clock riêng,
  vẫn Choreographer thật, 1500ms/30fps và assertion tiến độ >=0,99; không đổi
  animation sản phẩm. Focused GREEN 9 ca gồm 5 hoạt ảnh và 4 voice.
- RED chuyển trạng thái màn giọng: 3 ca, 1 lỗi xác nhận native preview bị tháo
  khi chuyển sang chuẩn bị. Các assertion câu tổng hợp dài và thông báo đạt.
  Đây là lỗi review bắt trước triển khai; đã sửa bằng host ổn định nêu trên.
- GREEN toàn Android: `recordPaparazziDebug lintDebug assembleDebug assembleDebugAndroidTest`
  thành công, **422 ca / 0 failure / 0 error / 1 export skip / 84 lớp**.
  Lint **0 lỗi / 44 cảnh báo / 5 thông tin**. Plan check **0 lỗi / 10 cảnh báo**.
- Review PNG thấy một ảnh chữ 200% sau full suite bị dịch phần đầu câu;
  chạy riêng đúng test, source không đổi, ảnh hiển thị đủ câu và assertion đạt.
  Còn nghi ngờ trạng thái render/scroll trong fixture khi chạy chung; không
  suy rằng mọi ảnh full suite đạt trực quan. Cần kiểm màn thật khi nghiệm thu.
  Không thay layout/ngưỡng chỉ để sửa ảnh kiểm thử; phần này được ghi rõ thay
  vì coi ảnh đơn lẻ là bằng chứng toàn luồng.
- Log riêng: `D:/vericlue/tmp/phone-demo-2026-11-02/diagnostics/voice-deadline-*.log`.
