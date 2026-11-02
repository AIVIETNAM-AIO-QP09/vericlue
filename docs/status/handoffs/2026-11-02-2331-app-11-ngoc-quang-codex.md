# Bàn giao · APP-11 · Ngoc Quang+Codex · 2026-11-02 23:31

**Nhánh:** `codex/APP-11-s24fe-integration`
**Trạng thái task sau phiên này:** review; chưa nghiệm thu bản tích hợp trên điện thoại.

## Đã xong
- Người dùng yêu cầu xem/cập nhật UI và quét mặt của bạn trong nhóm. Ghép
  PR130 `658139f3cd0a4153e7ec6816dccbcf8f5a6de703` vào nền PR134
  `9291bb53eb3c12cc86f1c8b71bdc3801288dfa5b`, trên nhánh riêng. Chưa merge hai PR trên GitHub.
- Ba subagent chia camera, backend, màn hình/lời nhắc; sau đó review chéo.
  Giữ sửa ghi micro chung MP4, decoder PTS v3, vòng đời finalize, quyền riêng tư,
  hai checkbox đồng ý độc lập, lưu tài khoản trước chuyển trang và nhãn demo.
- UI mới dùng căn mặt/oval và phản hồi từng hướng; adaptive giữ đúng hướng
  650ms qua các frame mới, xác nhận ngắn rồi mới chuyển, trong video tối đa 30s.
  Lời nhắc dùng bộ chống lặp hiện có, không yêu cầu quay cùng bên lần nữa khi
  đang xác nhận. Timed v1/v2 không nhận thêm chốt động tác adaptive.
- Review sửa bẫy merge CameraX: không tăng generation khi dừng lượt hiện tại,
  để Finalize hoàn tất đúng deferred; lượt mới vẫn chặn callback cũ. Probe đọc
  cache nhận cả tên file số cũ và hậu tố generation mới, giữ kiểm thư mục.
- Độ mới kiểm cả sensor timestamp và analyzer timestamp; thời gian giữ/gap
  dựa cảm biến. Độ trễ xử lý không tạo thêm thời gian giữ mặt. Lỗi lấy JPEG
  chính diện chuyển retry; cancellation vẫn được truyền đúng.
- API/ML phân biệt phép đo adaptive với timed: `+session-video-v3-adaptive`,
  `+head-adaptive-v1`. EOF kiểm cả frame cuối ngoài nhịp lấy mẫu; tư thế sai
  ở cuối không được thừa hưởng lần giữ giữa trước đó. Schema bắt cặp mode/budget;
  OpenAPI và type TypeScript được sinh lại. Tài khoản cũ giữ embedding version nền.

## Đang dở
- Mã nguồn đã qua test/lint/build; bước triển khai máy thật ghi bổ sung sau
  khi kiểm server và cài đè thành công.
- Chưa có nghiệm thu máy thật của UI/adaptive mới. Lượt khôi phục thật trước
  vẫn `review`: nhận dạng câu và lipsync chưa đạt; không suy diễn UI mới sẽ sửa
  hai chốt này. Xem bàn giao APP-03 22:50 cùng ngày.

## Bước tiếp theo
1. Sao lưu SQLite và metadata, xuất source đóng băng từ commit đã kiểm.
2. Cập nhật server cùng APK có cùng signer hiện tại; chỉ cài đè giữ dữ liệu.
3. Người dùng tự mở app, thử căn mặt/quay đúng, quay nhầm rồi sửa, giữ giữa cuối;
   theo dõi kết quả thực tế. Không tự mở camera bằng ADB.

## Quyết định, lưu ý, bẫy
- OTP mô phỏng; AI thật với ngưỡng demo tạm, không thay policy/ngưỡng YAML.
  Standard adaptive thiếu artifact riêng phải 503; error/degraded không thành pass.
- Không reset/xóa app, tài khoản, khóa, model hay media. Không dùng mẫu máy thật
  hoặc 32 mẫu parity VIVOS để chọn ngưỡng/fit. Không tuyên bố khôi phục đã đạt.
- Capture route cần camera thật, kể cả đi vào từ gallery; bỏ timer giả lập cũ
  khi thiếu quyền camera. Các ảnh kiểm tra giao diện dùng nội dung tổng hợp.

## Câu hỏi cho nhóm
- Còn cần dữ liệu có quyền sử dụng và chia theo người/nguồn trước hiệu chỉnh;
  việc ghép UI không giải quyết thiếu artifact hay nghiệm thu AI toàn luồng.

## Test đã chạy
- RED Android: 36 ca, 10 assertion fail đúng mục tiêu (6 lời nhắc, 3 thời gian
  camera, 1 tương thích timed); đã sửa sau khi thấy lỗi thật.
- Backend riêng: 248 ML + 189 API đạt; hai tập này không cộng vào test tổng thể
  như số mẫu độc lập. Ruff các file liên quan sạch.
- JSON/API contract: 43 đạt, gồm RED 4 ca mode/budget trước khi bổ sung schema.
- TypeScript typecheck đạt; 6 nhóm kiểm Three.js offline/giảm chuyển động/WebGL đạt.
- `plan_check.py`: 0 lỗi, 10 cảnh báo tải/phụ thuộc có sẵn.
- Tổng thể `python -m pytest -m 'not slow'`: **5087 đạt, 79 bỏ qua,
  25 deselected**, 2 cảnh báo; không phải phép đo trọng số thật/độ chính xác AI.
- Android `recordPaparazziDebug lintDebug assembleDebug assembleDebugAndroidTest`:
  **410 ca, 0 failure/error, 1 export skip, 81 lớp**. Lint **0 lỗi, 44 cảnh báo**;
  hai APK build thành công. Giữ signed media, API localhost8421, live mặc định,
  tắt presence trace. V2 signature đúng signer của app đang dùng.
- Lượt toàn bộ đầu bắt 3 lỗi: footer timed-center chạm oval khi chữ200%, và
  2 ca animation bị ảnh hưởng bởi ComposeView test cũ chưa dispose. Rút gọn
  lời gợi ý tương đương và dọn fixture trong finally; giữ nguyên assertion,
  timing animation, ngưỡng và hình học camera. Lượt toàn bộ sau đạt, review
  trực quan lại center/countdown và các màn đồng ý/demo/success.
- Ruff toàn repo sạch, format17 file Python sạch, OpenAPI `--check` khớp;
  staged diff không whitespace error, không thêm media/dữ liệu/trọng số/bí mật.
