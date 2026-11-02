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
- APK `1840ede720a4c3edaf3e518957b1bd6312dc57e2` đã cài đè S24 FE lúc 00:29
  ngày 03/11, hash/signer/reverse8421 khớp. API vẫn source85c8ab4, cấu hình
  riêng và toàn bộ hàng tài khoản/khôi phục không đổi sau cài. Kết quả người
  dùng sau đó ghi ở mục nghiệm thu bên dưới; khôi phục vẫn chưa đạt.

## Bước tiếp theo
1. Người dùng tự mở app thử khôi phục: chờ “Đang ghi âm”, đọc đủ câu, bấm
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
- Công cụ xem PNG từng hiển thị phần đầu câu bị che không nhất quán. Kiểm
  metadata cho thấy ảnh từ lượt chung/riêng khớp; đọc pixel trực tiếp bản sao
  đường dẫn ngắn xác nhận thẻ câu nằm dưới top bar (375×812, màu thẻ ở x30 bắt
  đầu y84). Reviewer rút lại nhận định clipping; chưa có bằng chứng lỗi render
  sản phẩm. Không sửa layout/compositing theo ảnh hiển thị sai lệch. Đường dẫn
  snapshot dài hơn 260 ký tự làm Python trên máy này báo không tồn tại; sao
  chép bằng PowerShell sang đường dẫn ngắn rồi kiểm, không xóa file gốc.
- Triển khai: giữ signer cũ/v2, signed media/live mặc định bật, presence trace
  tắt, APK đang cài có SHA256 khớp artifact; dữ liệu app giữ nguyên và không
  gọi ADB mở app/camera. Đây không phải bằng chứng các chốt AI đã đạt.
- Log riêng: `D:/vericlue/tmp/phone-demo-2026-11-02/diagnostics/voice-deadline-*.log`.

## Lượt thật sau cài APK1840ede và sửa preview tiếp theo

- Lượt đầu có retry local vì hết ngân sách quay đầu, chưa gửi server. Sau
  retry, head_turn đạt nhưng gaze_tracking degraded/E_LOW_QUALITY với lý do
  `head_not_still`; API review trước giọng. Đây là kết quả ước lượng tư thế,
  không kết luận người dùng thao tác sai. Không thay thời gian/ngưỡng để qua.
- Lượt khôi phục tiếp theo đã qua bảy chốt mặt/mắt/quay đầu, gửi được giọng
  khi bấm kết thúc. Voice spoof và continuity đạt; voice_challenge báo
  E_CHALLENGE_MISMATCH, lipsync không đạt, API review và không ghi recovery binding.
  Tài khoản còn nguyên. Nội dung vẫn khớp đúng challenge hiện tại, không có
  dạng chuỗi chữ số gộp trong ASR để giải thích bằng lỗi chuẩn hóa số.
- Người dùng báo ô camera màn đọc như bị zoom, không thấy mặt. Root cause:
  host full-window được giữ ổn định nhưng thumbnail chỉ là cửa sổ cắt, chưa
  ánh xạ lớp vẽ. Sửa bằng FIT đồng dạng theo hai khung đo trong cùng tọa độ
  gốc, trừ origin của scene; dùng size đầy đủ, không dùng bounds bị clip khi
  cuộn. Native host vẫn gắn/kích thước cố định, không đổi zoom/capture/AI.
- RED preview: 4 ca, 3 lỗi đúng mục tiêu (2 phép ánh xạ, 1 pixel marker giữa
  viewport không xuất hiện trong thumbnail). Lần đầu fixture không compile
  vì Android bootclasspath không có AWT; đó không tính là RED hành vi. Fixture
  đọc RGB qua reflection từ ảnh renderer rồi giữ assert nội dung thật.
- GREEN cuối preview: **426 ca / 0 failure / 0 error / 1 export skip / 86 lớp**;
  lint **0 lỗi / 44 cảnh báo / 5 thông tin**, hai APK build thành công. Plan check
  **0 lỗi / 10 cảnh báo**. Hai fixture GIF mới cần sở hữu frame clock/recomposer
  riêng: từng test không đổi đều đạt khi chạy riêng nhưng lỗi khi chạy chung.
  Giữ nguyên thời lượng, assertion scroll/host và RGB, không bỏ kiểm tra.
- Đối chứng âm thanh riêng, cùng cặp MP4/WAV của lượt này: giải mã AAC độc lập,
  resample và ánh xạ PTS cho dạng sóng gần trùng ở độ trễ 0. Chưa có bằng chứng
  Android chuẩn hóa làm hỏng đáng kể bản thu này. Không phải kiểm định clock
  vật lý, chất lượng âm học hay độ chính xác AI. Không đổi PCM/offset theo điểm
  AI; report và media lease chỉ nằm riêng, không đưa dữ liệu sinh trắc vào Git.
