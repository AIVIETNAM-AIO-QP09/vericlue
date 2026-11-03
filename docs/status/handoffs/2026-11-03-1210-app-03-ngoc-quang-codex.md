# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-03 12:10

**Nhánh:** `codex/APP-11-s24fe-integration`
**Trạng thái task sau phiên này:** doing

Tiếp theo bàn giao 10:42. API đang chạy từ `11dfc7ec6a85`, profile demo riêng
GenD 0.90 theo yêu cầu người dùng. Mốc giờ trong tài liệu là UTC+7.

## Đã xong
- Đối chiếu lượt 11:50: GenD và gaze trả `ok/fail`, năm kiểm tra mặt còn lại
  đạt. Chưa đến màn giọng, không có lỗi hạ tầng trong kết quả mô-đun. Tài khoản
  mới vẫn tồn tại; chưa commit liên kết khôi phục. Đây khác lượt 11:15 đã qua
  mặt nhưng bị lipsync chặn.
- Phát hiện lỗi xác định mốc video: `recordedDurationNanos` là snapshot trước
  khi CameraX gửi event, nhưng app ghép với giờ khi callback được xử lý trên
  main thread. Thời gian chờ UI làm lệch ước lượng origin. `RecordingEventClock`
  chụp giờ tại executor submission; callback giữ main executor, một clock mỗi
  lần ghi và vẫn kiểm recording generation. Không đổi lịch hoặc ngưỡng gaze.
- Subagent review độc lập cả helper, integration và nguồn chính thức CameraX
  1.4.1: mỗi runnable chứa một event, listener CameraController được gọi đồng
  bộ. Không có finding cần sửa. Test có delayed queue, timestamp từng event,
  scope accessor, exception và nested restoration.
- Rà soát GenD không tìm thêm lỗi wrapper: BGR/RGB, geometry/căn mặt, trọng số,
  lớp fake và chọn front vẫn phù hợp đối chứng upstream trước đó. Không đổi
  GenD, không tự tăng ngưỡng lần nữa. Không thể kết luận nguyên nhân điểm cao
  chỉ từ luma/độ nét một bản thu.
- Đối chứng optical clock trên video không đủ nhận dạng một offset duy nhất
  (đỉnh cạnh tranh, tín hiệu yếu và vùng không đồng thuận). Không lấy lag tốt
  nhất để sửa video hoặc nới cửa sổ gaze. Điểm iris/support không đổi membership
  trong lượt này, nên chưa có bằng chứng cho giả thuyết nhảy anchor.
- Đã kiểm public metadata và danh mục đầy đủ RTFS v2 bằng collector có giới hạn
  byte/trang, chặn redirect và kiểm version trước/sau. Chỉ metadata; không tải
  media/CSV/trọng số hoặc fit. Giấy phép tác giả không tự chứng minh đồng ý sử
  dụng từng người hay split theo người.
  Inventory không chứa ảnh donor, chỉ có metadata CSV về nguồn ảnh; việc đối
  chiếu cùng người qua các video/ảnh khác ID vẫn chưa giải quyết.

## Đang dở
- Mốc video vẫn là ước lượng: bản sửa loại trễ main queue, chưa đo latency
  encoder/sensor và chưa có lượt S24 FE trên APK mới.
- GenD phiên bản `align-upstream-numpy-v2` chưa có hiệu chỉnh/đánh giá độc lập
  phù hợp. Ngưỡng 0.90 là cấu hình vận hành demo, không phải kết quả đánh giá.
- Lipsync 11:15 có cờ căn câu và điểm SyncNet độc lập không đạt. Oracle Uroman
  tổng hợp không tái hiện lỗi chuẩn hóa; kiểm CTC không chứng minh lỗi căn câu.
  Frontend landmark mới vẫn offline, chưa bật API. Không ép degraded thành đạt.
- Đăng ký 11:10 và đăng nhập lại 11:13 đã đạt; khôi phục toàn luồng vẫn chưa
  nghiệm thu, PR135 giữ draft và không merge.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Hoàn tất kiểm tra Android, đóng gói APK trace=false cùng signer và cài
   `install -r` giữ dữ liệu; ghi receipt triển khai bên dưới.
2. Một lượt khôi phục mới trên S24 FE để đối chiếu gaze/GenD; chỉ đến bước
   giọng khi mặt thực sự đạt. Không dùng lượt điện thoại để báo độ chính xác.
3. Lấy gói GenD cũ hoặc dữ liệu có nguồn/quyền sử dụng, kiểm split theo người
   trước khi fit; metadata RTFS chưa đủ. Giữ VIVOS parity ngoài hiệu chỉnh.

## Quyết định, lưu ý, bẫy
- Không đổi API/profile/DB/khóa/tài khoản, không mở camera hoặc bấm consent thay
  người dùng. Không sửa thresholds.yaml/contracts/ADR; không push media hoặc
  trace. Giữ server chạy, không tắt máy.
- Bằng chứng riêng ở bundle `D:/vericlue/tmp/phone-demo-2026-11-02/diagnostics/`:
  `face-1150-private/replay-private.json`, `gend-demo090-20261103/flows-followup-safe.json`.
  Optical diagnostic ở `D:/vericlue/tmp/face-clock-optical-2026-11-03/`;
  metadata receipt ở `D:/vericlue/tmp/face-calibration-readiness-2026-11-03/evidence-v2/`.
  Đây là chẩn đoán kỹ thuật, không phải báo cáo đánh giá mô hình.

## Câu hỏi cho nhóm
- Vẫn cần đường dẫn gói GenD `gend-calibration/20261021_1310`, splits và nguồn
  dữ liệu; không suy việc thiếu trên máy này thành nhóm chưa từng hiệu chỉnh.

## Test đã chạy
- RED: kiểm delayed main queue thất bại đúng với cách lấy giờ cũ, origin
  1.500 ms thay vì 900 ms trong fixture tổng hợp. Không phải số đo máy thật.
- GREEN: `testDebugUnitTest --tests '*RecordingEventClockTest'` **5 đạt**.
  Dùng offline, max-workers=2, Kotlin incremental=false và các thuộc tính demo
  đặt trong dấu nháy. Hai lần trước dừng vì PowerShell tách `-P` không có nháy,
  rồi cache incremental không resolve symbol có sẵn; không sửa source để né.
- Full `testDebugUnitTest lintDebug assembleDebug` cùng cấu hình demo bình
  thường, offline/max-workers=2/incremental=false: **BUILD SUCCESSFUL**.
  XML tổng **450 ca: 449 đạt, 1 export skip, 0 failure/error**. Lint **0 lỗi,
  44 warning và 5 information**. BuildConfig live/signed=true, trace=false,
  endpoint localhost:8421. Log riêng `diagnostics/clock-fix-build-20261103.log`.
- `plan_check.py`: **0 lỗi, 10 cảnh báo** tải/lịch có sẵn; diff check sạch.
- Helper đóng gói ngoài repo được review độc lập: giữ backup APK/build-info,
  kiểm source Android sạch, signer/v2 signature, profile/API manifest, test và
  lint trước thay APK. Chưa có receipt cài máy tại thời điểm commit mã nguồn.