- Kiểm tra khả năng so sánh ASR tiếp: DNU đã có WAV kèm nhãn và split theo người;
  chưa có dữ liệu A/V tương ứng cho khớp môi. PhoWhisper-small đã tải riêng theo
  manifest pinned có sẵn và kiểm SHA, chỉ là ứng viên, chưa đánh giá hay cài API.
  Qwen1.7 chưa có artifact tại máy. Chọn model phải đánh giá trên
  calib_fit, khóa trước đánh giá; không chọn bằng các lượt điện thoại này.
- APK preview `b578195bfaa1404882a0f98a56cfe124edf01c75` đã cài đè S24 FE
  lúc 01:03 ngày 03/11 (18:03 UTC ngày 02/11). Hash APK đang cài khớp artifact,
  giữ signer cũ, reverse8421 hoạt động; toàn bộ hàng tài khoản/khôi phục và
  cấu hình riêng không đổi. API85c8ab4 vẫn healthz=ok, failed_modules rỗng.
  Người dùng được mời thử lượt cuối; chưa ghi nhận nghiệm thu camera hoặc
  khôi phục toàn luồng cho bản này. Không tự mở app/camera bằng ADB.

## Lỗi chờ phản hồi sau bản preview

- Người dùng báo “Chưa thể kết nối”. ADB/reverse8421 còn hoạt động và API
  healthz=ok. Hai phiên mới đều qua đủ bảy chốt mặt, server yêu cầu giọng;
  chưa có media giọng hay recovery binding trong hai phiên này.
- Lượt đầu ghi PAD khoảng 50,1 giây trong nhóm song song, sau đó FACE_MATCH
  chạy riêng khoảng 11,8 giây: riêng hai giai đoạn đã hơn 61,9 giây. Android
  đang đặt read timeout 60 giây và gom IOException vào màn lỗi mạng. Đây là
  thời gian xử lý thật của lượt chẩn đoán, không phải benchmark hiệu suất.
- Server có deadline suy luận chung tối đa 90,8 giây. Bản sửa giới hạn riêng
  phản hồi finalize/voice ở 120 giây; các endpoint thường vẫn 60 giây,
  connect 15 giây và write 60 giây. Không đổi deadline server, chốt xác minh,
  hợp đồng hay phát lại tự động các POST đã được tiếp nhận.
- Không hướng dẫn bấm gửi lại finalize của phiên cũ: server đã yêu cầu giọng
  thì POST finalize lặp lại trả 409, API hiện không có endpoint đọc lại kết
  quả bước giọng đang chờ. Phiên mất phản hồi này chưa được coi là khôi phục.
- RED riêng HTTP: 4 ca, 3 lỗi đúng mục tiêu; ca endpoint thường hết thời gian
  vẫn đạt. GREEN toàn Android: **430 ca / 0 failure / 0 error / 1 export skip**
  trong 87 lớp; lint **0 lỗi / 44 cảnh báo / 5 thông tin**, hai APK build đạt.
  Test dùng phản hồi thật chậm 250ms so với cửa sổ thường 100ms, không đợi
  60 giây trong test. Plan check **0 lỗi / 10 cảnh báo**. Review độc lập không
  có blocker. Cơ chế retry OkHttp hiện hữu không đổi; không tuyên bố mọi POST
  đều được transport đảm bảo gửi đúng một lần.

## Review thêm phản hồi upload/giọng

- HTTP 200 với `received=false` hoặc sai tên bước trước đây vẫn đánh dấu ack
  và gọi callback bỏ video. Giờ media/signals đòi đúng StepAck; giữ nguyên
  đường 409 `step_already_received` cho phản hồi đã mất.
- Trước đây phản hồi giọng có trạng thái lạ/thiếu câu/mã đọc lại đã xóa pending
  WAV và gọi callback trước khi bị từ chối. Giờ kiểm mode/policy, trạng thái,
  câu/mã và route trước mọi thay đổi. Callback chỉ chạy sau khi cập nhật đúng
  thử thách mới; legacy không purpose vẫn tương thích mã đọc lại vắng mặt.
- Đây là hai lỗi kiểm phản hồi tìm bằng review, không khẳng định là nguyên
  nhân ASR/lipsync ở ca người thật. Không đổi schema hoặc chốt AI.
- RED 36 ca của ba lớp: 7 lỗi đúng mục tiêu. GREEN toàn Android **441 ca /
  0 failure / 0 error / 1 export skip / 88 lớp**, lint **0 lỗi / 44 cảnh báo /
  5 thông tin**, hai APK build đạt. 11 ca mới kiểm response thật qua
  MockWebServer. Bốn fixture cũ trả nhầm ack media cho signals được sửa tên
  bước; assertion cũ giữ nguyên. Review độc lập không có blocker.
